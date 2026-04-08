# TidingsIQ Operations Scripts

This directory contains manual operational helpers that sit outside the Bruin pipeline itself.

## `archive_bronze.py`

Exports Bronze rows older than the retention window to GCS and can optionally delete those rows after a successful export.

The script is intentionally explicit:

- it counts eligible rows first
- it defaults to dry-run behavior when `--dry-run` is provided
- it deletes rows only when `--delete-after-export` is set

Example dry run:

```bash
python3 scripts/archive_bronze.py \
  --project-id tidingsiq-dev \
  --archive-uri-prefix gs://your-bronze-archive-bucket/manual \
  --dry-run
```

Example export without deletion:

```bash
python3 scripts/archive_bronze.py \
  --project-id tidingsiq-dev \
  --archive-uri-prefix gs://your-bronze-archive-bucket/manual
```

Example export and cleanup:

```bash
python3 scripts/archive_bronze.py \
  --project-id tidingsiq-dev \
  --archive-uri-prefix gs://your-bronze-archive-bucket/manual \
  --delete-after-export
```

Requirements:

- Google Application Default Credentials or equivalent auth
- `google-cloud-bigquery` available in the active Python environment
- pipeline service account or operator identity with access to the Bronze archive bucket

This script is the current manual Bronze retention path. No recurring retention automation is configured yet.

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
scripts/reset_warehouse.sh tidingsiq-dev
```
