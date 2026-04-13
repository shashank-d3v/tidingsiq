# TidingsIQ Operations Runbook

This runbook contains the current manual commands for resetting, validating, and debugging the TidingsIQ cloud pipeline in the active project.

Current project and region assumptions:

- project: `tidingsiq-dev`
- region: `asia-south1`
- pipeline job: `tidingsiq-pipeline`
- reporting job: `tidingsiq-pipeline-report`
- Bronze archive job: `tidingsiq-bronze-archive`
- pipeline scheduler: `tidingsiq-pipeline-schedule`
- reporting scheduler: `tidingsiq-pipeline-report-schedule`
- Bronze archive scheduler: `tidingsiq-bronze-archive-schedule`

## Warehouse Reset

Warehouse-only reset. This preserves:

- `gold.positive_feed_guardrail_terms`
- datasets and infrastructure
- Bronze archive bucket contents

Run the helper:

```bash
cd "/Volumes/SWE/repos/DE 2026/tidingsiq"
scripts/reset_warehouse.sh tidingsiq-dev
```

Verify empty state:

```bash
bq query --use_legacy_sql=false "select count(*) as bronze_rows from \`tidingsiq-dev.bronze.gdelt_news_raw\`"
bq query --use_legacy_sql=false "select count(*) as silver_rows from \`tidingsiq-dev.silver.gdelt_news_refined\`"
bq query --use_legacy_sql=false "select count(*) as gold_rows from \`tidingsiq-dev.gold.positive_news_feed\`"
bq query --use_legacy_sql=false "select count(*) as metric_rows from \`tidingsiq-dev.gold.pipeline_run_metrics\`"
bq query --use_legacy_sql=false "select count(*) as guardrail_term_rows from \`tidingsiq-dev.gold.positive_feed_guardrail_terms\`"
```

## Manual Pipeline Smoke Test

Run the deployed Cloud Run Job manually:

```bash
gcloud run jobs execute tidingsiq-pipeline \
  --region=asia-south1 \
  --project=tidingsiq-dev \
  --wait
```

Inspect the latest execution:

```bash
gcloud run jobs executions list \
  --job=tidingsiq-pipeline \
  --region=asia-south1 \
  --project=tidingsiq-dev \
  --limit=5
```

Inspect logs:

```bash
gcloud logging read \
  'resource.type="cloud_run_job" AND resource.labels.job_name="tidingsiq-pipeline"' \
  --project=tidingsiq-dev \
  --limit=100 \
  --format='value(textPayload)'
```

Verify row counts:

```bash
bq query --use_legacy_sql=false "select count(*) as bronze_rows from \`tidingsiq-dev.bronze.gdelt_news_raw\`"
bq query --use_legacy_sql=false "select count(*) as silver_rows, countif(is_duplicate = false) as silver_canonical_rows from \`tidingsiq-dev.silver.gdelt_news_refined\`"
bq query --use_legacy_sql=false "select count(*) as gold_rows, countif(is_positive_feed_eligible) as eligible_rows from \`tidingsiq-dev.gold.positive_news_feed\`"
bq query --use_legacy_sql=false "select audit_run_at, bronze_row_count, silver_row_count, silver_canonical_row_count, gold_row_count from \`tidingsiq-dev.gold.pipeline_run_metrics\` order by audit_run_at desc limit 5"
```

## Scheduler Operations

Describe the current pipeline scheduler:

```bash
gcloud scheduler jobs describe tidingsiq-pipeline-schedule \
  --location=asia-south1 \
  --project=tidingsiq-dev
```

Pause:

```bash
gcloud scheduler jobs pause tidingsiq-pipeline-schedule \
  --location=asia-south1 \
  --project=tidingsiq-dev
```

Resume:

```bash
gcloud scheduler jobs resume tidingsiq-pipeline-schedule \
  --location=asia-south1 \
  --project=tidingsiq-dev
```

Trigger immediately:

```bash
gcloud scheduler jobs run tidingsiq-pipeline-schedule \
  --location=asia-south1 \
  --project=tidingsiq-dev
```

Describe the daily reporting scheduler:

```bash
gcloud scheduler jobs describe tidingsiq-pipeline-report-schedule \
  --location=asia-south1 \
  --project=tidingsiq-dev
```

Describe the Bronze archive scheduler:

```bash
gcloud scheduler jobs describe tidingsiq-bronze-archive-schedule \
  --location=asia-south1 \
  --project=tidingsiq-dev
```

## Bronze Archive Operations

Current rollout caveat:

- Export-only Bronze archive runs are not yet idempotent across repeated daily executions. If `bronze_archive_dry_run = false` and `bronze_archive_delete_after_export = false`, or if a delete-enabled run exports successfully but fails before delete completes, the next run can export the same old Bronze rows again into a new `cutoff_date=...` path.
- Keep export-only mode short-lived during rollout, review the emitted `BRONZE_ARCHIVE_SUMMARY` logs closely, and do not treat repeated export-only schedules as a steady-state retention strategy until the archive path gains a persisted high-water mark, non-overlapping export windows, or equivalent reconciliation.

Run the deployed Bronze archive job manually in dry-run mode:

```bash
gcloud run jobs execute tidingsiq-bronze-archive \
  --region=asia-south1 \
  --project=tidingsiq-dev \
  --wait
```

Inspect recent archive executions:

```bash
gcloud run jobs executions list \
  --job=tidingsiq-bronze-archive \
  --region=asia-south1 \
  --project=tidingsiq-dev \
  --limit=5
```

Inspect archive summary logs:

```bash
gcloud logging read \
  'resource.type="cloud_run_job" AND resource.labels.job_name="tidingsiq-bronze-archive" AND textPayload:"BRONZE_ARCHIVE_SUMMARY"' \
  --project=tidingsiq-dev \
  --limit=20 \
  --format='value(textPayload)'
```

Pause the Bronze archive scheduler during rollout:

```bash
gcloud scheduler jobs pause tidingsiq-bronze-archive-schedule \
  --location=asia-south1 \
  --project=tidingsiq-dev
```

Resume the Bronze archive scheduler:

```bash
gcloud scheduler jobs resume tidingsiq-bronze-archive-schedule \
  --location=asia-south1 \
  --project=tidingsiq-dev
```

Trigger the Bronze archive scheduler immediately:

```bash
gcloud scheduler jobs run tidingsiq-bronze-archive-schedule \
  --location=asia-south1 \
  --project=tidingsiq-dev
```

Check the current eligible Bronze backlog against the archive cutoff:

```bash
bq query --use_legacy_sql=false "select count(*) as eligible_rows, min(ingested_at) as oldest_eligible_ingested_at from \`tidingsiq-dev.bronze.gdelt_news_raw\` where ingested_at < timestamp_sub(timestamp_trunc(current_timestamp(), day), interval 45 day)"
```

Validate exported parquet row count for a specific cutoff date:

```bash
bq query --use_legacy_sql=false "create or replace external table \`tidingsiq-dev.bronze_staging.archive_validation\` options(format='PARQUET', uris=['gs://tidingsiq-dev-tidingsiq-bronze-archive/automated/bronze_gdelt_news_raw/cutoff_date=2026-02-26/*.parquet']); select count(*) as exported_rows from \`tidingsiq-dev.bronze_staging.archive_validation\`"
```

## Image and Deployment Debug

Build and push the pipeline image:

```bash
cd "/Volumes/SWE/repos/DE 2026/tidingsiq"
docker buildx build \
  --platform linux/amd64 \
  -f pipeline/bruin/Dockerfile \
  -t asia-south1-docker.pkg.dev/tidingsiq-dev/tidingsiq-pipeline/tidingsiq-bruin:latest \
  --push .
```

Update the Cloud Run pipeline job to the pushed image:

```bash
gcloud run jobs update tidingsiq-pipeline \
  --region=asia-south1 \
  --project=tidingsiq-dev \
  --image=asia-south1-docker.pkg.dev/tidingsiq-dev/tidingsiq-pipeline/tidingsiq-bruin:latest
```

Update the reporting job to the same image:

```bash
gcloud run jobs update tidingsiq-pipeline-report \
  --region=asia-south1 \
  --project=tidingsiq-dev \
  --image=asia-south1-docker.pkg.dev/tidingsiq-dev/tidingsiq-pipeline/tidingsiq-bruin:latest
```

Update the Bronze archive job to the same image:

```bash
gcloud run jobs update tidingsiq-bronze-archive \
  --region=asia-south1 \
  --project=tidingsiq-dev \
  --image=asia-south1-docker.pkg.dev/tidingsiq-dev/tidingsiq-pipeline/tidingsiq-bruin:latest
```

Run the reporting job manually:

```bash
gcloud run jobs execute tidingsiq-pipeline-report \
  --region=asia-south1 \
  --project=tidingsiq-dev \
  --wait
```

Inspect reporting logs:

```bash
gcloud logging read \
  'resource.type="cloud_run_job" AND resource.labels.job_name="tidingsiq-pipeline-report"' \
  --project=tidingsiq-dev \
  --limit=50 \
  --format='value(textPayload)'
```

## Warehouse Health Checks

Gold eligible and ineligible split:

```bash
bq query --use_legacy_sql=false "select count(*) as gold_rows, countif(is_positive_feed_eligible) as eligible_rows, countif(not is_positive_feed_eligible) as ineligible_rows from \`tidingsiq-dev.gold.positive_news_feed\`"
```

Gold exclusion breakdown:

```bash
bq query --use_legacy_sql=false "select coalesce(exclusion_reason, 'eligible') as bucket, count(*) as row_count from \`tidingsiq-dev.gold.positive_news_feed\` group by 1 order by row_count desc"
```

Most recent metrics snapshot:

```bash
bq query --use_legacy_sql=false "select * from \`tidingsiq-dev.gold.pipeline_run_metrics\` order by audit_run_at desc limit 1"
```

Latest summary log:

```bash
gcloud logging read \
  'resource.type="cloud_run_job" AND resource.labels.job_name="tidingsiq-pipeline-report" AND textPayload:"DAILY_PIPELINE_SUMMARY"' \
  --project=tidingsiq-dev \
  --limit=5 \
  --format='value(textPayload)'
```

## Terraform Apply Path

From the Terraform directory:

```bash
cd "/Volumes/SWE/repos/DE 2026/tidingsiq/infra/terraform"
terraform init
terraform fmt -recursive
terraform validate
terraform plan
terraform apply
```

If the scheduler should stay paused during a rollout, keep `pipeline_schedule_paused = true` in the local `terraform.tfvars` until the manual smoke test is clean.
For archive rollout, keep `bronze_archive_schedule_paused = true`, `bronze_archive_dry_run = true`, and `bronze_archive_delete_after_export = false` until the dry-run and export-only checks are clean.
Do not leave the archive scheduler running indefinitely in export-only mode as the long-term default, because repeated export-only executions can duplicate already archived Bronze rows under newer cutoff-date prefixes.
