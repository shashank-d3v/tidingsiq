data "google_project" "current" {
  project_id = var.project_id
}

locals {
  automation_region          = coalesce(var.automation_region, var.region)
  artifact_registry_location = coalesce(var.artifact_registry_location, local.automation_region)
  pipeline_container_image   = trimspace(var.pipeline_container_image) != "" ? trimspace(var.pipeline_container_image) : "${local.artifact_registry_location}-docker.pkg.dev/${var.project_id}/${var.pipeline_artifact_repository_id}/tidingsiq-bruin:latest"
  pipeline_job_run_uri       = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${local.automation_region}/jobs/${var.pipeline_job_name}:run"
  cloud_run_service_agent    = "service-${data.google_project.current.number}@serverless-robot-prod.iam.gserviceaccount.com"
}

resource "google_service_account" "scheduler" {
  count = var.enable_pipeline_automation ? 1 : 0

  project      = var.project_id
  account_id   = "tidingsiq-scheduler-${var.environment}"
  display_name = "TidingsIQ Scheduler ${upper(var.environment)}"
  description  = "Invokes the TidingsIQ Cloud Run Job on a schedule."
}

resource "google_artifact_registry_repository" "pipeline" {
  count = var.enable_pipeline_automation ? 1 : 0

  project       = var.project_id
  location      = local.artifact_registry_location
  repository_id = var.pipeline_artifact_repository_id
  format        = "DOCKER"
  description   = "Container images for the TidingsIQ Bruin pipeline."
  labels        = local.common_labels
}

resource "google_artifact_registry_repository_iam_member" "cloud_run_service_agent_reader" {
  count = var.enable_pipeline_automation ? 1 : 0

  project    = var.project_id
  location   = google_artifact_registry_repository.pipeline[0].location
  repository = google_artifact_registry_repository.pipeline[0].repository_id
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${local.cloud_run_service_agent}"
}

resource "google_cloud_run_v2_job" "pipeline" {
  count = var.enable_pipeline_automation ? 1 : 0

  project             = var.project_id
  location            = local.automation_region
  name                = var.pipeline_job_name
  deletion_protection = false
  labels              = local.common_labels

  template {
    task_count  = var.pipeline_job_task_count
    parallelism = var.pipeline_job_parallelism

    template {
      service_account = google_service_account.pipeline.email
      max_retries     = var.pipeline_job_max_retries
      timeout         = var.pipeline_job_timeout

      containers {
        image = local.pipeline_container_image
        args  = ["run", "pipeline/bruin/pipeline.yml"]

        env {
          name  = "BRUIN_PROJECT_ID"
          value = var.project_id
        }

        env {
          name  = "BRUIN_BIGQUERY_LOCATION"
          value = var.bigquery_location
        }

        env {
          name  = "GDELT_MAX_FILES"
          value = tostring(var.pipeline_gdelt_max_files)
        }

        env {
          name  = "GDELT_DISABLE_SSL_VERIFY"
          value = var.pipeline_gdelt_disable_ssl_verify ? "true" : "false"
        }

        resources {
          limits = {
            cpu    = "1"
            memory = var.pipeline_job_memory_limit
          }
        }
      }
    }
  }

  depends_on = [
    google_artifact_registry_repository_iam_member.cloud_run_service_agent_reader,
  ]
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_invoker" {
  count = var.enable_pipeline_automation ? 1 : 0

  project  = var.project_id
  location = google_cloud_run_v2_job.pipeline[0].location
  name     = google_cloud_run_v2_job.pipeline[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler[0].email}"
}

resource "google_cloud_scheduler_job" "pipeline" {
  count = var.enable_pipeline_automation ? 1 : 0

  project          = var.project_id
  region           = local.automation_region
  name             = var.pipeline_scheduler_name
  description      = "Scheduled execution for the TidingsIQ Bruin Cloud Run Job."
  schedule         = var.pipeline_schedule
  time_zone        = var.pipeline_schedule_time_zone
  paused           = var.pipeline_schedule_paused
  attempt_deadline = "600s"

  retry_config {
    retry_count = 1
  }

  http_target {
    http_method = "POST"
    uri         = local.pipeline_job_run_uri
    body        = base64encode("{}")

    headers = {
      "Content-Type" = "application/json"
    }

    oauth_token {
      service_account_email = google_service_account.scheduler[0].email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [
    google_cloud_run_v2_job_iam_member.scheduler_invoker,
  ]
}
