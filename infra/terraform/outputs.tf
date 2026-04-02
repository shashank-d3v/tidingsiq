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
