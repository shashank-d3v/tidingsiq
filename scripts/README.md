# TidingsIQ Operations Scripts

This directory contains manual operational helpers that sit outside the Bruin pipeline itself.

## `archive_bronze.py`

Exports Bronze rows older than the retention window to GCS and can optionally delete those rows after a successful export.

The script is intentionally explicit:

- it counts eligible rows first
- it normalizes the cutoff to a stable daily boundary unless an explicit cutoff override is provided
- it writes to an idempotent archive path partitioned by `cutoff_date=YYYY-MM-DD`
- it validates exported parquet row count before any delete phase
- it deletes rows only when `--delete-after-export` is set and `--max-delete-rows` is not exceeded
- it emits both a JSON summary payload and a compact `BRONZE_ARCHIVE_SUMMARY` line for Cloud Logging and alerting

Example dry run:

```bash
python3 scripts/archive_bronze.py \
  --project-id <GCP_PROJECT_ID> \
  --archive-uri-prefix <ARCHIVE_BUCKET_URI>/manual \
  --run-date <YYYY-MM-DD> \
  --dry-run
```

Example export without deletion:

```bash
python3 scripts/archive_bronze.py \
  --project-id <GCP_PROJECT_ID> \
  --archive-uri-prefix <ARCHIVE_BUCKET_URI>/manual \
  --max-delete-rows 20000
```

Example export and cleanup:

```bash
python3 scripts/archive_bronze.py \
  --project-id <GCP_PROJECT_ID> \
  --archive-uri-prefix <ARCHIVE_BUCKET_URI>/manual \
  --max-delete-rows 20000 \
  --delete-after-export
```

Requirements:

- Google Application Default Credentials or equivalent auth
- `google-cloud-bigquery` available in the active Python environment
- pipeline service account or operator identity with access to the Bronze archive bucket

This script is the canonical Bronze archive worker for both manual runs and the scheduled Cloud Run job path.

## `daily_pipeline_report.py`

Builds a compact daily warehouse-health summary from:

- `gold.pipeline_run_metrics`
- `gold.positive_news_feed`

The script prints:

- one JSON payload for machine-readable logs
- one compact line prefixed with `DAILY_PIPELINE_SUMMARY` for Cloud Monitoring log-match alerts

This script is designed to run inside the pipeline container as a separate Cloud Run Job.

Example local run:

```bash
python3 scripts/daily_pipeline_report.py
```

Environment variables:

- `TIDINGSIQ_GCP_PROJECT` or `GOOGLE_CLOUD_PROJECT`
- optional `TIDINGSIQ_GOLD_FEED_TABLE`
- optional `TIDINGSIQ_GOLD_METRICS_TABLE`

Requirements:

- Google Application Default Credentials or equivalent auth
- `google-cloud-bigquery` available in the active Python environment

## GDELT reliability schema migration

`migrate_gdelt_reliability_schema.sh` applies the idempotent additive migration in
`migrations/20260826_gdelt_reliability.sql`. It expands Bronze ingestion metadata and
Gold operational metrics without recreating tables, changing partitioning, or
backfilling historical values. It also creates the partitioned
`bronze.gdelt_ingestion_attempts` ledger needed by the updated metrics query.

Run it only after capturing the incident snapshot and pausing the pipeline and
reporting schedulers:

```bash
scripts/migrate_gdelt_reliability_schema.sh <GCP_PROJECT_ID>
```

The operator needs BigQuery schema-update permission for the `bronze` and `gold`
datasets. Re-running the helper is safe because every statement uses
`ADD COLUMN IF NOT EXISTS` or `CREATE TABLE IF NOT EXISTS`.

## `reset_warehouse.sh`

Performs the documented warehouse-only reset for:

- `bronze.gdelt_news_raw`
- `silver.gdelt_news_refined`
- `gold.positive_news_feed`
- `gold.pipeline_run_metrics`
- any residual tables in `bronze_staging`

It intentionally preserves:

- `gold.positive_feed_guardrail_terms`
- all datasets and infrastructure
- archived Bronze objects in GCS

Example:

```bash
scripts/reset_warehouse.sh <GCP_PROJECT_ID>
```


## Checkpointed archival and bounded source repairs

`archive_bronze_incremental.py` is the scheduled archive worker. It exports after
45 days, verifies full Parquet row equivalence, and advances a persisted GCS
checkpoint under a generation lock. `--prune-after-days 90 --max-delete-rows 20000`
retains the complete serving horizon and limits daily pruning. Read `bootstrap.json`
plus the checkpoint's manifest chain when restoring; do not union orphaned batches.
The legacy `archive_bronze.py` is only for explicitly scoped recovery exports.

`repair_gdelt_windows.py --project-id <PROJECT> --start-date YYYY-MM-DD --end-date YYYY-MM-DD`
repairs 1–31 daily sample windows ending at 00:30 UTC. It requires all four ZIPs
for every window, stages JSON load jobs, and executes a single capped merge only
after all windows pass. It preserves newer versions, retains staging for two days,
and must be followed by one full pipeline run. It is not a continuous-day backfill.

See `docs/incident_20260928.md` for migration prerequisites and verified recovery.
