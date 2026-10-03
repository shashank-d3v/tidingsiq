# TidingsIQ Terraform Foundation

This directory contains the infrastructure modules for TidingsIQ. It provisions the minimum GCP resources needed to support the data pipeline and app:

- BigQuery datasets: `bronze`, `silver`, `gold`
- operational BigQuery datasets: `bronze_staging`, `gold_staging`
- Bronze archive bucket with lifecycle deletion after the retention window
- pipeline service account for Bruin workloads
- static reader/publisher identities for public serving; retained legacy app identity when hosting is enabled
- scoped BigQuery and bucket IAM bindings for pipeline, reporting, publisher, reader, and archive runtimes
- applied pipeline automation resources for Artifact Registry, Cloud Run Jobs, and Cloud Scheduler
- optional restricted-egress network path for future static outbound IP or private VPC-only dependencies
- reporting resources for a daily Cloud Run summary job and Monitoring-based email notifications
- app hosting resources for Artifact Registry and a Cloud Run service
- static feed bucket, read-only frontend mount, daily publisher, schedule and failure alert
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
- Cloud Run Admin API
- Cloud Scheduler API
- Cloud Monitoring API

If `enable_restricted_egress = true` or `enable_app_edge = true`, the relevant networking APIs must also be enabled. Restricted egress requires:

- Compute Engine API
- Serverless VPC Access API

## Files

- `versions.tf`: Terraform and provider constraints
- `variables.tf`: input variables
- `main.tf`: provider, datasets, service accounts, and IAM
- `outputs.tf`: useful resource outputs
- `terraform.tfvars.example`: starter local variable file
- `automation.tf`: pipeline automation resources
- `restricted_egress.tf`: dedicated VPC, connector, firewall, NAT, and blocked-egress observability
- `reporting.tf`: daily reporting job and email notification resources
- `app_hosting.tf`: frontend hosting, with static/legacy mode selected by inputs
- `static_dashboard.tf`: private feed bucket, static identities, publisher, schedule and alert
- `app_edge.tf`: optional external HTTPS load balancer, Cloud Armor, and app observability resources

## Current Network Posture

The active dev deployment uses the low-cost Cloud Run default internet egress posture:

- `enable_restricted_egress = false`
- no Serverless VPC Access connector
- no dedicated restricted-egress VPC, subnet, router, or Cloud NAT
- no static outbound IP
- pipeline and Bronze archive Cloud Run Jobs have no `vpc_access` block

This is intentional. The May 2026 billing review showed the restricted-egress path was the dominant cost driver, while Cloud Run execution was almost fully covered by savings. The restricted-egress resources were removed from the live `tidingsiq-dev` deployment on 2026-05-04 with Terraform. Re-enable this slice only when an external dependency requires IP allowlisting, a private VPC-only dependency is introduced, or an audit requirement explicitly needs connector-backed egress.

