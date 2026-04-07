# TidingsIQ Operations Runbook

This runbook contains the current manual commands for resetting, validating, and debugging the TidingsIQ cloud pipeline in the active project.

Current project and region assumptions:

- project: `tidingsiq-dev`
- region: `asia-south1`
- pipeline job: `tidingsiq-pipeline`
- reporting job: `tidingsiq-pipeline-report`
- pipeline scheduler: `tidingsiq-pipeline-schedule`
- reporting scheduler: `tidingsiq-pipeline-report-schedule`

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
