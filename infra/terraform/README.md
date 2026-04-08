# TidingsIQ Terraform Foundation

This directory contains the first infrastructure slice for TidingsIQ. It provisions the minimum GCP resources needed to support the data pipeline and app:

- BigQuery datasets: `bronze`, `silver`, `gold`
- operational BigQuery dataset: `bronze_staging`
- Bronze archive bucket with lifecycle deletion after the retention window
- pipeline service account for Bruin workloads
- app service account for Streamlit reads
- minimum BigQuery IAM bindings for both identities
- applied pipeline automation resources for Artifact Registry, Cloud Run Jobs, and Cloud Scheduler
- reporting resources for a daily Cloud Run summary job and Monitoring-based email notifications
- optional app hosting resources for Artifact Registry and a Cloud Run service

## Prerequisites

- Terraform `>= 1.6`
- access to a target GCP project
- Google application default credentials or another supported Terraform authentication method
- required APIs already enabled in the target project, at minimum BigQuery and IAM

This scaffold does not enable project APIs automatically. That is intentional to keep the first version small and permission-conscious.

Cloud Storage must also be enabled in the target project because Bronze archival is now provisioned in Terraform.

If you enable the pipeline automation slice, the following APIs must also already be enabled:

- Artifact Registry API
- Cloud Run Admin API
- Cloud Scheduler API
- Cloud Monitoring API

## Files

- `versions.tf`: Terraform and provider constraints
- `variables.tf`: input variables
- `main.tf`: provider, datasets, service accounts, and IAM
- `outputs.tf`: useful resource outputs
- `terraform.tfvars.example`: starter local variable file
- `future_multi_environment.md`: reference notes for a possible future multi-environment setup
- `automation.tf`: pipeline automation resources
- `reporting.tf`: daily reporting job and email notification resources
- `app_hosting.tf`: optional Streamlit app hosting resources

## Usage

Create a local variable file from the example. `terraform.tfvars` is intended for machine-local configuration and is gitignored.

```bash
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform fmt -recursive
terraform validate
terraform plan
```

Apply only after reviewing the plan against the intended project:

```bash
terraform apply
```

## Input Variables

| Name | Required | Default | Purpose |
|---|---|---|---|
| `project_id` | Yes | none | Target GCP project ID |
| `environment` | No | `dev` | Environment label and service account suffix |
| `region` | No | `us-central1` | Provider region |
| `bigquery_location` | No | `US` | BigQuery dataset location |
| `archive_bucket_location` | No | `null` | Bronze archive bucket location; falls back to `bigquery_location` |
| `bronze_archive_bucket_name` | No | derived | Explicit Bronze archive bucket name |
| `bronze_archive_retention_days` | No | `365` | GCS lifecycle retention for archived Bronze objects |
| `enable_pipeline_automation` | No | `false` | Enables Artifact Registry, Cloud Run Job, and Cloud Scheduler resources |
| `automation_region` | No | `null` | Region for Cloud Run Job and Cloud Scheduler |
| `artifact_registry_location` | No | `null` | Artifact Registry location; falls back to `automation_region` |
| `pipeline_artifact_repository_id` | No | `tidingsiq-pipeline` | Artifact Registry repository ID for the pipeline image |
| `pipeline_container_image` | No | derived | Full image URI for the pipeline container |
| `pipeline_job_name` | No | `tidingsiq-pipeline` | Cloud Run Job name |
| `pipeline_job_memory_limit` | No | `2Gi` | Memory limit for the Cloud Run Job container |
| `pipeline_schedule` | No | `0 */6 * * *` | Cloud Scheduler cron for the pipeline |
| `pipeline_schedule_time_zone` | No | `Asia/Kolkata` | Time zone for the pipeline schedule |
| `pipeline_schedule_paused` | No | `true` | Creates the scheduler job paused by default; set to `false` to activate recurring runs |
| `enable_pipeline_reporting` | No | `false` | Enables the reporting job, reporting scheduler, and Monitoring email notifications |
| `notification_email_recipient` | No | `""` | Recipient for failure alerts and per-run summary notifications |
| `reporting_job_name` | No | `tidingsiq-pipeline-report` | Cloud Run Job name for the reporting task |
| `reporting_scheduler_name` | No | `tidingsiq-pipeline-report-schedule` | Cloud Scheduler job name for the reporting task |
| `reporting_schedule` | No | `20 */6 * * *` | Cron for the reporting task, aligned 20 minutes after each pipeline window |
| `reporting_schedule_time_zone` | No | `Asia/Kolkata` | Time zone for the reporting scheduler |
| `enable_app_hosting` | No | `false` | Enables Artifact Registry and a Cloud Run service for the Streamlit app |
| `app_artifact_repository_id` | No | `tidingsiq-app` | Artifact Registry repository ID for the app image |
| `app_container_image` | No | derived | Full image URI for the Streamlit app container |
| `app_service_name` | No | `tidingsiq-app` | Cloud Run service name for the Streamlit app |
| `app_memory_limit` | No | `1Gi` | Memory limit for the Streamlit Cloud Run container |
| `app_allow_unauthenticated` | No | `true` | Grants public invoke access to the Streamlit Cloud Run service |
| `labels` | No | `{}` | Extra labels for supported resources |