With restricted egress disabled, GDELT/public URL fetches and Google APIs such as BigQuery continue over normal Cloud Run outbound networking. External sites will not see a stable source IP.

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
| `enable_restricted_egress` | No | `false` | Enables the optional dedicated VPC egress path and attaches it to the pipeline and Bronze archive jobs; keep `false` for the low-cost dev posture |
| `restricted_egress_subnet_cidr` | No | `10.240.0.0/24` | CIDR range for the optional restricted-egress subnet |
| `restricted_egress_connector_cidr` | No | `10.240.1.0/28` | CIDR range for the optional Serverless VPC Access connector |
| `pipeline_artifact_repository_id` | No | `<PIPELINE_REPOSITORY_ID>` | Artifact Registry repository ID for the pipeline image |
| `pipeline_container_image` | Conditionally | `""` | Full image URI or digest for the shared pipeline image; required when pipeline, reporting, or archive automation is enabled |
| `pipeline_job_name` | No | `<PIPELINE_JOB_NAME>` | Cloud Run Job name |
| `pipeline_job_timeout` | No | `3600s` | Per-task timeout for the pipeline Cloud Run Job |
| `pipeline_job_max_retries` | No | `0` | Cloud Run Job retry count; dev keeps this at `0` to avoid duplicate paid runs after data-quality failures |
| `pipeline_job_task_count` | No | `1` | Task count for the pipeline Cloud Run Job execution |
| `pipeline_job_parallelism` | No | `1` | Parallelism for the pipeline Cloud Run Job execution |
| `pipeline_job_memory_limit` | No | `4Gi` | Memory limit for the Cloud Run Job container |
| `pipeline_gdelt_max_files` | No | `4` | GDELT file cap injected into the Cloud Run Job environment |
| `pipeline_gdelt_publication_lag_minutes` | No | `60` | Rolling-window lag used only when the GDELT manifest cannot be validated |
| `pipeline_gdelt_download_max_attempts` | No | `4` | Per-request attempt limit for manifest and archive downloads |
| `pipeline_gdelt_download_backoff_seconds` | No | `5,15,30` | Retry delays before jitter and any capped `Retry-After` override |
| `pipeline_gdelt_recent_file_hours` | No | `24` | Age window in which archive HTTP 400/404 responses are treated as transient |
| `pipeline_schedule` | No | `0 6 * * *` | Cloud Scheduler cron for the pipeline |
| `pipeline_schedule_time_zone` | No | `Asia/Kolkata` | Time zone for the pipeline schedule |
| `pipeline_schedule_paused` | No | `true` | Creates the scheduler job paused by default; set to `false` to activate recurring runs |
| `enable_pipeline_reporting` | No | `false` | Enables the reporting job, reporting scheduler, and Monitoring email notifications |
| `enable_bronze_archive_automation` | No | `false` | Enables the Bronze archive job, scheduler, and Monitoring alerts |
| `notification_email_recipient` | No | `""` | Recipient for failure alerts and per-run summary notifications |
| `reporting_job_name` | No | `<REPORTING_JOB_NAME>` | Cloud Run Job name for the reporting task |
| `reporting_scheduler_name` | No | `<REPORTING_SCHEDULER_NAME>` | Cloud Scheduler job name for the reporting task |
| `reporting_schedule` | No | `20 6 * * *` | Cron for the reporting task, aligned 20 minutes after the daily pipeline window |
| `reporting_schedule_time_zone` | No | `Asia/Kolkata` | Time zone for the reporting scheduler |
| `reporting_schedule_paused` | No | `false` | Keeps the reporting scheduler paused during controlled deployments |
| `bronze_archive_job_name` | No | `<ARCHIVE_JOB_NAME>` | Cloud Run Job name for Bronze archive automation |
| `bronze_archive_container_image` | No | `""` | Optional pinned archive-worker image; defaults to the pipeline image when empty |
| `bronze_archive_scheduler_name` | No | `<ARCHIVE_SCHEDULER_NAME>` | Cloud Scheduler job name for Bronze archive automation |
| `bronze_archive_schedule` | No | `15 3 * * *` | Daily cron for the Bronze archive job |
| `bronze_archive_schedule_time_zone` | No | `Asia/Kolkata` | Time zone for the Bronze archive scheduler |
| `bronze_archive_schedule_paused` | No | `true` | Creates the Bronze archive scheduler paused by default |
| `bronze_archive_dry_run` | No | `true` | Runs the Bronze archive worker in dry-run mode |
| `bronze_archive_delete_after_export` | No | `false` | Enables capped pruning outside the 90-day serving horizon after verified archival |
| `bronze_archive_memory_limit` | No | `512Mi` | Memory for server-side archive orchestration |
| `bronze_archive_max_delete_rows` | No | `20000` | Delete guardrail for the Bronze archive worker |
| `enable_app_hosting` | No | `false` | Enables Artifact Registry and a direct public Cloud Run service for the frontend |
| `app_artifact_repository_id` | No | `tidingsiq-app` | Artifact Registry repository ID for the app image |
| `app_container_image` | No | derived | Pinned image URI for the frontend container |
| `app_service_name` | No | `tidingsiq-app` | Cloud Run service name for the frontend |
| `app_gold_table` | No | derived | Legacy Streamlit Gold table; not injected in static mode |
| `app_memory_limit` | No | `1Gi` | Legacy frontend memory; static mode uses 512Mi |
| `app_min_instance_count` | No | `0` | Minimum frontend revision instances; keep `0` for scale-to-zero cost control |
| `app_max_instance_count` | No | `2` | Maximum frontend revision instances |
| `app_allow_unauthenticated` | No | `true` | Grants public invoke access to the frontend Cloud Run service |
| `enable_static_dashboard` | No | `false` | Enables private feed, static identities/publisher and nginx hosting mode; requires app hosting and reporting |
| `static_publisher_image` | When static enabled | `""` | Pinned publisher image digest |
| `static_publish_schedule_paused` | No | `true` | Keep the new daily 06:30 IST publisher paused until a verified canary |
| `enable_app_edge` | No | `false` | Enables an optional future hardening layer with an external HTTPS load balancer, Cloud Armor, and app observability resources in front of the frontend |
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

Legacy app service account, still provisioned when `enable_app_hosting = true`:
- project role: `roles/bigquery.jobUser`
- dataset role on `gold`: `roles/bigquery.dataViewer`

Static reader when `enable_static_dashboard = true`:
- bucket role on static feed bucket: `roles/storage.objectViewer`
- active frontend identity, read-only GCS volume, no warehouse query path

Static publisher when `enable_static_dashboard = true`:
- project role: `roles/bigquery.jobUser`
- dataset role on `gold`: `roles/bigquery.dataViewer`
- bucket role on static feed bucket: `roles/storage.objectUser`
- the reporting scheduler identity also receives `roles/run.invoker` on this job

