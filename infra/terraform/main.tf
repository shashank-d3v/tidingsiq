provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
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
    silver = {
      description = "Normalized and deduplicated article-level models."
    }
    gold = {
      description = "Application-facing positive news feed and serving models."
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
