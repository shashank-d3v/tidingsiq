variable "project_id" {
  description = "Target GCP project ID for TidingsIQ resources."
  type        = string

  validation {
    condition     = length(trimspace(var.project_id)) > 0
    error_message = "project_id must be a non-empty GCP project ID."
  }
}

variable "environment" {
  description = "Short environment name used in labels and service account naming."
  type        = string
  default     = "dev"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]*$", var.environment))
    error_message = "environment must start with a lowercase letter and contain only lowercase letters, digits, and hyphens."
  }
}

variable "region" {
  description = "Default GCP region for provider-level configuration."
  type        = string
  default     = "us-central1"
}

variable "bigquery_location" {
  description = "BigQuery dataset location."
  type        = string
  default     = "US"
}

variable "archive_bucket_location" {
  description = "Location for the Bronze archive bucket. Should be compatible with the BigQuery dataset location."
  type        = string
  default     = null
}

variable "bronze_archive_bucket_name" {
  description = "Optional explicit name for the Bronze archive bucket. Defaults to a project-scoped derived name."
  type        = string
  default     = ""
}

variable "bronze_archive_retention_days" {
  description = "Retention period for Bronze archive objects in GCS before lifecycle deletion."
  type        = number
  default     = 365

  validation {
    condition     = var.bronze_archive_retention_days >= 30
    error_message = "bronze_archive_retention_days must be at least 30."
  }
}

variable "labels" {
  description = "Optional additional labels to apply where supported."
  type        = map(string)
  default     = {}
}

variable "enable_pipeline_automation" {
  description = "When true, provisions Artifact Registry, a Cloud Run Job, and a Cloud Scheduler trigger for the Bruin pipeline."
  type        = bool
  default     = false
}

variable "automation_region" {
  description = "Region for Cloud Run Jobs and Cloud Scheduler. Defaults to region when null."
  type        = string
  default     = null
}

variable "artifact_registry_location" {
  description = "Location for the Artifact Registry repository. Defaults to automation_region."
  type        = string
  default     = null
}

variable "pipeline_artifact_repository_id" {
  description = "Artifact Registry repository ID for the Bruin pipeline image."
  type        = string
  default     = "tidingsiq-pipeline"
}

variable "pipeline_container_image" {
  description = "Full container image URI for the pipeline job. Leave empty to use the conventional Artifact Registry path."
  type        = string
  default     = ""
}

variable "pipeline_job_name" {
  description = "Cloud Run Job name for the TidingsIQ pipeline."
  type        = string
  default     = "tidingsiq-pipeline"
}

variable "pipeline_job_timeout" {
  description = "Per-task timeout for the Cloud Run Job."
  type        = string
  default     = "3600s"
}

variable "pipeline_job_max_retries" {
  description = "Maximum retries per Cloud Run Job task."
  type        = number
  default     = 1
}

variable "pipeline_job_task_count" {
  description = "Task count for the Cloud Run Job execution."
  type        = number
  default     = 1
}

variable "pipeline_job_parallelism" {
  description = "Parallelism for the Cloud Run Job execution."
  type        = number
  default     = 1
}

variable "pipeline_job_memory_limit" {
  description = "Memory limit for the Cloud Run Job container."
  type        = string
  default     = "2Gi"
}

variable "pipeline_gdelt_max_files" {
  description = "Default GDELT file cap injected into the Cloud Run Job environment."
  type        = number
  default     = 4
}

variable "pipeline_gdelt_disable_ssl_verify" {
  description = "When true, sets GDELT_DISABLE_SSL_VERIFY in the Cloud Run Job as a compatibility workaround for upstream certificate validation failures."
  type        = bool
  default     = false
}

variable "pipeline_scheduler_name" {
  description = "Cloud Scheduler job name for pipeline execution."
  type        = string
  default     = "tidingsiq-pipeline-schedule"
}

variable "pipeline_schedule" {
  description = "Cron schedule for the pipeline automation."
  type        = string
  default     = "0 */6 * * *"
}

variable "pipeline_schedule_time_zone" {
  description = "Time zone for the Cloud Scheduler cron expression."
  type        = string
  default     = "UTC"
}

variable "pipeline_schedule_paused" {
  description = "When true, creates the Cloud Scheduler job in a paused state."
  type        = bool
  default     = true
}
