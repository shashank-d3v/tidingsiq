# TidingsIQ Terraform Foundation

This directory contains the first infrastructure slice for TidingsIQ. It provisions the minimum GCP resources needed to support the data pipeline and app:

- BigQuery datasets: `bronze`, `silver`, `gold`
- operational BigQuery datasets: `bronze_staging`, `gold_staging`
- Bronze archive bucket with lifecycle deletion after the retention window
- pipeline service account for Bruin workloads
- conditional app service account for Streamlit reads when app hosting is enabled
- minimum BigQuery and bucket IAM bindings for pipeline, reporting, app, and archive runtimes
- applied pipeline automation resources for Artifact Registry, Cloud Run Jobs, and Cloud Scheduler
- optional restricted-egress network path for the pipeline and Bronze archive Cloud Run jobs
- reporting resources for a daily Cloud Run summary job and Monitoring-based email notifications
- optional app hosting resources for Artifact Registry and a Cloud Run service
- optional app-edge resources for future hardening via an external HTTPS load balancer, Cloud Armor, logging metrics, dashboards, and an instance-pressure alert

## Prerequisites

- Terraform `>= 1.6`
- access to a target GCP project
- Google application default credentials or another supported Terraform authentication method
- required APIs already enabled in the target project, at minimum BigQuery and IAM

This module does not enable project APIs automatically. That is intentional to keep the infrastructure explicit and permission-conscious.

Cloud Storage must also be enabled in the target project because Bronze archival is now provisioned in Terraform.

If you enable the pipeline automation slice, the following APIs must also already be enabled:

- Artifact Registry API
- Compute Engine API
- Cloud Run Admin API
- Cloud Scheduler API
- Cloud Monitoring API
- Serverless VPC Access API

## Files

- `versions.tf`: Terraform and provider constraints
- `variables.tf`: input variables
- `main.tf`: provider, datasets, service accounts, and IAM
- `outputs.tf`: useful resource outputs
- `terraform.tfvars.example`: starter local variable file
- `future_multi_environment.md`: reference notes for a possible future multi-environment setup
- `automation.tf`: pipeline automation resources
- `restricted_egress.tf`: dedicated VPC, connector, firewall, NAT, and blocked-egress observability
- `reporting.tf`: daily reporting job and email notification resources
- `app_hosting.tf`: optional Streamlit app hosting resources
- `app_edge.tf`: optional external HTTPS load balancer, Cloud Armor, and app observability resources

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

