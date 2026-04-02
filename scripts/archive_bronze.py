from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


DEFAULT_SOURCE_TABLE = "bronze.gdelt_news_raw"
DEFAULT_RETENTION_DAYS = 45


@dataclass(frozen=True)
class BronzeArchiveConfig:
    project_id: str
    archive_uri_prefix: str
    source_table: str = DEFAULT_SOURCE_TABLE
    retention_days: int = DEFAULT_RETENTION_DAYS
    delete_after_export: bool = False
    dry_run: bool = False


def _normalize_gcs_prefix(value: str) -> str:
    normalized = value.strip().rstrip("/")
    if not normalized.startswith("gs://"):
        raise ValueError("archive_uri_prefix must start with gs://")
    return normalized


def _table_fqn(project_id: str, source_table: str) -> str:
    normalized = source_table.strip().strip("`")
    if normalized.count(".") == 1:
        return f"{project_id}.{normalized}"
    if normalized.count(".") == 2:
        return normalized
    raise ValueError("source_table must be dataset.table or project.dataset.table")


def _timestamp_literal(value: datetime) -> str:
    utc_value = value.astimezone(timezone.utc)
    return utc_value.strftime("%Y-%m-%d %H:%M:%S+00:00")


def build_archive_uri(prefix: str, *, run_started_at: datetime) -> str:
    normalized_prefix = _normalize_gcs_prefix(prefix)
    run_id = run_started_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{normalized_prefix}/bronze_gdelt_news_raw/exported_at={run_id}/*.parquet"


def build_count_sql(table_fqn: str) -> str:
    return f"""
select count(*) as row_count
from `{table_fqn}`
where ingested_at < @cutoff_timestamp
""".strip()


def build_export_sql(table_fqn: str, archive_uri: str, cutoff_timestamp: datetime) -> str:
    return f"""
export data options(
  uri='{archive_uri}',
  format='PARQUET',
  overwrite=true
) as
select *
from `{table_fqn}`
where ingested_at < timestamp('{_timestamp_literal(cutoff_timestamp)}')
""".strip()


def build_delete_sql(table_fqn: str, cutoff_timestamp: datetime) -> str:
    return f"""
delete from `{table_fqn}`
where ingested_at < timestamp('{_timestamp_literal(cutoff_timestamp)}')
""".strip()


def archive_bronze(config: BronzeArchiveConfig) -> dict[str, object]:
    from google.cloud import bigquery

    now_utc = datetime.now(timezone.utc)
    cutoff_timestamp = now_utc - timedelta(days=config.retention_days)
    table_fqn = _table_fqn(config.project_id, config.source_table)
    archive_uri = build_archive_uri(config.archive_uri_prefix, run_started_at=now_utc)

    client = bigquery.Client(project=config.project_id)
    count_job = client.query(
        build_count_sql(table_fqn),
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter(
                    "cutoff_timestamp", "TIMESTAMP", cutoff_timestamp
                )
            ]
        ),
    )
    row_count = int(next(iter(count_job.result()))["row_count"])

    summary = {
        "table_fqn": table_fqn,
        "archive_uri": archive_uri,
        "cutoff_timestamp": cutoff_timestamp.isoformat(),
        "row_count": row_count,
        "delete_after_export": config.delete_after_export,
        "dry_run": config.dry_run,
    }

    if config.dry_run or row_count == 0:
        return summary

    export_sql = build_export_sql(table_fqn, archive_uri, cutoff_timestamp)
    client.query(export_sql).result()

    if config.delete_after_export:
        delete_sql = build_delete_sql(table_fqn, cutoff_timestamp)
        client.query(delete_sql).result()

    return summary


def parse_args() -> BronzeArchiveConfig:
    parser = argparse.ArgumentParser(
        description="Export Bronze rows older than the retention window to GCS."
    )
    parser.add_argument("--project-id", required=True, help="Target GCP project ID.")
    parser.add_argument(
        "--archive-uri-prefix",
        required=True,
        help="GCS prefix such as gs://your-bucket/archives",
    )
    parser.add_argument(
        "--source-table",
        default=DEFAULT_SOURCE_TABLE,
        help="Bronze source table in dataset.table or project.dataset.table form.",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=DEFAULT_RETENTION_DAYS,
        help="Rows older than this many days are eligible for export.",
    )
    parser.add_argument(
        "--delete-after-export",
        action="store_true",
        help="Delete eligible Bronze rows after a successful export job.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count eligible rows and print the intended export target without exporting.",
    )
    args = parser.parse_args()

    return BronzeArchiveConfig(
        project_id=args.project_id,
        archive_uri_prefix=args.archive_uri_prefix,
        source_table=args.source_table,
        retention_days=args.retention_days,
        delete_after_export=args.delete_after_export,
        dry_run=args.dry_run,
    )


def main() -> None:
    config = parse_args()
    summary = archive_bronze(config)

    print("Bronze archive summary")
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
