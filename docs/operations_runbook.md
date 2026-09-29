# TidingsIQ Operations Runbook

This runbook contains parameterized example commands for resetting, validating, and debugging a TidingsIQ cloud deployment without exposing any specific live environment.

Replace the placeholders in each command before use:

- `<REPOSITORY_ROOT>`
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
- `<APP_RUN_APP_URL>`

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
cd <REPOSITORY_ROOT>
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

Confirm the Bruin interval matches the intended cadence instead of collapsing to a stale day-wide or zero-width window:

```bash
gcloud logging read \
  'resource.type="cloud_run_job" AND resource.labels.job_name="<PIPELINE_JOB_NAME>" AND textPayload:"Interval:"' \
  --project=<GCP_PROJECT_ID> \
  --limit=5 \
  --format='value(timestamp,textPayload)'
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

Network posture check:

- default dev posture is restricted egress disabled
- pipeline and archive Cloud Run Jobs should not have a `vpcAccess` block
- the restricted-egress connector should not exist unless `enable_restricted_egress = true`

Verify default low-cost egress posture:

```bash
gcloud run jobs describe <PIPELINE_JOB_NAME> \
  --region=<REGION> \
  --project=<GCP_PROJECT_ID> \
  --format='yaml(template.template.vpcAccess)'

gcloud run jobs describe <ARCHIVE_JOB_NAME> \
  --region=<REGION> \
  --project=<GCP_PROJECT_ID> \
  --format='yaml(template.template.vpcAccess)'

gcloud compute networks vpc-access connectors describe tiq-eg-<ENVIRONMENT> \
  --region=<REGION> \
  --project=<GCP_PROJECT_ID>
```

Expected result for the active dev cost-control posture:

- both Cloud Run job describes show `null` for `vpcAccess`
- the connector describe returns `NOT_FOUND`

If restricted egress is deliberately enabled for the pipeline and archive jobs, also inspect blocked firewall logs after the manual run:

```bash
gcloud logging read \
  'logName="projects/<GCP_PROJECT_ID>/logs/compute.googleapis.com%2Ffirewall" AND jsonPayload.disposition="DENIED" AND (jsonPayload.rule_details.reference:"tidingsiq-restricted-egress-<ENVIRONMENT>-metadata-deny" OR jsonPayload.rule_details.reference:"tidingsiq-restricted-egress-<ENVIRONMENT>-non-public-deny")' \
  --project=<GCP_PROJECT_ID> \
  --limit=50 \
  --format='value(jsonPayload.connection.src_ip,jsonPayload.connection.dest_ip,jsonPayload.rule_details.reference)'
