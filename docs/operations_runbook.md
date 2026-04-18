# TidingsIQ Operations Runbook

This runbook contains parameterized example commands for resetting, validating, and debugging a TidingsIQ cloud deployment without exposing any specific live environment.

Replace the placeholders in each command before use:

- `<GCP_PROJECT_ID>`
- `<REGION>`
- `<PIPELINE_JOB_NAME>`
- `<REPORTING_JOB_NAME>`
- `<ARCHIVE_JOB_NAME>`
- `<PIPELINE_SCHEDULER_NAME>`
- `<REPORTING_SCHEDULER_NAME>`
- `<ARCHIVE_SCHEDULER_NAME>`
- `<PIPELINE_IMAGE_URI>`
- `<ARCHIVE_BUCKET_URI>`
- `<ARCHIVE_CUTOFF_DATE>`
- `<ENVIRONMENT>`
- `<RESTRICTED_EGRESS_METRIC_NAME>`
- `<APP_SERVICE_NAME>`
- `<APP_DOMAIN_NAME>`
- `<APP_BACKEND_SERVICE_NAME>`
- `<APP_HTTPS_FORWARDING_RULE_NAME>`
- `<APP_HTTP_FORWARDING_RULE_NAME>`
- `<APP_CLOUD_ARMOR_POLICY_NAME>`

Operational dataset assumptions:

- `bronze_staging` supports Bronze merge and archive validation paths
- `gold_staging` supports `dlt` merge loads for Gold Python assets such as `gold.url_validation_results`

## Warehouse Reset

Warehouse-only reset. This preserves:

- `gold.positive_feed_guardrail_terms`
- datasets and infrastructure
- Bronze archive bucket contents

Run the helper:

```bash
cd "/Volumes/SWE/repos/DE 2026/tidingsiq"
scripts/reset_warehouse.sh <GCP_PROJECT_ID>
```

Verify empty state:

```bash
bq query --use_legacy_sql=false "select count(*) as bronze_rows from \`<GCP_PROJECT_ID>.bronze.gdelt_news_raw\`"
bq query --use_legacy_sql=false "select count(*) as silver_rows from \`<GCP_PROJECT_ID>.silver.gdelt_news_refined\`"
bq query --use_legacy_sql=false "select count(*) as gold_rows from \`<GCP_PROJECT_ID>.gold.positive_news_feed\`"
bq query --use_legacy_sql=false "select count(*) as metric_rows from \`<GCP_PROJECT_ID>.gold.pipeline_run_metrics\`"
bq query --use_legacy_sql=false "select count(*) as guardrail_term_rows from \`<GCP_PROJECT_ID>.gold.positive_feed_guardrail_terms\`"
```

## Manual Pipeline Smoke Test

Run the deployed Cloud Run Job manually:

```bash
gcloud run jobs execute <PIPELINE_JOB_NAME> \
  --region=<REGION> \
  --project=<GCP_PROJECT_ID> \
  --wait
```

Inspect the latest execution:

```bash
gcloud run jobs executions list \
  --job=<PIPELINE_JOB_NAME> \
  --region=<REGION> \
  --project=<GCP_PROJECT_ID> \
  --limit=5
```

Inspect logs:

```bash
gcloud logging read \
  'resource.type="cloud_run_job" AND resource.labels.job_name="<PIPELINE_JOB_NAME>"' \
  --project=<GCP_PROJECT_ID> \
  --limit=100 \
  --format='value(textPayload)'
```

Verify row counts:

```bash
bq query --use_legacy_sql=false "select count(*) as bronze_rows from \`<GCP_PROJECT_ID>.bronze.gdelt_news_raw\`"
bq query --use_legacy_sql=false "select count(*) as silver_rows, countif(is_duplicate = false) as silver_canonical_rows from \`<GCP_PROJECT_ID>.silver.gdelt_news_refined\`"
bq query --use_legacy_sql=false "select count(*) as gold_rows, countif(is_positive_feed_eligible) as eligible_rows from \`<GCP_PROJECT_ID>.gold.positive_news_feed\`"
bq query --use_legacy_sql=false "select audit_run_at, bronze_row_count, silver_row_count, silver_canonical_row_count, gold_row_count from \`<GCP_PROJECT_ID>.gold.pipeline_run_metrics\` order by audit_run_at desc limit 5"
```

