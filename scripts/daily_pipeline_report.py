from __future__ import annotations

import json
import os
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone


SUMMARY_MARKER = "DAILY_PIPELINE_SUMMARY"


def determine_action_needed(
    *,
    latest_gold_ingested_at: datetime | None,
    gold_row_count: int,
    eligible_row_count: int,
    bronze_window_is_complete: bool | None = None,
    bronze_downloaded_file_count: int | None = None,
    consecutive_complete_low_volume_run_count: int = 0,
    now_utc: datetime | None = None,
) -> str:
    now_utc = now_utc or datetime.now(timezone.utc)

    if gold_row_count <= 0:
        return "gold_empty"
    if eligible_row_count <= 0:
        return "eligible_feed_empty"
    if latest_gold_ingested_at is None:
        return "gold_stale"
    if latest_gold_ingested_at.tzinfo is None:
        latest_gold_ingested_at = latest_gold_ingested_at.replace(tzinfo=timezone.utc)
    if latest_gold_ingested_at < now_utc - timedelta(hours=18):
        return "gold_stale"
    if consecutive_complete_low_volume_run_count >= 3:
        return "gdelt_low_volume_failure"
    if bronze_window_is_complete is False:
        return "gdelt_window_empty" if bronze_downloaded_file_count == 0 else "gdelt_window_partial"
    if bronze_window_is_complete is None:
        return "gdelt_window_unknown"
    if consecutive_complete_low_volume_run_count > 0:
        return "gdelt_low_volume_warning"

    return "healthy"


def build_report_payload(
    *,
    latest_metrics: dict[str, object],
    exclusion_counts: dict[str, int],
    generated_at: datetime | None = None,
) -> dict[str, object]:
    generated_at = generated_at or datetime.now(timezone.utc)
    eligible_row_count = int(exclusion_counts.get("eligible", 0))
    ineligible_row_count = sum(
        count for bucket, count in exclusion_counts.items() if bucket != "eligible"
    )

    action_needed = determine_action_needed(
        latest_gold_ingested_at=latest_metrics.get("latest_gold_ingested_at"),
        gold_row_count=int(latest_metrics.get("gold_row_count", 0)),
        eligible_row_count=eligible_row_count,
        bronze_window_is_complete=latest_metrics.get(
            "latest_bronze_ingestion_is_complete"
        ),
        bronze_downloaded_file_count=latest_metrics.get(
            "latest_bronze_ingestion_downloaded_file_count"
        ),
        consecutive_complete_low_volume_run_count=int(
            latest_metrics.get("consecutive_complete_low_volume_run_count", 0) or 0
        ),
        now_utc=generated_at,
    )

    expected_files = int(
        latest_metrics.get("latest_bronze_ingestion_expected_file_count", 0) or 0
    )
    downloaded_files = int(
        latest_metrics.get("latest_bronze_ingestion_downloaded_file_count", 0) or 0
    )
    is_complete = latest_metrics.get("latest_bronze_ingestion_is_complete")
    bronze_window_status = (
        "unknown"
        if is_complete is None
        else "complete"
        if bool(is_complete)
        else "empty"
        if downloaded_files == 0
        else "partial"
    )

    top_exclusions = sorted(
        (
            {"bucket": bucket, "rows": rows}
            for bucket, rows in exclusion_counts.items()
            if bucket != "eligible"
        ),
        key=lambda item: (-item["rows"], item["bucket"]),
    )[:3]

    return {
        "report_type": SUMMARY_MARKER,
        "generated_at": generated_at.isoformat(),
        "latest_run_at": _isoformat_or_none(latest_metrics.get("audit_run_at")),
        "latest_gold_ingested_at": _isoformat_or_none(
            latest_metrics.get("latest_gold_ingested_at")
        ),
        "bronze_source_window_start": _isoformat_or_none(
            latest_metrics.get("latest_bronze_source_window_start")
        ),
        "bronze_source_window_end": _isoformat_or_none(
            latest_metrics.get("latest_bronze_source_window_end")
        ),
        "bronze_files_downloaded": downloaded_files,
        "bronze_files_expected": expected_files,
        "bronze_window_status": bronze_window_status,
        "bronze_low_volume": latest_metrics.get(
            "latest_bronze_ingestion_low_volume"
        ),
        "bronze_low_volume_streak": int(
            latest_metrics.get("consecutive_complete_low_volume_run_count", 0) or 0
        ),
        "bronze_row_count": int(latest_metrics.get("bronze_row_count", 0)),
        "silver_row_count": int(latest_metrics.get("silver_row_count", 0)),
        "silver_canonical_row_count": int(
            latest_metrics.get("silver_canonical_row_count", 0)
        ),
        "silver_duplicate_row_count": int(
            latest_metrics.get("silver_duplicate_row_count", 0)
        ),
        "gold_row_count": int(latest_metrics.get("gold_row_count", 0)),
        "eligible_row_count": eligible_row_count,
        "ineligible_row_count": ineligible_row_count,
        "gold_avg_happy_factor": _float_or_none(latest_metrics.get("gold_avg_happy_factor")),
        "gold_max_happy_factor": _float_or_none(latest_metrics.get("gold_max_happy_factor")),
        "top_exclusions": top_exclusions,
        "action_needed": action_needed,
    }


