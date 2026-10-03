variable "enable_static_dashboard" {
  description = "Serve the static public dashboard with separately published Gold snapshots."
  type        = bool
  default     = false
  validation {
    condition     = !var.enable_static_dashboard || (var.enable_app_hosting && var.enable_pipeline_reporting)
    error_message = "The static dashboard requires app hosting and pipeline reporting."
  }
}
variable "static_publisher_image" {
  description = "Pinned image for the daily eligible-feed publisher."
  type        = string
  default     = ""
}
variable "static_publish_schedule_paused" {
  type    = bool
  default = true
}
locals {
  static_bucket_name = "${var.project_id}-static-feed"
}
resource "google_storage_bucket" "static_feed" {
  count                       = var.enable_static_dashboard ? 1 : 0
  project                     = var.project_id
  name                        = local.static_bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  versioning { enabled = true }
  # Live hashed feed files must survive a paused/failed publisher indefinitely.
  # Only private audits expire by age; cleanup must preserve manifest references.
  lifecycle_rule {
    condition {
      age            = 45
      matches_prefix = ["_audit/"]
    }
    action { type = "Delete" }
  }
  lifecycle_rule {
    condition {
      num_newer_versions = 7
      with_state         = "ARCHIVED"
    }
    action { type = "Delete" }
  }
}
resource "google_service_account" "static_reader" {
  count        = var.enable_static_dashboard ? 1 : 0
  project      = var.project_id
  account_id   = "tidingsiq-static-reader"
  display_name = "TidingsIQ static frontend (no warehouse access)"
}
resource "google_storage_bucket_iam_member" "static_reader" {
  count  = var.enable_static_dashboard ? 1 : 0
  bucket = google_storage_bucket.static_feed[0].name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.static_reader[0].email}"
}
resource "google_service_account" "static_publisher" {
  count        = var.enable_static_dashboard ? 1 : 0
  project      = var.project_id
  account_id   = "tidingsiq-static-publisher"
  display_name = "TidingsIQ daily static feed publisher"
}
resource "google_project_iam_member" "static_publisher_jobs" {
  count   = var.enable_static_dashboard ? 1 : 0
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.static_publisher[0].email}"
}
resource "google_bigquery_dataset_iam_member" "static_publisher_gold" {
  count      = var.enable_static_dashboard ? 1 : 0
  dataset_id = google_bigquery_dataset.datasets["gold"].dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.static_publisher[0].email}"
}
# Read execution outcomes without granting pipeline invocation or mutation.
resource "google_cloud_run_v2_job_iam_member" "static_publisher_pipeline_viewer" {
  count      = var.enable_static_dashboard ? 1 : 0
  project    = var.project_id
  location   = local.automation_region
  name       = var.pipeline_job_name
  role       = "roles/run.viewer"
  member     = "serviceAccount:${google_service_account.static_publisher[0].email}"
  depends_on = [google_cloud_run_v2_job.pipeline]
}
resource "google_storage_bucket_iam_member" "static_publisher" {
  count  = var.enable_static_dashboard ? 1 : 0
  bucket = google_storage_bucket.static_feed[0].name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.static_publisher[0].email}"
}
resource "google_cloud_run_v2_job" "static_publisher" {
  count               = var.enable_static_dashboard ? 1 : 0
  project             = var.project_id
  location            = local.automation_region
  name                = "tidingsiq-static-publisher"
  deletion_protection = false
  template {
    task_count = 1
    template {
      service_account = google_service_account.static_publisher[0].email
      max_retries     = 1
      timeout         = "600s"
      containers {
        image = var.static_publisher_image
        args  = ["--project", var.project_id, "--bucket", google_storage_bucket.static_feed[0].name, "--location", var.bigquery_location, "--pipeline-region", local.automation_region, "--pipeline-job", var.pipeline_job_name]
        resources {
          limits = { cpu = "1", memory = "512Mi" }
        }
      }
    }
  }
  depends_on = [google_storage_bucket_iam_member.static_publisher, google_bigquery_dataset_iam_member.static_publisher_gold, google_project_iam_member.static_publisher_jobs, google_cloud_run_v2_job_iam_member.static_publisher_pipeline_viewer]
}
resource "google_cloud_run_v2_job_iam_member" "static_publisher_invoker" {
  count    = var.enable_static_dashboard ? 1 : 0
  project  = var.project_id
  location = local.automation_region
  name     = google_cloud_run_v2_job.static_publisher[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.reporting_scheduler[0].email}"
}
resource "google_cloud_scheduler_job" "static_publisher" {
  count            = var.enable_static_dashboard ? 1 : 0
  project          = var.project_id
  region           = local.automation_region
  name             = "tidingsiq-static-publisher-schedule"
  description      = "Publish verified static feed after the 06:00 pipeline and 06:20 summary."
  schedule         = "30 6 * * *"
  time_zone        = "Asia/Kolkata"
  paused           = var.static_publish_schedule_paused
  attempt_deadline = "600s"
  retry_config { retry_count = 1 }
  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${local.automation_region}/jobs/${google_cloud_run_v2_job.static_publisher[0].name}:run"
    body        = base64encode("{}")
    headers     = { "Content-Type" = "application/json" }
    oauth_token {
      service_account_email = google_service_account.reporting_scheduler[0].email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
  depends_on = [google_cloud_run_v2_job_iam_member.static_publisher_invoker]
}
resource "google_monitoring_alert_policy" "static_publish_failure" {
  count                 = var.enable_static_dashboard && local.enable_notification_email ? 1 : 0
  project               = var.project_id
  display_name          = "TidingsIQ static feed publication failed"
  combiner              = "OR"
  notification_channels = [google_monitoring_notification_channel.pipeline_email[0].name]
  conditions {
    display_name = "Static publisher failed"
    condition_matched_log {
      filter = "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"tidingsiq-static-publisher\" AND textPayload:\"STATIC_FEED_PUBLISH status=failed\""
    }
  }
  alert_strategy {
    auto_close = "86400s"
    notification_rate_limit { period = "3600s" }
  }
  documentation {
    mime_type = "text/markdown"
    content   = "The public feed retains its last verified edition. Check the pipeline, publisher logs and manifest freshness before retrying. Never replace the manifest before all referenced files are verified."
  }
}

resource "google_monitoring_alert_policy" "static_dedup_shift" {
  count                 = var.enable_static_dashboard && local.enable_notification_email ? 1 : 0
  project               = var.project_id
  display_name          = "TidingsIQ story suppression changed"
  combiner              = "OR"
  notification_channels = [google_monitoring_notification_channel.pipeline_email[0].name]
  conditions {
    display_name = "Story suppression changed more than 15 percentage points"
    condition_matched_log {
      filter = "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"tidingsiq-static-publisher\" AND textPayload:\"STATIC_FEED_DEDUP status=warning\""
    }
  }
  alert_strategy {
    auto_close = "86400s"
    notification_rate_limit { period = "3600s" }
  }
  documentation {
    mime_type = "text/markdown"
    content   = "Publication remains enabled. Compare the private _audit objects and matcher versions with the prior edition. Review unusually large clusters before changing matching rules."
  }
}