```

Describe the blocked-egress metric only when restricted egress is enabled:

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

## GDELT Source-Window Reliability

Normal runs resolve four consecutive 15-minute GKG archives from GDELT's validated
`lastupdate.txt` manifest. If the manifest remains unavailable or invalid after the
configured retries, the pipeline emits `GDELT_MANIFEST_FALLBACK` and anchors the
window at `floor(now - GDELT_PUBLICATION_LAG_MINUTES)`. Explicit Bruin intervals
remain authoritative for backfills and do not contact the manifest. Invoke Bruin
with `--start-date` and `--end-date`; the asset prefers Bruin's exact intraday
`BRUIN_START_DATETIME`/`BRUIN_END_DATETIME` values and falls back to the date-only
variables only for compatible direct execution.

Bruin also exports a computed interval for ordinary scheduled runs. The container
entrypoint records whether `--start-date`/`--end-date` were actually supplied, and
the ingestion ignores Bruin's generated interval for deployed live executions so
they continue to use the manifest or lag fallback.

The archive downloader retries transient transport failures and configured HTTP
statuses within each asset. Cloud Run job retries remain disabled (`maxRetries=0`),
so a successful asset is never rerun merely because another archive was late.
Interpret `GDELT_DOWNLOAD_ATTEMPT` records together with the terminal
`GDELT_INGESTION_SUMMARY`; response bodies are intentionally absent from logs.

Window outcomes are:

- `complete`: all four archives downloaded; normal volume evaluation applies
- `partial`: one to three archives downloaded; valid rows land and volume evaluation is skipped
- `empty`: no archives downloaded; Bronze data is left unchanged and volume evaluation is skipped

Terminal source-fetch outcomes (`complete`, `partial`, and `empty`) are also
persisted to `bronze.gdelt_ingestion_attempts` before the asset returns. Recording
failures stop the asset rather than silently dropping monitoring state. This
ledger describes source downloads, not the later Bruin/dlt commit; parser and
warehouse-load failures still use the pipeline failure alert. Historical rows
without ledger entries remain available through the metrics query's fallback.
The daily report labels a fresh 0/4 attempt `gdelt_window_empty`, and absent live
history `gdelt_window_unknown`; a backfill-only warehouse still emits a metrics
snapshot with nullable live-ingestion fields.

Every incomplete live window triggers the `TidingsIQ GDELT Incomplete Source Window`
policy immediately. Backfills are excluded from that policy and must be checked
synchronously by their operator. Corrupt ZIPs, parser failures, excessive malformed
rows, and zero accepted rows from a downloaded archive remain hard failures.

The adaptive volume check considers only complete, non-backfill ingestions with a
five-run baseline. One or two low-volume observations warn; the third consecutive
qualifying low-volume ingestion lands before the downstream Gold custom check fails.
Partial and backfill ingestions neither advance nor reset the streak. The emergency
`GDELT_LOW_ACCEPTED_ROW_ACTION=fail` override restores immediate Bronze failure and
should remain disabled during normal operation.

Before deploying a schema-changing image:

1. Record the current image digest, scheduler states, BigQuery schemas, row counts,
   latest ingestion timestamps, and recent metrics rows in an incident snapshot.
2. Pause the pipeline and reporting schedulers; leave the unrelated archive scheduler unchanged.
3. Run `scripts/migrate_gdelt_reliability_schema.sh <GCP_PROJECT_ID>`; this also creates
   the partitioned source-attempt ledger required by the metrics query. Run it
   before a metrics-only deployment, even if the additive columns already exist.
4. Verify the additive columns and confirm the pipeline service account can append to both expanded tables.
5. Apply the reviewed Terraform plan and immutable image digest, preserving one task,
   one worker, `4Gi`, `3600s`, and `maxRetries=0`.
6. Run a manual canary. Do not resume either scheduler until a complete `4/4` canary
   has loaded Bronze, Silver, Gold, metrics, and URL validation successfully.

For a targeted historical repair, execute only
`pipeline/bruin/assets/bronze/gdelt_news_raw.py` and pass the exact interval through
Bruin's `--start-date` and `--end-date` flags. Require `mode=backfill`,
`downloaded_files=4`, a positive accepted-row count, the exact expected source-window
bounds, and the four expected archive filenames; stop on the first mismatch or
incomplete window. Record the ingestion ID and filenames. After all Bronze repairs,
run the full pipeline once and verify four distinct GKG archives per repaired window,
no duplicate inflation, and exclusion of backfills from the live low-volume streak.

Rollback restores the recorded previous image digest and environment while both
schedulers remain paused. Additive schema columns and monitoring resources may stay.
Do not delete backfilled data automatically; any corrupt ingestion requires a
separately reviewed repair scoped by its recorded ingestion ID and archive list.

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
gcloud compute networks vpc-access connectors describe tiq-eg-<ENVIRONMENT> \
  --region=<REGION> \
  --project=<GCP_PROJECT_ID>
```

## Public App Operations

Describe the hosted app service:

```bash
gcloud run services describe <APP_SERVICE_NAME> \
  --region=<REGION> \
  --project=<GCP_PROJECT_ID>
```

Fetch the direct public `run.app` URL:

