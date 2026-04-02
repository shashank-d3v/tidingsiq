# TidingsIQ Terraform Foundation

This directory contains the first infrastructure slice for TidingsIQ. It provisions the minimum GCP resources needed to support the data pipeline and app:

- BigQuery datasets: `bronze`, `silver`, `gold`
- Bronze archive bucket with lifecycle deletion after the retention window
- pipeline service account for Bruin workloads
- app service account for Streamlit reads
- minimum BigQuery IAM bindings for both identities
- optional pipeline automation resources for Artifact Registry, Cloud Run Jobs, and Cloud Scheduler

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

## Files

- `versions.tf`: Terraform and provider constraints
- `variables.tf`: input variables
- `main.tf`: provider, datasets, service accounts, and IAM
- `outputs.tf`: useful resource outputs
- `terraform.tfvars.example`: starter local variable file
- `future_multi_environment.md`: reference notes for a possible future multi-environment setup
- `automation.tf`: optional pipeline automation resources

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
| `pipeline_schedule` | No | `0 */6 * * *` | Cloud Scheduler cron for the pipeline |
| `pipeline_schedule_paused` | No | `true` | Creates the scheduler job paused by default |
| `labels` | No | `{}` | Extra labels for supported resources |

## Provisioned Access Model

Pipeline service account:
- project role: `roles/bigquery.jobUser`
- dataset role on `bronze`, `silver`, `gold`: `roles/bigquery.dataEditor`
- bucket role on Bronze archive bucket: `roles/storage.objectAdmin`

App service account:
- project role: `roles/bigquery.jobUser`
- dataset role on `gold`: `roles/bigquery.dataViewer`

This is the minimum working split for the planned architecture:
- the pipeline can create and update warehouse objects
- the app can run query jobs but only read the serving dataset

Terraform operator or CI identity still needs permission to create and manage the archive bucket and lifecycle rules.

If pipeline automation is enabled, Terraform also provisions:

- an Artifact Registry Docker repository for the pipeline image
- a Cloud Run Job that runs `bruin run pipeline/bruin/pipeline.yml`
- a scheduler service account with `roles/run.invoker` on the Cloud Run Job
- a Cloud Scheduler HTTP job that calls the Cloud Run Jobs API with OAuth

## Notes

- This repository currently targets a single active environment.
- Dataset IDs are intentionally plain: `bronze`, `silver`, and `gold`.
- `delete_contents_on_destroy` is disabled to avoid accidental dataset deletion behavior.
- If stricter IAM boundaries are required later, move from dataset-wide editor access to more specific table or routine permissions after the first end-to-end slice is working.
- If you revisit a multi-environment setup later, see `future_multi_environment.md`.
- Current retention targets are Bronze 45 days with GCS archive, Silver 90 days, and Gold 180 days.
- The Bronze archive bucket is now part of Terraform. Export and cleanup operations are still run separately from the pipeline.
- Pipeline automation resources are disabled by default so the current applied foundation is not changed until you are ready to push an image and enable them explicitly.
