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

variable "dataset_id_prefix" {
  description = "Optional prefix for BigQuery dataset IDs, for example prod_bronze. Leave empty to keep dataset IDs as bronze, silver, and gold."
  type        = string
  default     = ""

  validation {
    condition     = var.dataset_id_prefix == "" || can(regex("^[A-Za-z_][A-Za-z0-9_]*$", var.dataset_id_prefix))
    error_message = "dataset_id_prefix must be empty or contain only letters, numbers, and underscores, starting with a letter or underscore."
  }
}

variable "labels" {
  description = "Optional additional labels to apply where supported."
  type        = map(string)
  default     = {}
}