def build_summary_line(report: dict[str, object]) -> str:
    top_exclusions = report.get("top_exclusions") or []
    exclusion_text = ",".join(
        f"{item['bucket']}:{item['rows']}" for item in top_exclusions if item
    ) or "none"

    return (
        f"{SUMMARY_MARKER} "
        f"generated_at={report['generated_at']} "
        f"latest_run_at={report['latest_run_at'] or 'none'} "
        f"bronze_window={report['bronze_window_status']} "
        f"bronze_files={report['bronze_files_downloaded']}/{report['bronze_files_expected']} "
        f"bronze_low_volume={report['bronze_low_volume']} "
        f"bronze_low_volume_streak={report['bronze_low_volume_streak']} "
        f"bronze={report['bronze_row_count']} "
        f"silver={report['silver_row_count']} "
        f"canonical={report['silver_canonical_row_count']} "
        f"duplicates={report['silver_duplicate_row_count']} "
        f"gold={report['gold_row_count']} "
        f"eligible={report['eligible_row_count']} "
        f"ineligible={report['ineligible_row_count']} "
        f"avg_happy={report['gold_avg_happy_factor']} "
        f"max_happy={report['gold_max_happy_factor']} "
        f"top_exclusions={exclusion_text} "
        f"action={report['action_needed']}"
    )


def _isoformat_or_none(value: object) -> str | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    return None


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def fetch_latest_metrics(client, metrics_table_fqn: str) -> dict[str, object]:
    query = f"""
select
  audit_run_at,
  bronze_row_count,
  silver_row_count,
  silver_canonical_row_count,
  silver_duplicate_row_count,
  gold_row_count,
  gold_avg_happy_factor,
  gold_max_happy_factor,
  latest_gold_ingested_at,
  latest_gold_published_at,
  latest_bronze_source_window_start,
  latest_bronze_source_window_end,
  latest_bronze_ingestion_expected_file_count,
  latest_bronze_ingestion_downloaded_file_count,
  latest_bronze_ingestion_is_complete,
  latest_bronze_ingestion_low_volume,
  consecutive_complete_low_volume_run_count
from `{metrics_table_fqn}`
order by audit_run_at desc
limit 1
"""
    rows = list(client.query(query).result())
    if not rows:
        raise RuntimeError(f"No rows found in metrics table {metrics_table_fqn}.")
    return dict(rows[0].items())


def fetch_exclusion_counts(client, gold_feed_table_fqn: str) -> dict[str, int]:
    query = f"""
select
  coalesce(exclusion_reason, 'eligible') as bucket,
  count(*) as row_count
from `{gold_feed_table_fqn}`
group by 1
"""
    rows = list(client.query(query).result())
    return {str(row["bucket"]): int(row["row_count"]) for row in rows}


def main() -> int:
    from google.cloud import bigquery

    project_id = (
        os.getenv("TIDINGSIQ_GCP_PROJECT")
        or os.getenv("BRUIN_PROJECT_ID")
        or os.getenv("GOOGLE_CLOUD_PROJECT")
    )
    if not project_id:
        raise RuntimeError(
            "TIDINGSIQ_GCP_PROJECT, BRUIN_PROJECT_ID, or GOOGLE_CLOUD_PROJECT must be set."
        )

    gold_feed_table_fqn = os.getenv(
        "TIDINGSIQ_GOLD_FEED_TABLE", f"{project_id}.gold.positive_news_feed"
    )
    metrics_table_fqn = os.getenv(
        "TIDINGSIQ_GOLD_METRICS_TABLE", f"{project_id}.gold.pipeline_run_metrics"
    )

    client = bigquery.Client(project=project_id)
    latest_metrics = fetch_latest_metrics(client, metrics_table_fqn)
    exclusion_counts = fetch_exclusion_counts(client, gold_feed_table_fqn)
    report = build_report_payload(
        latest_metrics=latest_metrics,
        exclusion_counts=exclusion_counts,
    )

    print(json.dumps(report, sort_keys=True))
    print(build_summary_line(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