The legacy app identity is not selected by the static frontend. Its retained IAM
is not removed by enabling static mode; review that separately before cleanup.

Archive service account when `enable_bronze_archive_automation = true`:
- project role: `roles/bigquery.jobUser`
- dataset role on `bronze`: `roles/bigquery.dataEditor`
- bucket role on Bronze archive bucket: `roles/storage.objectAdmin`

This is the provisioned split for the current architecture:
- the pipeline can create and update warehouse objects
- reporting and publishing can submit queries but only read Gold
- the static frontend can read the published files without querying BigQuery
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

This slice is not part of the active low-cost dev deployment. Enabling it adds always-on networking resources and should be treated as a deliberate static-outbound-IP or private-network decision, not the default pipeline posture.

If pipeline reporting is enabled, Terraform also provisions:

- a reporting service account with BigQuery read access on `gold`
- a reporting Cloud Run Job that emits a daily warehouse summary log
- a second Cloud Scheduler job for the daily report cadence
- an email notification channel for Monitoring
- a Monitoring alert policy for pipeline failures
- a Monitoring alert policy for daily summary delivery
- a `gdelt_incomplete_source_windows` log-based metric for partial or empty live windows
- an enabled `TidingsIQ GDELT Incomplete Source Window` policy that alerts on the first event, rate-limits notifications to once per hour, and auto-closes after 24 hours

The incomplete-window filter explicitly requires `mode=live`, so operator-driven
backfills do not create asynchronous alerts. Terraform outputs expose both the metric
and alert-policy names for deployment verification.

If Bronze archive automation is enabled, Terraform also provisions:

- a dedicated Bronze archive execution service account with Bronze-only BigQuery access plus archive-bucket object administration
- a dedicated Cloud Run Job that runs `python3 scripts/archive_bronze_incremental.py`
- a scheduler service account with `roles/run.invoker` on the Bronze archive job
- a Cloud Scheduler HTTP job for the archive cadence
- a log-based metric for repeated archive failures
- a log-based metric for delete-enabled backlog detection
- Monitoring alert policies for repeated failures and backlog accumulation

If app hosting is enabled, Terraform also provisions:

- an Artifact Registry Docker repository for the app image
- a Cloud Run service using the selected frontend image
- static mode selects the reader identity and read-only GCS volume, with no legacy BigQuery environment variables
- optional unauthenticated public invoke access on that Cloud Run service
- direct public serving on the Cloud Run `run.app` URL by default

If static mode is enabled, Terraform also provisions:

- a private, versioned static-feed bucket with public access prevention
- lifecycle deletion of private audits after 45 days and archived versions after seven newer versions
- live hashed feed files retained without age expiry; storage grows until a separate
  cleanup safely removes unreferenced editions
- separate reader/publisher service accounts and scoped IAM
- pipeline-job-scoped read-only execution access for the publisher success gate
- a daily 06:30 IST publisher job/schedule (paused by default)
- a publisher failure alert using the configured notification channel

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
- keep `enable_restricted_egress = false` unless static outbound IP, third-party IP allowlisting, or private VPC access is required
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
- A future second environment must use separate variables, resource names where needed, and separate Terraform state/backend prefixes. The current module is single-environment.
- Bronze exports after 45 days and prunes verified rows beyond 90 days; Silver has a 90-day cutoff. Gold has a 180-day model cutoff but its available history is constrained by Silver.
- The Bronze archive bucket is part of Terraform, and the scheduled Bronze archive job reuses the pipeline image but runs under a dedicated archive service account.
- The active archive worker persists a GCS checkpoint and immutable manifests. Repeated completed windows are no-ops. Optional pruning retains 90 days and enforces the deletion cap; see the [incident record](../../docs/history/incident_20260928.md).
- Pipeline automation remains opt-in in code through `enable_pipeline_automation`.
- Restricted egress remains opt-in in code through `enable_restricted_egress` and is intentionally disabled in the active dev deployment for cost control.
- Keep the scheduler paused during future rollouts until a manual `gcloud run jobs execute ... --wait` succeeds against the deployed image after any reset or image change.
- Pipeline reporting uses native Monitoring email notifications, so it does not require a third-party email API secret.
- App hosting is also opt-in in code through `enable_app_hosting`.
- App edge is also opt-in in code through `enable_app_edge`.

## Static Deployment and Emergency Scaling

Use the [deployment guide](../../docs/deployment_plan.md) for the isolated build
contexts and first publisher canary. Update local image digests after a release.
Service-level `scaling` is ignored by the app resource's lifecycle so a manual
emergency stop survives Terraform operations. Explicitly inspect and resume
service-level scaling only when the intended static revision and data are ready.

Defaults above are module defaults, not live values. On 2 October 2026, all four
schedules were enabled: pipeline 06:00, report 06:20, publisher 06:30, archive
03:15/15:15 in Asia/Kolkata. The active app used static mode, request-based billing,
min=0 and max=2. No apply was performed during that documentation verification.