Examples in this document use placeholders such as `<GCP_PROJECT_ID>`, `<REGION>`, `<PIPELINE_JOB_NAME>`, and `<IMAGE_URI>` for public-safe configuration.

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
| `enable_restricted_egress` | No | `false` | Enables the dedicated VPC egress path and attaches it to the pipeline and Bronze archive jobs |
| `restricted_egress_subnet_cidr` | No | `10.240.0.0/24` | CIDR range for the dedicated restricted-egress subnet |
| `restricted_egress_connector_cidr` | No | `10.240.1.0/28` | CIDR range for the Serverless VPC Access connector |
| `pipeline_artifact_repository_id` | No | `<PIPELINE_REPOSITORY_ID>` | Artifact Registry repository ID for the pipeline image |
| `pipeline_container_image` | Conditionally | `""` | Full image URI or digest for the shared pipeline image; required when pipeline, reporting, or archive automation is enabled |
| `pipeline_job_name` | No | `<PIPELINE_JOB_NAME>` | Cloud Run Job name |
| `pipeline_job_memory_limit` | No | `4Gi` | Memory limit for the Cloud Run Job container |
| `pipeline_schedule` | No | `0 */6 * * *` | Cloud Scheduler cron for the pipeline |
| `pipeline_schedule_time_zone` | No | `Asia/Kolkata` | Time zone for the pipeline schedule |
| `pipeline_schedule_paused` | No | `true` | Creates the scheduler job paused by default; set to `false` to activate recurring runs |
| `enable_pipeline_reporting` | No | `false` | Enables the reporting job, reporting scheduler, and Monitoring email notifications |
| `enable_bronze_archive_automation` | No | `false` | Enables the Bronze archive job, scheduler, and Monitoring alerts |
| `notification_email_recipient` | No | `""` | Recipient for failure alerts and per-run summary notifications |
| `reporting_job_name` | No | `<REPORTING_JOB_NAME>` | Cloud Run Job name for the reporting task |
| `reporting_scheduler_name` | No | `<REPORTING_SCHEDULER_NAME>` | Cloud Scheduler job name for the reporting task |
| `reporting_schedule` | No | `20 */6 * * *` | Cron for the reporting task, aligned 20 minutes after each pipeline window |
| `reporting_schedule_time_zone` | No | `Asia/Kolkata` | Time zone for the reporting scheduler |
| `bronze_archive_job_name` | No | `<ARCHIVE_JOB_NAME>` | Cloud Run Job name for Bronze archive automation |
| `bronze_archive_scheduler_name` | No | `<ARCHIVE_SCHEDULER_NAME>` | Cloud Scheduler job name for Bronze archive automation |
| `bronze_archive_schedule` | No | `15 3 * * *` | Daily cron for the Bronze archive job |
| `bronze_archive_schedule_time_zone` | No | `Asia/Kolkata` | Time zone for the Bronze archive scheduler |
| `bronze_archive_schedule_paused` | No | `true` | Creates the Bronze archive scheduler paused by default |
| `bronze_archive_dry_run` | No | `true` | Runs the Bronze archive worker in dry-run mode |
| `bronze_archive_delete_after_export` | No | `false` | Enables delete-after-export once reconciliation is trusted |
| `bronze_archive_max_delete_rows` | No | `20000` | Delete guardrail for the Bronze archive worker |
| `enable_app_hosting` | No | `false` | Enables Artifact Registry and a direct public Cloud Run service for the Streamlit app |
| `app_artifact_repository_id` | No | `tidingsiq-app` | Artifact Registry repository ID for the app image |
| `app_container_image` | No | derived | Full image URI for the Streamlit app container |
| `app_service_name` | No | `tidingsiq-app` | Cloud Run service name for the Streamlit app |
| `app_memory_limit` | No | `1Gi` | Memory limit for the Streamlit Cloud Run container |
| `app_allow_unauthenticated` | No | `true` | Grants public invoke access to the Streamlit Cloud Run service |
| `enable_app_edge` | No | `false` | Enables an optional future hardening layer with an external HTTPS load balancer, Cloud Armor, and app observability resources in front of the Streamlit app |
| `app_domain_name` | Conditionally | `""` | DNS hostname served by the external HTTPS load balancer; required when `enable_app_edge = true` |
| `app_rate_limit_count` | No | `120` | Per-IP Cloud Armor throttle threshold for the app |
| `app_rate_limit_interval_sec` | No | `60` | Cloud Armor throttle interval in seconds for the app |
| `app_rate_limit_preview` | No | `true` | Keeps the Cloud Armor throttle rule in preview mode for monitor-first rollout |
| `app_backend_log_sample_rate` | No | `1.0` | Logging sample rate for the app load balancer backend service |
| `labels` | No | `{}` | Extra labels for supported resources |

## Provisioned Access Model

Pipeline service account:
- project role: `roles/bigquery.jobUser`
- dataset role on `bronze`, `bronze_staging`, `silver`, `gold`, `gold_staging`: `roles/bigquery.dataEditor`

Reporting service account:
- project role: `roles/bigquery.jobUser`
- dataset role on `gold`: `roles/bigquery.dataViewer`

App service account when `enable_app_hosting = true`:
- project role: `roles/bigquery.jobUser`
- dataset role on `gold`: `roles/bigquery.dataViewer`

Archive service account when `enable_bronze_archive_automation = true`:
- project role: `roles/bigquery.jobUser`
- dataset role on `bronze`: `roles/bigquery.dataEditor`
- bucket role on Bronze archive bucket: `roles/storage.objectAdmin`

This is the minimum working split for the planned architecture:
- the pipeline can create and update warehouse objects
- reporting and the app can run query jobs but only read the serving dataset
- archive runs with its own Bronze-only identity instead of reusing the pipeline service account

`bronze_staging` and `gold_staging` exist only to support operational merge/staging load paths. They are not part of the logical Bronze/Silver/Gold contract exposed in the docs and app.

Terraform operator or CI identity still needs permission to create and manage the archive bucket and lifecycle rules.

If pipeline automation is enabled, Terraform also provisions:

- an Artifact Registry Docker repository for the pipeline image
- a Cloud Run Job that runs `bruin run pipeline/bruin/pipeline.yml`
- a scheduler service account with `roles/run.invoker` on the Cloud Run Job
- a Cloud Scheduler HTTP job that calls the Cloud Run Jobs API with OAuth

If restricted egress is enabled, Terraform also provisions:

- a dedicated VPC and subnet for controlled serverless egress
- a Serverless VPC Access connector in the automation region
- a Cloud Router and Cloud NAT path for public outbound traffic
- high-priority firewall deny rules for RFC1918, loopback, link-local, metadata, and CGNAT destinations
- firewall-rule logging for blocked traffic
- a log-based metric for blocked outbound attempts
- a Monitoring alert policy for blocked egress attempts when `notification_email_recipient` is configured
- Cloud Run VPC egress attachment for the main pipeline job and the Bronze archive job only

