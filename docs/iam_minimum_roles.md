# TidingsIQ Minimum IAM Roles

This document describes the minimum runtime IAM model for TidingsIQ using placeholders instead of live operator identities.

Replace these placeholders when applying the model to a real environment:

- `<GCP_PROJECT_ID>`
- `<PIPELINE_SERVICE_ACCOUNT_EMAIL>`
- `<REPORTING_SERVICE_ACCOUNT_EMAIL>`
- `<APP_SERVICE_ACCOUNT_EMAIL>`
- `<PIPELINE_SCHEDULER_SERVICE_ACCOUNT_EMAIL>`
- `<REPORTING_SCHEDULER_SERVICE_ACCOUNT_EMAIL>`
- `<ARCHIVE_SERVICE_ACCOUNT_EMAIL>`
- `<ARCHIVE_SCHEDULER_SERVICE_ACCOUNT_EMAIL>`
- `<SERVERLESS_SERVICE_AGENT_EMAIL>`
- `<PIPELINE_JOB_NAME>`
- `<REPORTING_JOB_NAME>`
- `<ARCHIVE_JOB_NAME>`
- `<PIPELINE_ARTIFACT_REPOSITORY>`
- `<APP_ARTIFACT_REPOSITORY>`
- `<ARCHIVE_BUCKET_URI>`

## Baseline Inventory

| Identity | Status | Purpose |
|---|---|---|
| `<PIPELINE_SERVICE_ACCOUNT_EMAIL>` | Required | Runs the Cloud Run Bruin pipeline job |
| `<REPORTING_SERVICE_ACCOUNT_EMAIL>` | Optional | Runs the reporting Cloud Run job when reporting is enabled |
| `<PIPELINE_SCHEDULER_SERVICE_ACCOUNT_EMAIL>` | Optional | Invokes the pipeline Cloud Run job from Cloud Scheduler |
| `<REPORTING_SCHEDULER_SERVICE_ACCOUNT_EMAIL>` | Optional | Invokes the reporting Cloud Run job from Cloud Scheduler |
| `<APP_SERVICE_ACCOUNT_EMAIL>` | Optional | Runs the Cloud Run app service when app hosting is enabled |
| `<ARCHIVE_SERVICE_ACCOUNT_EMAIL>` | Optional | Runs the Bronze archive Cloud Run job when archive automation is enabled |
| `<ARCHIVE_SCHEDULER_SERVICE_ACCOUNT_EMAIL>` | Optional | Invokes the archive Cloud Run job from Cloud Scheduler |
| `<SERVERLESS_SERVICE_AGENT_EMAIL>` | Platform-managed | Pulls container images from Artifact Registry for deployed Cloud Run runtimes |

## Exact Actions By Identity

### `<PIPELINE_SERVICE_ACCOUNT_EMAIL>`

Required actions:

- submit BigQuery jobs for the Bruin pipeline
- read and write the `bronze`, `bronze_staging`, `silver`, `gold`, and `gold_staging` datasets
- fetch upstream GDELT payloads over HTTP
- validate article URLs over outbound HTTP

Not required:

- Bronze archive bucket access
- reporting-only or app-only query access patterns

### `<REPORTING_SERVICE_ACCOUNT_EMAIL>`

Required actions when reporting is enabled:

- submit BigQuery query jobs
- read `gold.positive_news_feed`
- read `gold.pipeline_run_metrics`
- read `gold.INFORMATION_SCHEMA`

Not required:

- dataset writes
- GCS access
- access to Bronze, Silver, or staging datasets

### `<APP_SERVICE_ACCOUNT_EMAIL>`

Required actions when app hosting is enabled:

- submit BigQuery query jobs
- read `gold.positive_news_feed`
- read `gold.pipeline_run_metrics`
- read `gold.INFORMATION_SCHEMA`

Not required:

- Bronze, Silver, or staging access
- GCS access
- any runtime presence when `enable_app_hosting = false`

### `<PIPELINE_SCHEDULER_SERVICE_ACCOUNT_EMAIL>`

Required actions:

- invoke the pipeline Cloud Run job

Not required:

- BigQuery access
- Storage access
- reporting or archive job invocation

### `<REPORTING_SCHEDULER_SERVICE_ACCOUNT_EMAIL>`

Required actions:

- invoke the reporting Cloud Run job

Not required:

- BigQuery access
- Storage access
- pipeline or archive job invocation

### `<ARCHIVE_SERVICE_ACCOUNT_EMAIL>`

Required actions when archive automation is enabled:

- submit BigQuery jobs
- count, export, validate, and optionally delete rows from `bronze.gdelt_news_raw`
- write archive Parquet objects into the Bronze archive bucket
- overwrite existing archive objects for a cutoff prefix during reruns

Not required:

- access to `silver`, `gold`, `bronze_staging`, or `gold_staging`
- pipeline or reporting job invocation

### `<ARCHIVE_SCHEDULER_SERVICE_ACCOUNT_EMAIL>`

