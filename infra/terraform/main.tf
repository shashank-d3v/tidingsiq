provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  bronze_archive_bucket_name = trimspace(var.bronze_archive_bucket_name) != "" ? trimspace(var.bronze_archive_bucket_name) : "${var.project_id}-tidingsiq-bronze-archive"
  archive_bucket_location    = coalesce(var.archive_bucket_location, var.bigquery_location)

  common_labels = merge(
    {
      app         = "tidingsiq"
      environment = var.environment
      managed_by  = "terraform"
    },
    var.labels
  )

  datasets = {
    bronze = {
      description = "Raw landed GDELT records and ingestion metadata."
    }
    bronze_staging = {
      description = "Operational staging dataset used by the Bronze load path during merge writes."
    }
    silver = {
      description = "Normalized and deduplicated article-level models."
    }
    gold = {
      description = "Application-facing positive news feed and serving models."
    }
    gold_staging = {
      description = "Operational staging dataset used by dlt merge loads for Gold assets."
    }
  }
}

resource "google_bigquery_dataset" "datasets" {
  for_each = local.datasets

  project                    = var.project_id
  dataset_id                 = each.key
  location                   = var.bigquery_location
  description                = each.value.description
  delete_contents_on_destroy = false
  labels                     = local.common_labels
}

resource "google_storage_bucket" "bronze_archive" {
  project                     = var.project_id
  name                        = local.bronze_archive_bucket_name
  location                    = local.archive_bucket_location
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  labels                      = local.common_labels

  lifecycle_rule {
    condition {
      age = var.bronze_archive_retention_days
    }

    action {
      type = "Delete"
    }
  }
}

resource "google_service_account" "pipeline" {
  project      = var.project_id
  account_id   = "tidingsiq-pipeline-${var.environment}"
  display_name = "TidingsIQ Pipeline ${upper(var.environment)}"
  description  = "Executes Bruin ingestion and transformation workloads for TidingsIQ."
}

resource "google_service_account" "app" {
  project      = var.project_id
  account_id   = "tidingsiq-app-${var.environment}"
  display_name = "TidingsIQ App ${upper(var.environment)}"
  description  = "Queries the Gold dataset for the TidingsIQ Streamlit app."
}

resource "google_project_iam_member" "pipeline_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_project_iam_member" "app_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.app.email}"
}

resource "google_bigquery_dataset_iam_member" "pipeline_dataset_editor" {
  for_each = google_bigquery_dataset.datasets

  dataset_id = each.value.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_bigquery_dataset_iam_member" "app_gold_viewer" {
  dataset_id = google_bigquery_dataset.datasets["gold"].dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.app.email}"
}

resource "google_storage_bucket_iam_member" "pipeline_bronze_archive_object_admin" {
  bucket = google_storage_bucket.bronze_archive.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.pipeline.email}"
}
