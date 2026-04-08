locals {
  enable_notification_email = trimspace(var.notification_email_recipient) != ""
}

resource "google_service_account" "reporting" {
  count = var.enable_pipeline_reporting ? 1 : 0

  project      = var.project_id
  account_id   = "tidingsiq-reporting-${var.environment}"
  display_name = "TidingsIQ Reporting ${upper(var.environment)}"
  description  = "Runs the daily TidingsIQ warehouse summary reporting job."
}

resource "google_project_iam_member" "reporting_job_user" {
  count = var.enable_pipeline_reporting ? 1 : 0

  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.reporting[0].email}"
}

resource "google_bigquery_dataset_iam_member" "reporting_gold_viewer" {
  count = var.enable_pipeline_reporting ? 1 : 0

  dataset_id = google_bigquery_dataset.datasets["gold"].dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.reporting[0].email}"
}

resource "google_cloud_run_v2_job" "reporting" {
  count = var.enable_pipeline_reporting ? 1 : 0

  project             = var.project_id
  location            = local.automation_region
  name                = var.reporting_job_name
  deletion_protection = false
  labels              = local.common_labels

  template {
    task_count  = 1
    parallelism = 1

    template {
      service_account = google_service_account.reporting[0].email
      max_retries     = 1
      timeout         = "600s"

      containers {
        image = local.pipeline_container_image
        command = ["python3"]
        args    = ["scripts/daily_pipeline_report.py"]

        env {
          name  = "TIDINGSIQ_GCP_PROJECT"
          value = var.project_id
        }

        env {
          name  = "BRUIN_PROJECT_ID"
          value = var.project_id
        }

        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }

        env {
          name  = "TIDINGSIQ_GOLD_FEED_TABLE"
          value = "${var.project_id}.gold.positive_news_feed"
        }

        env {
          name  = "TIDINGSIQ_GOLD_METRICS_TABLE"
          value = "${var.project_id}.gold.pipeline_run_metrics"
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
      }
    }
  }

  depends_on = [
    google_artifact_registry_repository_iam_member.cloud_run_service_agent_reader,
  ]
}

resource "google_service_account" "reporting_scheduler" {
  count = var.enable_pipeline_reporting ? 1 : 0

  project      = var.project_id
  account_id   = "tidingsiq-report-sched-${var.environment}"
  display_name = "TidingsIQ Reporting Scheduler ${upper(var.environment)}"
  description  = "Invokes the TidingsIQ daily reporting Cloud Run Job."
}

resource "google_cloud_run_v2_job_iam_member" "reporting_scheduler_invoker" {
  count = var.enable_pipeline_reporting ? 1 : 0

  project  = var.project_id
  location = google_cloud_run_v2_job.reporting[0].location
  name     = google_cloud_run_v2_job.reporting[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.reporting_scheduler[0].email}"
}

resource "google_cloud_scheduler_job" "reporting" {
  count = var.enable_pipeline_reporting ? 1 : 0

  project          = var.project_id
  region           = local.automation_region
  name             = var.reporting_scheduler_name
  description      = "Post-run summary execution for the TidingsIQ warehouse."
  schedule         = var.reporting_schedule
  time_zone        = var.reporting_schedule_time_zone
  paused           = false
  attempt_deadline = "600s"

  retry_config {
    retry_count = 1
  }

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${local.automation_region}/jobs/${var.reporting_job_name}:run"
    body        = base64encode("{}")

    headers = {
      "Content-Type" = "application/json"
    }

    oauth_token {
      service_account_email = google_service_account.reporting_scheduler[0].email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [
    google_cloud_run_v2_job_iam_member.reporting_scheduler_invoker,
  ]
}

resource "google_monitoring_notification_channel" "pipeline_email" {
  count = var.enable_pipeline_reporting && local.enable_notification_email ? 1 : 0

  project      = var.project_id
  display_name = "TidingsIQ Pipeline Email"
  type         = "email"

  labels = {
    email_address = trimspace(var.notification_email_recipient)
  }

  user_labels = local.common_labels
}

resource "google_monitoring_alert_policy" "pipeline_failure" {
  count = var.enable_pipeline_reporting && local.enable_notification_email ? 1 : 0

  project               = var.project_id
  display_name          = "TidingsIQ Pipeline Failure"
  combiner              = "OR"
  enabled               = true
  notification_channels = [google_monitoring_notification_channel.pipeline_email[0].name]

  conditions {
    display_name = "Matched pipeline failure logs"

    condition_matched_log {
      filter = <<-EOT
resource.type="cloud_run_job"
resource.labels.job_name="${var.pipeline_job_name}"
(
  severity>=ERROR
  OR textPayload:"bruin run completed with failures"
  OR textPayload=~"^FAIL\\s"
)
EOT
    }
  }

  alert_strategy {
    auto_close = "1800s"

    notification_rate_limit {
      period = "300s"
    }
  }

  documentation {
    mime_type = "text/markdown"
    content   = "Matched a Cloud Run Job pipeline failure log for `${var.pipeline_job_name}` in `${local.automation_region}`."
  }
}

resource "google_monitoring_alert_policy" "daily_summary" {
  count = var.enable_pipeline_reporting && local.enable_notification_email ? 1 : 0

  project               = var.project_id
  display_name          = "TidingsIQ Daily Pipeline Summary"
  combiner              = "OR"
  enabled               = true
  notification_channels = [google_monitoring_notification_channel.pipeline_email[0].name]

  conditions {
    display_name = "Matched daily summary logs"

    condition_matched_log {
      filter = <<-EOT
resource.type="cloud_run_job"
resource.labels.job_name="${var.reporting_job_name}"
textPayload:"DAILY_PIPELINE_SUMMARY"
EOT
    }
  }

  alert_strategy {
    auto_close = "7200s"

    notification_rate_limit {
      period = "3600s"
    }
  }

  documentation {
    mime_type = "text/markdown"
    content   = "Matched the daily pipeline summary log emitted by `${var.reporting_job_name}`."
  }
}
