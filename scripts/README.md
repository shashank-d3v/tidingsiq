# TidingsIQ Operations Scripts

This directory contains scheduled workers and manual operational helpers outside the Bruin asset graph.

## Traffic and engagement reporting

`analyse_traffic.py` summarizes bounded Cloud Run request/event JSON exports into
aggregate page-load, engagement, click and legacy-client metrics without exposing
addresses. `verify_engagement_frontend.py` checks routes, feed row counts and
reserved QA events on a staged/public frontend. See
[measurement definitions and the scheduled review](../docs/engagement_rollout_20261002.md).

## `publish_static_feed.py`

Daily public-feed publisher. Reads eligible Gold rows and run metrics using the
publisher identity, requires the latest Cloud Run pipeline execution to have
succeeded, and verifies its time interval contains the metrics audit timestamp.
It validates freshness/completeness, assigns stories while retaining all variants
in 7/30-day JSON/gzip files, and verifies uploaded bytes. Before the generation-
conditional manifest switch it rechecks the execution; a failed, active or changed
execution leaves the previous manifest intact.

```bash
python3 scripts/publish_static_feed.py \
  --project <GCP_PROJECT_ID> --bucket <STATIC_FEED_BUCKET> --location <BIGQUERY_LOCATION> \
  --pipeline-region <CLOUD_RUN_REGION> --pipeline-job <PIPELINE_JOB_NAME>
```

This is a production write operation, not a local preview command. Use the
[static app guide](../app/static/README.md) for a credential-free local preview and
the [deployment guide](../docs/deployment_plan.md#publisher-release) for its image.
Each query has a 500 MB billed-byte cap; success/failure logs start with
`STATIC_FEED_PUBLISH`. Tests are in `tests/test_publish_static_feed.py`.

## `archive_bronze.py` (Legacy Recovery Helper)

Retained for explicitly scoped recovery exports. It is **not** the scheduled
worker and does not implement the current checkpoint/full-row verification
contract. Do not use its legacy deletion option as a substitute for guarded
90-day pruning. Scheduled archival uses `archive_bronze_incremental.py`, described
below and in the [runbook](../docs/operations_runbook.md#bronze-archive-operations).

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

See `docs/history/incident_20260928.md` for migration prerequisites and verified recovery.
