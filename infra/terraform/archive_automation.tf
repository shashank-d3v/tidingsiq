resource "google_cloud_run_v2_job" "bronze_archive" {
  count = var.enable_bronze_archive_automation ? 1 : 0

  project             = var.project_id
  location            = local.automation_region
  name                = var.bronze_archive_job_name
  deletion_protection = false
  labels              = local.common_labels

  template {
    task_count  = 1
    parallelism = 1

    template {
      service_account = google_service_account.pipeline.email
      max_retries     = 1
      timeout         = var.pipeline_job_timeout

      containers {
        image   = local.pipeline_container_image
        command = ["python3"]
        args = concat(
          [
            "scripts/archive_bronze.py",
            "--project-id",
            var.project_id,
            "--archive-uri-prefix",
            "gs://${google_storage_bucket.bronze_archive.name}/automated",
            "--max-delete-rows",
            tostring(var.bronze_archive_max_delete_rows),
          ],
          var.bronze_archive_dry_run ? ["--dry-run"] : [],
          var.bronze_archive_delete_after_export ? ["--delete-after-export"] : [],
        )

        env {
          name  = "BRUIN_PROJECT_ID"
          value = var.project_id
        }

        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
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

resource "google_service_account" "bronze_archive_scheduler" {
  count = var.enable_bronze_archive_automation ? 1 : 0

  project      = var.project_id
  account_id   = "tidingsiq-archive-sched-${var.environment}"
  display_name = "TidingsIQ Archive Scheduler ${upper(var.environment)}"
  description  = "Invokes the TidingsIQ Bronze archive Cloud Run Job."
}

resource "google_cloud_run_v2_job_iam_member" "bronze_archive_scheduler_invoker" {
  count = var.enable_bronze_archive_automation ? 1 : 0

  project  = var.project_id
  location = google_cloud_run_v2_job.bronze_archive[0].location
  name     = google_cloud_run_v2_job.bronze_archive[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.bronze_archive_scheduler[0].email}"
}

resource "google_cloud_scheduler_job" "bronze_archive" {
  count = var.enable_bronze_archive_automation ? 1 : 0

  project          = var.project_id
  region           = local.automation_region
  name             = var.bronze_archive_scheduler_name
  description      = "Scheduled execution for the TidingsIQ Bronze archive job."
  schedule         = var.bronze_archive_schedule
  time_zone        = var.bronze_archive_schedule_time_zone
  paused           = var.bronze_archive_schedule_paused
  attempt_deadline = "600s"

  retry_config {
    retry_count = 1
  }

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${local.automation_region}/jobs/${var.bronze_archive_job_name}:run"
    body        = base64encode("{}")

    headers = {
      "Content-Type" = "application/json"
    }

    oauth_token {
      service_account_email = google_service_account.bronze_archive_scheduler[0].email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [
    google_cloud_run_v2_job_iam_member.bronze_archive_scheduler_invoker,
  ]
}

resource "google_logging_metric" "bronze_archive_failures" {
  count = var.enable_bronze_archive_automation ? 1 : 0

  project     = var.project_id
  name        = "bronze_archive_failures"
  description = "Count of failed Bronze archive executions emitted by the canonical archive worker."
  filter      = <<-EOT
resource.type="cloud_run_job"
resource.labels.job_name="${var.bronze_archive_job_name}"
textPayload:"BRONZE_ARCHIVE_SUMMARY"
textPayload:"status=failed"
EOT
}

resource "google_logging_metric" "bronze_archive_backlog_runs" {
  count = var.enable_bronze_archive_automation ? 1 : 0

  project     = var.project_id
  name        = "bronze_archive_backlog_runs"
  description = "Count of delete-enabled Bronze archive runs that still reported remaining eligible rows."
  filter      = <<-EOT
resource.type="cloud_run_job"
resource.labels.job_name="${var.bronze_archive_job_name}"
textPayload:"BRONZE_ARCHIVE_SUMMARY"
textPayload:"delete_after_export=True"
textPayload:"backlog_detected=True"
EOT
}

resource "google_monitoring_alert_policy" "bronze_archive_repeated_failures" {
  count = var.enable_bronze_archive_automation && local.enable_notification_email ? 1 : 0

  project               = var.project_id
  display_name          = "TidingsIQ Bronze Archive Repeated Failures"
  combiner              = "OR"
  enabled               = true
  notification_channels = [google_monitoring_notification_channel.pipeline_email[0].name]

  conditions {
    display_name = "Bronze archive failed twice within 24 hours"

    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.bronze_archive_failures[0].name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 1.5
      duration        = "0s"

      aggregations {
        alignment_period     = "86400s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = []
      }

      trigger {
        count = 1
      }
    }
  }

  alert_strategy {
    auto_close = "86400s"

    notification_rate_limit {
      period = "3600s"
    }
  }

  documentation {
    mime_type = "text/markdown"
    content   = "The Bronze archive worker emitted at least two failed `BRONZE_ARCHIVE_SUMMARY` runs in the last 24 hours."
  }
}

resource "google_monitoring_alert_policy" "bronze_archive_backlog" {
  count = var.enable_bronze_archive_automation && local.enable_notification_email ? 1 : 0

  project               = var.project_id
  display_name          = "TidingsIQ Bronze Archive Backlog"
  combiner              = "OR"
  enabled               = true
  notification_channels = [google_monitoring_notification_channel.pipeline_email[0].name]

  conditions {
    display_name = "Bronze archive backlog detected twice within 24 hours"

    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.bronze_archive_backlog_runs[0].name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 1.5
      duration        = "0s"

      aggregations {
        alignment_period     = "86400s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = []
      }

      trigger {
        count = 1
      }
    }
  }

  alert_strategy {
    auto_close = "86400s"

    notification_rate_limit {
      period = "3600s"
    }
  }

  documentation {
    mime_type = "text/markdown"
    content   = "The Bronze archive worker reported remaining eligible rows on at least two delete-enabled runs in the last 24 hours."
  }
}
