output "dataset_ids" {
  description = "BigQuery dataset IDs provisioned for TidingsIQ."
  value = {
    for name, dataset in google_bigquery_dataset.datasets : name => dataset.dataset_id
  }
}

output "pipeline_service_account_email" {
  description = "Service account email for pipeline execution."
  value       = google_service_account.pipeline.email
}

output "app_service_account_email" {
  description = "Service account email for the Streamlit app."
  value       = var.enable_app_hosting ? google_service_account.app[0].email : null
}

output "bronze_archive_bucket_name" {
  description = "GCS bucket name for archived Bronze exports."
  value       = google_storage_bucket.bronze_archive.name
}

output "pipeline_artifact_repository_name" {
  description = "Artifact Registry repository name for the shared pipeline image when any pipeline image consumer is enabled."
  value       = local.enable_pipeline_image_consumers ? google_artifact_registry_repository.pipeline[0].name : null
}

output "pipeline_container_image" {
  description = "Configured container image URI for the shared pipeline image."
  value       = local.enable_pipeline_image_consumers ? local.pipeline_container_image : null
}

output "pipeline_cloud_run_job_name" {
  description = "Cloud Run Job name for pipeline automation when enabled."
  value       = var.enable_pipeline_automation ? google_cloud_run_v2_job.pipeline[0].name : null
}

output "pipeline_scheduler_job_name" {
  description = "Cloud Scheduler job name for pipeline automation when enabled."
  value       = var.enable_pipeline_automation ? google_cloud_scheduler_job.pipeline[0].name : null
}

output "pipeline_scheduler_service_account_email" {
  description = "Service account email used by Cloud Scheduler to invoke the Cloud Run Job when automation is enabled."
  value       = var.enable_pipeline_automation ? google_service_account.scheduler[0].email : null
}

output "restricted_egress_network_name" {
  description = "Dedicated VPC name for restricted outbound traffic when the restricted-egress slice is enabled."
  value       = local.enable_restricted_egress_resources ? google_compute_network.restricted_egress[0].name : null
}

output "restricted_egress_connector_name" {
  description = "Serverless VPC Access connector name used for restricted outbound traffic when enabled."
  value       = local.enable_restricted_egress_resources ? google_vpc_access_connector.restricted_egress[0].name : null
}

output "restricted_egress_blocked_attempts_metric_name" {
  description = "Log-based metric name for firewall-denied outbound traffic through the restricted-egress connector when enabled."
  value       = local.enable_restricted_egress_resources ? google_logging_metric.restricted_egress_blocked_attempts[0].name : null
}

output "reporting_service_account_email" {
  description = "Service account email for the daily reporting job when reporting is enabled."
  value       = var.enable_pipeline_reporting ? google_service_account.reporting[0].email : null
}

output "reporting_cloud_run_job_name" {
  description = "Cloud Run Job name for the daily reporting task when reporting is enabled."
  value       = var.enable_pipeline_reporting ? google_cloud_run_v2_job.reporting[0].name : null
}

output "reporting_scheduler_job_name" {
  description = "Cloud Scheduler job name for the daily reporting task when reporting is enabled."
  value       = var.enable_pipeline_reporting ? google_cloud_scheduler_job.reporting[0].name : null
}

output "bronze_archive_cloud_run_job_name" {
  description = "Cloud Run Job name for Bronze archive automation when enabled."
  value       = var.enable_bronze_archive_automation ? google_cloud_run_v2_job.bronze_archive[0].name : null
}

output "bronze_archive_service_account_email" {
  description = "Service account email for the Bronze archive worker when archive automation is enabled."
  value       = var.enable_bronze_archive_automation ? google_service_account.bronze_archive[0].email : null
}

output "bronze_archive_scheduler_job_name" {
  description = "Cloud Scheduler job name for Bronze archive automation when enabled."
  value       = var.enable_bronze_archive_automation ? google_cloud_scheduler_job.bronze_archive[0].name : null
}

output "bronze_archive_scheduler_service_account_email" {
  description = "Service account email used by Cloud Scheduler to invoke the Bronze archive Cloud Run Job when automation is enabled."
  value       = var.enable_bronze_archive_automation ? google_service_account.bronze_archive_scheduler[0].email : null
}

output "notification_email_channel_name" {
  description = "Monitoring email notification channel name when reporting or archive notifications are enabled."
  value       = (var.enable_pipeline_reporting || var.enable_bronze_archive_automation) && trimspace(var.notification_email_recipient) != "" ? google_monitoring_notification_channel.pipeline_email[0].name : null
}

output "app_artifact_repository_name" {
  description = "Artifact Registry repository name for the Streamlit app image when app hosting is enabled."
  value       = var.enable_app_hosting ? google_artifact_registry_repository.app[0].name : null
}

output "app_container_image" {
  description = "Recommended or configured container image URI for the Streamlit app hosting path."
  value       = var.enable_app_hosting ? local.app_container_image : null
}

output "app_cloud_run_service_name" {
  description = "Cloud Run service name for the Streamlit app when app hosting is enabled."
  value       = var.enable_app_hosting ? google_cloud_run_v2_service.app[0].name : null
}

output "app_cloud_run_service_uri" {
  description = "Cloud Run service URI for the Streamlit app when app hosting is enabled."
  value       = var.enable_app_hosting ? google_cloud_run_v2_service.app[0].uri : null
}

output "app_load_balancer_ip" {
  description = "Global IP address for the Streamlit app external HTTPS load balancer when app edge is enabled."
  value       = local.app_edge_enabled ? google_compute_global_address.app[0].address : null
}

output "app_https_hostname" {
  description = "DNS hostname configured for the Streamlit app external HTTPS load balancer when app edge is enabled."
  value       = local.app_edge_enabled ? trimspace(var.app_domain_name) : null
}

output "app_cloud_armor_policy_name" {
  description = "Cloud Armor security policy name for the Streamlit app when app edge is enabled."
  value       = local.app_edge_enabled ? google_compute_security_policy.app[0].name : null
}

output "app_backend_service_name" {
  description = "External HTTPS load balancer backend service name for the Streamlit app when app edge is enabled."
  value       = local.app_edge_enabled ? google_compute_backend_service.app[0].name : null
}