If the smoke test is for a Gold Python load or a `dlt` merge-path regression, also verify the staging dataset and downstream assets explicitly:

```bash
bq show <GCP_PROJECT_ID>:gold_staging
bq query --use_legacy_sql=false "select count(*) as url_validation_rows from \`<GCP_PROJECT_ID>.gold.url_validation_results\`"
bq query --use_legacy_sql=false "select status, count(*) as row_count from \`<GCP_PROJECT_ID>.gold.url_validation_results\` where checked_at >= timestamp_sub(current_timestamp(), interval 24 hour) group by 1 order by row_count desc"
bq query --use_legacy_sql=false "select count(*) as source_quality_rows from \`<GCP_PROJECT_ID>.gold.source_quality_snapshot\`"
bq query --use_legacy_sql=false "select count(*) as positive_news_shadow_rows from \`<GCP_PROJECT_ID>.gold.positive_news_feed_v3_shadow\`"
```

If restricted egress is enabled for the pipeline and archive jobs, also inspect blocked firewall logs after the manual run:

```bash
gcloud logging read \
  'logName="projects/<GCP_PROJECT_ID>/logs/compute.googleapis.com%2Ffirewall" AND jsonPayload.disposition="DENIED" AND (jsonPayload.rule_details.reference:"tidingsiq-restricted-egress-<ENVIRONMENT>-metadata-deny" OR jsonPayload.rule_details.reference:"tidingsiq-restricted-egress-<ENVIRONMENT>-non-public-deny")' \
  --project=<GCP_PROJECT_ID> \
  --limit=50 \
  --format='value(jsonPayload.connection.src_ip,jsonPayload.connection.dest_ip,jsonPayload.rule_details.reference)'
```

Describe the blocked-egress metric:

```bash
gcloud logging metrics describe <RESTRICTED_EGRESS_METRIC_NAME> \
  --project=<GCP_PROJECT_ID>
```

If the smoke test is for URL-validation safety or SSRF hardening, add these checks:

```bash
bq query --use_legacy_sql=false "with suspicious as ( select normalized_url, url from \`<GCP_PROJECT_ID>.silver.gdelt_news_refined\` where is_duplicate = false and url is not null and (regexp_contains(lower(url), r'^https?://(127\\.|10\\.|192\\.168\\.|169\\.254\\.|metadata(\\.|/|:)|metadata\\.google\\.internal)') or regexp_contains(lower(url), r'^https?://[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+')) ) select count(*) as suspicious_source_urls from suspicious"
bq query --use_legacy_sql=false "select count(*) as url_validation_rows, countif(status = 'unavailable') as unavailable_rows, max(checked_at) as latest_checked_at from \`<GCP_PROJECT_ID>.gold.url_validation_results\`"
gcloud logging read 'resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"<PIPELINE_JOB_NAME>\" AND textPayload:\"Blocked URL target\"' --project=<GCP_PROJECT_ID> --limit=50 --format='value(timestamp,textPayload)'
```

Interpretation notes:

- `suspicious_source_urls = 0` means the current live Silver candidate set does not contain obvious SSRF-pattern URLs, so the live run mainly validates that the guardrail does not regress normal public validation traffic.
- If suspicious URLs are present, the Cloud Run logs should show `Blocked URL target` entries with explicit reasons such as `blocked_ip_literal`, `blocked_private_ip`, or `blocked_metadata_host`.
- Blocked targets currently surface as `status = 'unavailable'` in `gold.url_validation_results`; that is intentional to avoid downstream schema and scoring changes.

## Scheduler Operations

Rollout note:

- pausing `<PIPELINE_SCHEDULER_NAME>` pauses only the main Bruin pipeline cadence
- it does not pause `<REPORTING_SCHEDULER_NAME>` or `<ARCHIVE_SCHEDULER_NAME>`
- pause those separate schedulers only when their own job image, runtime config, or downstream contract is being changed

Describe the current pipeline scheduler:

```bash
gcloud scheduler jobs describe <PIPELINE_SCHEDULER_NAME> \
  --location=<REGION> \
  --project=<GCP_PROJECT_ID>
```