```bash
gcloud run services describe <APP_SERVICE_NAME> \
  --region=<REGION> \
  --project=<GCP_PROJECT_ID> \
  --format='value(status.url)'
```

Confirm the app is publicly reachable on the direct Cloud Run URL:

```bash
curl -I <APP_RUN_APP_URL>
```

Confirm the service is not restricted to a load-balancer-only ingress path:

```bash
gcloud run services describe <APP_SERVICE_NAME> \
  --region=<REGION> \
  --project=<GCP_PROJECT_ID> \
  --format='json(metadata.annotations,status.url)'
```

Smoke test the app root:

```bash
curl -L <APP_RUN_APP_URL> | head -n 20
```

Inspect recent Cloud Run request logs:

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="<APP_SERVICE_NAME>"' \
  --project=<GCP_PROJECT_ID> \
  --limit=50 \
  --format='value(timestamp,httpRequest.requestMethod,httpRequest.requestUrl,httpRequest.status)'
```

Current expected posture:

- Cloud Run serves the app directly on the reported `run.app` URL.
- No load balancer, Cloud Armor policy, forwarding rules, or custom-domain DNS should be required for the active deployment.
- If future traffic warrants stricter protection, the optional AppEdge Terraform slice can be re-enabled.

## Bronze Archive Operations

The active worker is `scripts/archive_bronze_incremental.py`. It uses a GCS
checkpoint, generation-conditional lock, immutable export paths, and full-row
Parquet reconciliation. The legacy `scripts/archive_bronze.py` remains available
for explicit recovery exports; do not schedule that legacy export-only path.
See [September recovery](incident_20260928.md) for the verified cutover and rollback.

Normal archival exports data after 45 days. Optional `--prune-after-days 90`
removes only checkpoint-covered rows outside both the ingestion and publication
90-day horizons. The default prune cap is 20,000 rows; a backlog above that cap
fails before deletion and needs a verified catch-up operation.

A repeated completed window is a no-op. A crashed worker may leave
`automated/archive.lock`; confirm its execution has terminated before removing
that exact object generation. Read committed manifests from `checkpoint.json`
and its predecessor links plus `bootstrap.json`, not by globbing every batch (failed batches may be
orphaned). Keep the bootstrap recovery export referenced by the initial checkpoint.

Run the deployed Bronze archive job with its configured export/retention policy:

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
cd <REPOSITORY_ROOT>
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

Common runtime failures and expected handling:

- `bronze.gdelt_news_raw` with `_csv.Error: field larger than field limit`: the Bronze parser raises Python's CSV field limit to `16MiB` by default. If GDELT legitimately emits larger fields, increase `GDELT_CSV_FIELD_SIZE_LIMIT` on the Cloud Run Job and rerun after rebuilding/deploying the image that contains this handling.
- `gold.url_validation_results` with `RemoteDisconnected`, `ConnectionResetError`, or incomplete reads from a publisher: the validator records the URL as `unavailable` and continues. Retries are intentionally not enabled yet.
- `bronze.gdelt_news_raw` with accepted rows below the recent average: this is now a warning by default because GDELT volume can swing substantially by window. Empty downloads, zero accepted rows, and high malformed-row ratios remain hard failures. Use `GDELT_LOW_ACCEPTED_ROW_ACTION=fail` only when row-count drops should page/fail immediately.

Inspect summary-delivery logs:

```bash
gcloud logging read \
  'resource.type="cloud_run_job" AND resource.labels.job_name="<REPORTING_JOB_NAME>" AND textPayload:"DAILY_PIPELINE_SUMMARY"' \
  --project=<GCP_PROJECT_ID> \
  --limit=20 \
  --format='value(textPayload)'
```

Inspect blocked-egress activity after the first scheduled run only when restricted egress is enabled:

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

The checkpointed worker supports export-only scheduling without repeated completed-window exports. Enable 90-day hot retention only after archive verification and a rollback snapshot; retain the configured daily deletion cap.
