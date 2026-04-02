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
  value       = google_service_account.app.email
}

output "bronze_archive_bucket_name" {
  description = "GCS bucket name for archived Bronze exports."
  value       = google_storage_bucket.bronze_archive.name
}

output "pipeline_artifact_repository_name" {
  description = "Artifact Registry repository name for the pipeline image when automation is enabled."
  value       = var.enable_pipeline_automation ? google_artifact_registry_repository.pipeline[0].name : null
}

output "pipeline_container_image" {
  description = "Recommended or configured container image URI for the pipeline automation."
  value       = var.enable_pipeline_automation ? local.pipeline_container_image : null
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