## Provisioned Access Model

Pipeline service account:
- project role: `roles/bigquery.jobUser`
- dataset role on `bronze`, `bronze_staging`, `silver`, `gold`: `roles/bigquery.dataEditor`
- bucket role on Bronze archive bucket: `roles/storage.objectAdmin`

App service account:
- project role: `roles/bigquery.jobUser`
- dataset role on `gold`: `roles/bigquery.dataViewer`

This is the minimum working split for the planned architecture:
- the pipeline can create and update warehouse objects
- the app can run query jobs but only read the serving dataset

`bronze_staging` exists only to support the Bronze merge load path used by the current Bruin ingestion flow. It is not part of the logical Bronze/Silver/Gold contract exposed in the docs and app.

Terraform operator or CI identity still needs permission to create and manage the archive bucket and lifecycle rules.

If pipeline automation is enabled, Terraform also provisions:

- an Artifact Registry Docker repository for the pipeline image
- a Cloud Run Job that runs `bruin run pipeline/bruin/pipeline.yml`
- a scheduler service account with `roles/run.invoker` on the Cloud Run Job
- a Cloud Scheduler HTTP job that calls the Cloud Run Jobs API with OAuth

If pipeline reporting is enabled, Terraform also provisions:

- a reporting service account with BigQuery read access on `gold`
- a reporting Cloud Run Job that emits a daily warehouse summary log
- a second Cloud Scheduler job for the daily report cadence
- an email notification channel for Monitoring
- a Monitoring alert policy for pipeline failures
- a Monitoring alert policy for daily summary delivery

If app hosting is enabled, Terraform also provisions:

- an Artifact Registry Docker repository for the app image
- a Cloud Run service for the Streamlit frontend
- optional unauthenticated public invoke access on that Cloud Run service

Current applied automation state in this project:

- Artifact Registry repository is created
- Cloud Run Job is created
- Cloud Scheduler trigger is active on the configured cadence
- the pipeline image must already exist in Artifact Registry before apply
- the email notification channel sends a verification email to the configured recipient
- the reporting Cloud Run Job is created
- the daily reporting scheduler is created and active
- the Streamlit app Artifact Registry repository is created
- the hosted Streamlit Cloud Run service is created when `enable_app_hosting = true`
- in the current environment, app hosting can be kept disabled while the UI and security posture are still being finalized

## Notes

- This repository currently targets a single active environment.
- Logical dataset IDs are intentionally plain: `bronze`, `silver`, and `gold`.
- `bronze_staging` is a supporting operational dataset used by the Bronze load path.
- `delete_contents_on_destroy` is disabled to avoid accidental dataset deletion behavior.
- If stricter IAM boundaries are required later, move from dataset-wide editor access to more specific table or routine permissions after the first end-to-end slice is working.
- If you revisit a multi-environment setup later, see `future_multi_environment.md`.
- Current retention targets are Bronze 45 days with GCS archive, Silver 90 days, and Gold 180 days.
- The Bronze archive bucket is now part of Terraform. Export and cleanup operations are still run separately from the pipeline.
- Pipeline automation remains opt-in in code through `enable_pipeline_automation`, but it is already applied in the current project.
- Keep the scheduler paused during future rollouts until a manual `gcloud run jobs execute ... --wait` succeeds against the deployed image after any reset or image change.
- Pipeline reporting uses native Monitoring email notifications, so it does not require a third-party email API secret.
- App hosting is also opt-in in code through `enable_app_hosting`, and is now applied in the current project.
