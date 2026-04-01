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

variable "labels" {
  description = "Optional additional labels to apply where supported."
  type        = map(string)
  default     = {}
}