Pause:

```bash
gcloud scheduler jobs pause <PIPELINE_SCHEDULER_NAME> \
  --location=<REGION> \
  --project=<GCP_PROJECT_ID>
```

Resume:

```bash
gcloud scheduler jobs resume <PIPELINE_SCHEDULER_NAME> \
  --location=<REGION> \
  --project=<GCP_PROJECT_ID>
```

Trigger immediately:

```bash
gcloud scheduler jobs run <PIPELINE_SCHEDULER_NAME> \
  --location=<REGION> \
  --project=<GCP_PROJECT_ID>
```

Describe the daily reporting scheduler:

```bash
gcloud scheduler jobs describe <REPORTING_SCHEDULER_NAME> \
  --location=<REGION> \
  --project=<GCP_PROJECT_ID>
```

Describe the Bronze archive scheduler:

```bash
gcloud scheduler jobs describe <ARCHIVE_SCHEDULER_NAME> \
  --location=<REGION> \
  --project=<GCP_PROJECT_ID>
```

If restricted egress is enabled, verify the connector state before resuming schedulers:

```bash
gcloud compute networks vpc-access connectors describe tidingsiq-restricted-egress-<ENVIRONMENT>-connector \
  --region=<REGION> \
  --project=<GCP_PROJECT_ID>
```

## Public App Edge Operations

Describe the hosted app service:

```bash
gcloud run services describe <APP_SERVICE_NAME> \
  --region=<REGION> \
  --project=<GCP_PROJECT_ID>
```

Confirm the app ingress is load-balancer-only:

```bash
gcloud run services describe <APP_SERVICE_NAME> \
  --region=<REGION> \
  --project=<GCP_PROJECT_ID> \
  --format='value(spec.template.metadata.annotations.run.googleapis.com/ingress,status.url)'
```

Describe the HTTPS forwarding rule:

```bash
gcloud compute forwarding-rules describe <APP_HTTPS_FORWARDING_RULE_NAME> \
  --global \
  --project=<GCP_PROJECT_ID>
```

Describe the HTTP redirect forwarding rule:

```bash
gcloud compute forwarding-rules describe <APP_HTTP_FORWARDING_RULE_NAME> \
  --global \
  --project=<GCP_PROJECT_ID>
```

Describe the Cloud Armor policy:

```bash
gcloud compute security-policies describe <APP_CLOUD_ARMOR_POLICY_NAME> \
  --project=<GCP_PROJECT_ID>
```

Smoke test the public hostname:

```bash
curl -I https://<APP_DOMAIN_NAME>
curl -I http://<APP_DOMAIN_NAME>
```

The HTTP response should redirect to HTTPS, and the HTTPS response should be served by the load balancer hostname rather than a direct public `run.app` path.

Inspect preview-mode throttle events during the monitor-first rollout:

```bash
gcloud logging read \
  'resource.type="http_load_balancer" AND resource.labels.backend_service_name="<APP_BACKEND_SERVICE_NAME>" AND jsonPayload.previewSecurityPolicy.configuredAction="THROTTLE" AND jsonPayload.previewSecurityPolicy.rateLimitAction.outcome="RATE_LIMIT_THRESHOLD_EXCEED"' \
  --project=<GCP_PROJECT_ID> \
  --limit=50 \
  --format='value(timestamp,httpRequest.remoteIp,jsonPayload.previewSecurityPolicy.rateLimitAction.outcome)'
```

Inspect enforced throttle denials after preview mode is turned off:

```bash
gcloud logging read \
  'resource.type="http_load_balancer" AND resource.labels.backend_service_name="<APP_BACKEND_SERVICE_NAME>" AND jsonPayload.enforcedSecurityPolicy.configuredAction="THROTTLE" AND jsonPayload.statusDetails="denied_by_security_policy"' \
  --project=<GCP_PROJECT_ID> \
  --limit=50 \
  --format='value(timestamp,httpRequest.remoteIp,jsonPayload.statusDetails)'
```

Inspect app request-volume logs:

```bash
gcloud logging read \
  'resource.type="http_load_balancer" AND resource.labels.backend_service_name="<APP_BACKEND_SERVICE_NAME>"' \
  --project=<GCP_PROJECT_ID> \
  --limit=50 \
  --format='value(timestamp,httpRequest.requestMethod,httpRequest.requestUrl,httpRequest.status)'
```

Rollout criteria:

- keep preview mode enabled for the first 7 days
- review page refreshes, pagination, filter changes, and multiple-user NAT traffic before enforcement
- disable preview mode before tightening thresholds
- only consider reducing the threshold toward `90 requests / 60 seconds / IP` after a second observation window

## Bronze Archive Operations

Rollout caveat:

- Export-only Bronze archive runs are not yet idempotent across repeated daily executions. If `bronze_archive_dry_run = false` and `bronze_archive_delete_after_export = false`, or if a delete-enabled run exports successfully but fails before delete completes, the next run can export the same old Bronze rows again into a new `cutoff_date=...` path.
- Keep export-only mode short-lived during rollout, review the emitted `BRONZE_ARCHIVE_SUMMARY` logs closely, and do not treat repeated export-only schedules as a steady-state retention strategy until the archive path gains a persisted high-water mark, non-overlapping export windows, or equivalent reconciliation.

Run the deployed Bronze archive job manually in dry-run mode:

```bash
gcloud run jobs execute <ARCHIVE_JOB_NAME> \
  --region=<REGION> \
  --project=<GCP_PROJECT_ID> \
  --wait
```

Inspect recent archive executions:

```bash
gcloud run jobs executions list \
  --job=<ARCHIVE_JOB_NAME> \
  --region=<REGION> \
  --project=<GCP_PROJECT_ID> \
  --limit=5
```

Inspect archive summary logs:

```bash
gcloud logging read \
  'resource.type="cloud_run_job" AND resource.labels.job_name="<ARCHIVE_JOB_NAME>" AND textPayload:"BRONZE_ARCHIVE_SUMMARY"' \
  --project=<GCP_PROJECT_ID> \
  --limit=20 \
  --format='value(textPayload)'
```

Pause the Bronze archive scheduler during rollout:

```bash
gcloud scheduler jobs pause <ARCHIVE_SCHEDULER_NAME> \
  --location=<REGION> \
  --project=<GCP_PROJECT_ID>
```

Resume the Bronze archive scheduler:

```bash
gcloud scheduler jobs resume <ARCHIVE_SCHEDULER_NAME> \
  --location=<REGION> \
  --project=<GCP_PROJECT_ID>
```

Trigger the Bronze archive scheduler immediately:

```bash
gcloud scheduler jobs run <ARCHIVE_SCHEDULER_NAME> \
  --location=<REGION> \
  --project=<GCP_PROJECT_ID>
```

Check the current eligible Bronze backlog against the archive cutoff:

```bash
bq query --use_legacy_sql=false "select count(*) as eligible_rows, min(ingested_at) as oldest_eligible_ingested_at from \`<GCP_PROJECT_ID>.bronze.gdelt_news_raw\` where ingested_at < timestamp_sub(timestamp_trunc(current_timestamp(), day), interval 45 day)"
```

Validate exported parquet row count for a specific cutoff date:

```bash
bq query --use_legacy_sql=false "create or replace external table \`<GCP_PROJECT_ID>.bronze_staging.archive_validation\` options(format='PARQUET', uris=['<ARCHIVE_BUCKET_URI>/automated/bronze_gdelt_news_raw/cutoff_date=<ARCHIVE_CUTOFF_DATE>/*.parquet']); select count(*) as exported_rows from \`<GCP_PROJECT_ID>.bronze_staging.archive_validation\`"
```

## Image And Deployment Debug

Build and push the pipeline image:

```bash
cd "/Volumes/SWE/repos/DE 2026/tidingsiq"
docker buildx build \
  --platform linux/amd64 \
  -f pipeline/bruin/Dockerfile \
  -t <PIPELINE_IMAGE_URI> \
  --push .
```

Use an explicit tag or digest-backed image reference for `<PIPELINE_IMAGE_URI>`; Terraform no longer falls back to `:latest` for the shared pipeline/reporting/archive image path.

Update the Cloud Run pipeline job to the pushed image:

```bash
gcloud run jobs update <PIPELINE_JOB_NAME> \
  --region=<REGION> \
  --project=<GCP_PROJECT_ID> \
  --image=<PIPELINE_IMAGE_URI>
```

Update the reporting job to the same image:

```bash
gcloud run jobs update <REPORTING_JOB_NAME> \
  --region=<REGION> \
  --project=<GCP_PROJECT_ID> \
  --image=<PIPELINE_IMAGE_URI>
```

Update the Bronze archive job to the same image:

```bash
gcloud run jobs update <ARCHIVE_JOB_NAME> \
  --region=<REGION> \
  --project=<GCP_PROJECT_ID> \
  --image=<PIPELINE_IMAGE_URI>
```

Run the reporting job manually:

```bash
gcloud run jobs execute <REPORTING_JOB_NAME> \
  --region=<REGION> \
  --project=<GCP_PROJECT_ID> \
  --wait
```

Inspect reporting logs:

```bash
gcloud logging read \
  'resource.type="cloud_run_job" AND resource.labels.job_name="<REPORTING_JOB_NAME>"' \
  --project=<GCP_PROJECT_ID> \
  --limit=100 \
  --format='value(textPayload)'
```

Check report-source tables:

```bash
bq query --use_legacy_sql=false "select count(*) as gold_rows, countif(is_positive_feed_eligible) as eligible_rows, countif(not is_positive_feed_eligible) as ineligible_rows from \`<GCP_PROJECT_ID>.gold.positive_news_feed\`"
bq query --use_legacy_sql=false "select coalesce(exclusion_reason, 'eligible') as bucket, count(*) as row_count from \`<GCP_PROJECT_ID>.gold.positive_news_feed\` group by 1 order by row_count desc"
bq query --use_legacy_sql=false "select * from \`<GCP_PROJECT_ID>.gold.pipeline_run_metrics\` order by audit_run_at desc limit 1"
```

If `gold.pipeline_run_metrics` fails with an inserted-column-count mismatch after a model change, the live table schema is behind the SQL model. Because this asset uses append materialization, truncating rows alone does not update the table definition. Either:

- add the missing columns and backfill historical rows before rerunning, if the history must be preserved
- or drop and recreate `gold.pipeline_run_metrics` with the current schema and partitioning, then rerun the pipeline or rerun `pipeline/bruin/assets/gold/pipeline_run_metrics.sql`, if losing the operational history is acceptable

Inspect summary-delivery logs:

```bash
gcloud logging read \
  'resource.type="cloud_run_job" AND resource.labels.job_name="<REPORTING_JOB_NAME>" AND textPayload:"DAILY_PIPELINE_SUMMARY"' \
  --project=<GCP_PROJECT_ID> \
  --limit=20 \
  --format='value(textPayload)'
```

Inspect blocked-egress activity after the first scheduled run:

```bash
gcloud logging read \
  'logName="projects/<GCP_PROJECT_ID>/logs/compute.googleapis.com%2Ffirewall" AND jsonPayload.disposition="DENIED" AND (jsonPayload.rule_details.reference:"tidingsiq-restricted-egress-<ENVIRONMENT>-metadata-deny" OR jsonPayload.rule_details.reference:"tidingsiq-restricted-egress-<ENVIRONMENT>-non-public-deny")' \
  --project=<GCP_PROJECT_ID> \
  --limit=100
```

## Terraform Rollout Notes

If the scheduler should stay paused during a rollout, keep `pipeline_schedule_paused = true` in the local `terraform.tfvars` until the manual smoke test is clean.

If restricted egress is enabled:

- keep `bronze_archive_schedule_paused = true` until the archive job also succeeds through the connector-backed path
- capture a `gold.url_validation_results` status mix before and after rollout so unexpected increases in `unavailable`, `timeout`, or `redirect_loop` are visible
- treat denied firewall logs as rollout signals; private, internal, and metadata destinations are expected, while legitimate public publisher redirects may indicate the rules need tuning or the source URL needs review

Do not leave the archive scheduler running indefinitely in export-only mode as the long-term default, because repeated export-only executions can duplicate already archived Bronze rows under newer cutoff-date prefixes.