If pipeline reporting is enabled, Terraform also provisions:

- a reporting service account with BigQuery read access on `gold`
- a reporting Cloud Run Job that emits a daily warehouse summary log
- a second Cloud Scheduler job for the daily report cadence
- an email notification channel for Monitoring
- a Monitoring alert policy for pipeline failures
- a Monitoring alert policy for daily summary delivery

If Bronze archive automation is enabled, Terraform also provisions:

- a dedicated Bronze archive execution service account with Bronze-only BigQuery access plus archive-bucket object administration
- a dedicated Cloud Run Job that runs `python3 scripts/archive_bronze.py`
- a scheduler service account with `roles/run.invoker` on the Bronze archive job
- a Cloud Scheduler HTTP job for the archive cadence
- a log-based metric for repeated archive failures
- a log-based metric for delete-enabled backlog detection
- Monitoring alert policies for repeated failures and backlog accumulation

If app hosting is enabled, Terraform also provisions:

- an Artifact Registry Docker repository for the app image
- a Cloud Run service for the Streamlit frontend
- optional unauthenticated public invoke access on that Cloud Run service
- direct public serving on the Cloud Run `run.app` URL by default

If app edge is enabled, Terraform also provisions:

- a global external HTTPS load balancer in front of the app
- a serverless NEG targeting the Cloud Run service in the automation region
- a Google-managed certificate for the configured hostname
- an HTTP-to-HTTPS redirect path on the same global IP
- a Cloud Armor security policy with a preview-first per-IP throttle rule
- backend-service request logging at the configured sample rate
- logs-based metrics for app request volume and Cloud Armor preview and enforced throttle events
- a logs-based metric for BigQuery jobs attributed to the app service account
- a Monitoring dashboard covering load balancer traffic, Cloud Armor signals, Cloud Run pressure, and BigQuery query volume and billed bytes
- a Monitoring alert policy for sustained Cloud Run instance pressure

Implementation notes:

- the shared pipeline image must already exist and `pipeline_container_image` must be set explicitly before apply when pipeline automation, reporting, or archive automation is enabled
- when `enable_restricted_egress = true`, keep the pipeline and Bronze archive schedulers paused until a manual Cloud Run smoke test confirms that public article validation still succeeds and blocked firewall logs match only private, internal, or metadata destinations
- the email notification channel sends a verification email to the configured recipient
- the Bronze archive job path is available in code and remains feature-gated behind `enable_bronze_archive_automation`
- app hosting can be kept disabled while the UI and security posture are still being finalized, and when disabled the app service account plus its BigQuery IAM are not provisioned
- when `enable_app_edge = true`, the Cloud Run service ingress is restricted to Google Cloud load balancers and internal traffic so internet requests must traverse the external HTTPS load balancer
- the default portfolio-app posture can stay public and unauthenticated on the direct Cloud Run URL, with `app_max_instance_count` kept conservative

## Notes

- This repository currently targets a single active environment.
- Logical dataset IDs are intentionally plain: `bronze`, `silver`, and `gold`.
- `bronze_staging` and `gold_staging` are supporting operational datasets used by the current merge load paths.
- `delete_contents_on_destroy` is disabled to avoid accidental dataset deletion behavior.
- If stricter IAM boundaries are required later, move from dataset-wide editor access to more specific table or routine permissions after the first end-to-end slice is working.
- If you revisit a multi-environment setup later, see `future_multi_environment.md`.
- Current retention targets are Bronze 45 days with GCS archive, Silver 90 days, and Gold 180 days.
- The Bronze archive bucket is part of Terraform, and the scheduled Bronze archive job reuses the pipeline image but runs under a dedicated archive service account.
- During rollout, export-only archive mode should be treated as transitional rather than steady-state because repeated export-only executions can re-export the same old Bronze rows into newer cutoff-date prefixes until delete succeeds or the worker gains a persisted archival boundary.
- Pipeline automation remains opt-in in code through `enable_pipeline_automation`.
- Restricted egress remains opt-in in code through `enable_restricted_egress`.
- Keep the scheduler paused during future rollouts until a manual `gcloud run jobs execute ... --wait` succeeds against the deployed image after any reset or image change.
- Pipeline reporting uses native Monitoring email notifications, so it does not require a third-party email API secret.
- App hosting is also opt-in in code through `enable_app_hosting`.
- App edge is also opt-in in code through `enable_app_edge`.