Required actions when archive automation is enabled:

- invoke the Bronze archive Cloud Run job

Not required:

- BigQuery access
- Storage access

### `<SERVERLESS_SERVICE_AGENT_EMAIL>`

Required actions:

- read the specific Artifact Registry repository used by each deployed Cloud Run job or service

Not required:

- project-wide Artifact Registry access
- any BigQuery or Storage access

## Final Minimum Role Set

| Identity | Scope | Role | Why it remains |
|---|---|---|---|
| `<PIPELINE_SERVICE_ACCOUNT_EMAIL>` | Project `<GCP_PROJECT_ID>` | `roles/bigquery.jobUser` | BigQuery job submission stays project-scoped |
| `<PIPELINE_SERVICE_ACCOUNT_EMAIL>` | Dataset `bronze` | `roles/bigquery.dataEditor` | Bronze merge writes |
| `<PIPELINE_SERVICE_ACCOUNT_EMAIL>` | Dataset `bronze_staging` | `roles/bigquery.dataEditor` | Operational merge and staging tables |
| `<PIPELINE_SERVICE_ACCOUNT_EMAIL>` | Dataset `silver` | `roles/bigquery.dataEditor` | Silver transforms |
| `<PIPELINE_SERVICE_ACCOUNT_EMAIL>` | Dataset `gold` | `roles/bigquery.dataEditor` | Gold transforms and metrics writes |
| `<PIPELINE_SERVICE_ACCOUNT_EMAIL>` | Dataset `gold_staging` | `roles/bigquery.dataEditor` | `dlt` merge staging for Gold Python assets |
| `<REPORTING_SERVICE_ACCOUNT_EMAIL>` | Project `<GCP_PROJECT_ID>` | `roles/bigquery.jobUser` | BigQuery query job submission |
| `<REPORTING_SERVICE_ACCOUNT_EMAIL>` | Dataset `gold` | `roles/bigquery.dataViewer` | Read-only reporting queries |
| `<APP_SERVICE_ACCOUNT_EMAIL>` | Project `<GCP_PROJECT_ID>` | `roles/bigquery.jobUser` | Only when app hosting is enabled |
| `<APP_SERVICE_ACCOUNT_EMAIL>` | Dataset `gold` | `roles/bigquery.dataViewer` | Only when app hosting is enabled |
| `<PIPELINE_SCHEDULER_SERVICE_ACCOUNT_EMAIL>` | Cloud Run job `<PIPELINE_JOB_NAME>` | `roles/run.invoker` | Pipeline scheduler invocation only |
| `<REPORTING_SCHEDULER_SERVICE_ACCOUNT_EMAIL>` | Cloud Run job `<REPORTING_JOB_NAME>` | `roles/run.invoker` | Reporting scheduler invocation only |
| `<ARCHIVE_SERVICE_ACCOUNT_EMAIL>` | Project `<GCP_PROJECT_ID>` | `roles/bigquery.jobUser` | Only when archive automation is enabled |
| `<ARCHIVE_SERVICE_ACCOUNT_EMAIL>` | Dataset `bronze` | `roles/bigquery.dataEditor` | Only when archive automation is enabled |
| `<ARCHIVE_SERVICE_ACCOUNT_EMAIL>` | Bucket `<ARCHIVE_BUCKET_URI>` | `roles/storage.objectAdmin` | Only when archive automation is enabled |
| `<ARCHIVE_SCHEDULER_SERVICE_ACCOUNT_EMAIL>` | Cloud Run job `<ARCHIVE_JOB_NAME>` | `roles/run.invoker` | Only when archive automation is enabled |
| `<SERVERLESS_SERVICE_AGENT_EMAIL>` | Artifact Registry repo `<PIPELINE_ARTIFACT_REPOSITORY>` | `roles/artifactregistry.reader` | Required for pipeline and reporting image pulls |
| `<SERVERLESS_SERVICE_AGENT_EMAIL>` | Artifact Registry repo `<APP_ARTIFACT_REPOSITORY>` | `roles/artifactregistry.reader` | Only when app hosting is enabled |

## Explicit Removals

These grants are intentionally excluded from the minimum model:

- any project-wide runtime grants beyond `roles/bigquery.jobUser`
- any Storage access for pipeline, reporting, app, or scheduler identities other than the dedicated archive runtime
- any BigQuery or Storage grants on scheduler identities
- any live app runtime IAM while `enable_app_hosting = false`
- reuse of the pipeline service account for Bronze archive execution

## Validation Expectations

After IAM changes:

- the pipeline job must still rebuild Bronze, Silver, Gold, and `gold.pipeline_run_metrics`
- the reporting job must still emit `DAILY_PIPELINE_SUMMARY`
- the archive worker must succeed in dry-run mode with the scheduler still disabled
- the pipeline service account must fail archive-bucket access after the split
- the reporting identity must fail write attempts against `gold`
