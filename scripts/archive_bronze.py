from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone


DEFAULT_SOURCE_TABLE = "bronze.gdelt_news_raw"
DEFAULT_RETENTION_DAYS = 45
DEFAULT_MAX_DELETE_ROWS = 20_000
SUMMARY_MARKER = "BRONZE_ARCHIVE_SUMMARY"
EXPORTED_ROWS_TEMP_TABLE = "archive_export"


@dataclass(frozen=True)
class BronzeArchiveConfig:
    project_id: str
    archive_uri_prefix: str
    source_table: str = DEFAULT_SOURCE_TABLE
    retention_days: int = DEFAULT_RETENTION_DAYS
    delete_after_export: bool = False
    dry_run: bool = False
    max_delete_rows: int = DEFAULT_MAX_DELETE_ROWS
    run_date: date | None = None
    cutoff_timestamp: datetime | None = None
    run_started_at: datetime | None = None


class BronzeArchiveFailure(RuntimeError):
    def __init__(self, message: str, *, summary: dict[str, object]) -> None:
        super().__init__(message)
        self.summary = summary


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
    utc_value = _as_utc(value)
    return utc_value.strftime("%Y-%m-%d %H:%M:%S+00:00")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def _parse_iso_datetime(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    return _as_utc(datetime.fromisoformat(normalized))


def _parse_run_date(value: str) -> date:
    return date.fromisoformat(value.strip())


def resolve_cutoff_timestamp(
    *,
    retention_days: int,
    run_started_at: datetime,
    run_date: date | None = None,
    cutoff_timestamp: datetime | None = None,
) -> datetime:
    if cutoff_timestamp is not None:
        return _as_utc(cutoff_timestamp)

    effective_run_date = run_date or _as_utc(run_started_at).date()
    run_boundary = datetime.combine(effective_run_date, time.min, tzinfo=timezone.utc)
    return run_boundary - timedelta(days=retention_days)


def build_archive_uri(prefix: str, *, cutoff_timestamp: datetime) -> str:
    normalized_prefix = _normalize_gcs_prefix(prefix)
    cutoff_date = _as_utc(cutoff_timestamp).date().isoformat()
    return (
        f"{normalized_prefix}/bronze_gdelt_news_raw/"
        f"cutoff_date={cutoff_date}/*.parquet"
    )


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


def build_export_validation_sql(temp_table_name: str = EXPORTED_ROWS_TEMP_TABLE) -> str:
    return f"""
select count(*) as row_count
from `{temp_table_name}`
""".strip()


def build_delete_sql(table_fqn: str, cutoff_timestamp: datetime) -> str:
    return f"""
delete from `{table_fqn}`
where ingested_at < timestamp('{_timestamp_literal(cutoff_timestamp)}')
""".strip()


def build_summary_line(summary: dict[str, object]) -> str:
    fields = {
        "status": summary.get("status"),
        "phase_completed": summary.get("phase_completed"),
        "cutoff_timestamp": summary.get("cutoff_timestamp"),
        "archive_uri": summary.get("archive_uri"),
        "candidate_row_count": summary.get("candidate_row_count"),
        "exported_row_count": summary.get("exported_row_count"),
        "deleted_row_count": summary.get("deleted_row_count"),
        "remaining_eligible_row_count": summary.get("remaining_eligible_row_count"),
        "dry_run": summary.get("dry_run"),
        "delete_after_export": summary.get("delete_after_export"),
        "backlog_detected": summary.get("backlog_detected"),
        "error": summary.get("error"),
    }
    parts = [SUMMARY_MARKER]
    for key, value in fields.items():
        if value is None:
            value = "none"
        parts.append(f"{key}={value}")
    return " ".join(parts)


def emit_summary(summary: dict[str, object]) -> None:
    print(json.dumps(summary, sort_keys=True))
    print(build_summary_line(summary))


def _build_bigquery_query_config(bigquery_module, cutoff_timestamp: datetime):
    return bigquery_module.QueryJobConfig(
        query_parameters=[
            bigquery_module.ScalarQueryParameter(
                "cutoff_timestamp", "TIMESTAMP", cutoff_timestamp
            )
        ]
    )


def count_eligible_rows(
    client,
    bigquery_module,
    *,
    table_fqn: str,
    cutoff_timestamp: datetime,
) -> int:
    count_job = client.query(
        build_count_sql(table_fqn),
        job_config=_build_bigquery_query_config(bigquery_module, cutoff_timestamp),
    )
    return int(next(iter(count_job.result()))["row_count"])


def export_rows(
    client,
    *,
    table_fqn: str,
    archive_uri: str,
    cutoff_timestamp: datetime,
) -> None:
    client.query(build_export_sql(table_fqn, archive_uri, cutoff_timestamp)).result()


def count_exported_rows(client, bigquery_module, *, archive_uri: str) -> int:
    external_config = bigquery_module.ExternalConfig("PARQUET")
    external_config.source_uris = [archive_uri]
    validation_job = client.query(
        build_export_validation_sql(),
        job_config=bigquery_module.QueryJobConfig(
            table_definitions={EXPORTED_ROWS_TEMP_TABLE: external_config}
        ),
    )
    return int(next(iter(validation_job.result()))["row_count"])


def delete_rows(
    client,
    *,
    table_fqn: str,
    cutoff_timestamp: datetime,
) -> int:
    delete_job = client.query(build_delete_sql(table_fqn, cutoff_timestamp))
    delete_job.result()
    return int(getattr(delete_job, "num_dml_affected_rows", 0) or 0)


def _base_summary(
    *,
    config: BronzeArchiveConfig,
    table_fqn: str,
    archive_uri: str,
    cutoff_timestamp: datetime,
) -> dict[str, object]:
    return {
        "table_fqn": table_fqn,
        "archive_uri": archive_uri,
        "cutoff_timestamp": cutoff_timestamp.isoformat(),
        "candidate_row_count": 0,
        "exported_row_count": 0,
        "deleted_row_count": 0,
        "remaining_eligible_row_count": 0,
        "delete_after_export": config.delete_after_export,
        "dry_run": config.dry_run,
        "max_delete_rows": config.max_delete_rows,
        "status": "pending",
        "phase_completed": "initializing",
        "backlog_detected": False,
    }


def _fail(summary: dict[str, object], *, error: str, phase_completed: str) -> BronzeArchiveFailure:
    failed_summary = dict(summary)
    failed_summary["status"] = "failed"
    failed_summary["phase_completed"] = phase_completed
    failed_summary["error"] = error
    return BronzeArchiveFailure(error, summary=failed_summary)


def build_unhandled_failure_summary(
    config: BronzeArchiveConfig,
    error: Exception,
) -> dict[str, object]:
    archive_uri = "none"
    cutoff_timestamp_value = "none"
    table_fqn = "none"

    try:
        now_utc = _as_utc(config.run_started_at or datetime.now(timezone.utc))
        cutoff_timestamp = resolve_cutoff_timestamp(
            retention_days=config.retention_days,
            run_started_at=now_utc,
            run_date=config.run_date,
            cutoff_timestamp=config.cutoff_timestamp,
        )
        cutoff_timestamp_value = cutoff_timestamp.isoformat()
        archive_uri = build_archive_uri(
            config.archive_uri_prefix,
            cutoff_timestamp=cutoff_timestamp,
        )
        table_fqn = _table_fqn(config.project_id, config.source_table)
    except Exception:
        pass

    return {
        "table_fqn": table_fqn,
        "archive_uri": archive_uri,
        "cutoff_timestamp": cutoff_timestamp_value,
        "candidate_row_count": 0,
        "exported_row_count": 0,
        "deleted_row_count": 0,
        "remaining_eligible_row_count": 0,
        "delete_after_export": config.delete_after_export,
        "dry_run": config.dry_run,
        "max_delete_rows": config.max_delete_rows,
        "status": "failed",
        "phase_completed": "unhandled_error",
        "backlog_detected": False,
        "error": str(error),
    }


def archive_bronze(
    config: BronzeArchiveConfig,
    *,
    client=None,
    bigquery_module=None,
) -> dict[str, object]:
    if client is None or bigquery_module is None:
        from google.cloud import bigquery as imported_bigquery

        bigquery_module = bigquery_module or imported_bigquery
        client = client or imported_bigquery.Client(project=config.project_id)

    now_utc = _as_utc(config.run_started_at or datetime.now(timezone.utc))
    cutoff_timestamp = resolve_cutoff_timestamp(
        retention_days=config.retention_days,
        run_started_at=now_utc,
        run_date=config.run_date,
        cutoff_timestamp=config.cutoff_timestamp,
    )
    table_fqn = _table_fqn(config.project_id, config.source_table)
    archive_uri = build_archive_uri(
        config.archive_uri_prefix,
        cutoff_timestamp=cutoff_timestamp,
    )
    summary = _base_summary(
        config=config,
        table_fqn=table_fqn,
        archive_uri=archive_uri,
        cutoff_timestamp=cutoff_timestamp,
    )

    candidate_row_count = count_eligible_rows(
        client,
        bigquery_module,
        table_fqn=table_fqn,
        cutoff_timestamp=cutoff_timestamp,
    )
    summary["candidate_row_count"] = candidate_row_count
    summary["phase_completed"] = "counted"

    if config.dry_run:
        summary["status"] = "dry_run"
        summary["backlog_detected"] = candidate_row_count > 0
        return summary

    if candidate_row_count == 0:
        summary["status"] = "noop"
        return summary

    export_rows(
        client,
        table_fqn=table_fqn,
        archive_uri=archive_uri,
        cutoff_timestamp=cutoff_timestamp,
    )
    summary["phase_completed"] = "exported"

    exported_row_count = count_exported_rows(
        client,
        bigquery_module,
        archive_uri=archive_uri,
    )
    summary["exported_row_count"] = exported_row_count

    if exported_row_count != candidate_row_count:
        raise _fail(
            summary,
            error=(
                "exported_row_count did not match candidate_row_count "
                f"({exported_row_count} != {candidate_row_count})"
            ),
            phase_completed="exported",
        )

    if not config.delete_after_export:
        summary["status"] = "export_only"
        summary["backlog_detected"] = candidate_row_count > 0
        return summary

    if candidate_row_count > config.max_delete_rows:
        raise _fail(
            summary,
            error=(
                "candidate_row_count exceeded max_delete_rows "
                f"({candidate_row_count} > {config.max_delete_rows})"
            ),
            phase_completed="exported",
        )

    deleted_row_count = delete_rows(
        client,
        table_fqn=table_fqn,
        cutoff_timestamp=cutoff_timestamp,
    )
    summary["deleted_row_count"] = deleted_row_count
    summary["phase_completed"] = "deleted"

    remaining_eligible_row_count = count_eligible_rows(
        client,
        bigquery_module,
        table_fqn=table_fqn,
        cutoff_timestamp=cutoff_timestamp,
    )
    summary["remaining_eligible_row_count"] = remaining_eligible_row_count
    summary["backlog_detected"] = remaining_eligible_row_count > 0

    if deleted_row_count != candidate_row_count:
        raise _fail(
            summary,
            error=(
                "deleted_row_count did not match candidate_row_count "
                f"({deleted_row_count} != {candidate_row_count})"
            ),
            phase_completed="deleted",
        )

    if remaining_eligible_row_count != 0:
        raise _fail(
            summary,
            error=(
                "remaining_eligible_row_count was not zero after delete "
                f"({remaining_eligible_row_count})"
            ),
            phase_completed="deleted",
        )

    summary["status"] = "deleted"
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
        help="Count eligible rows and emit the intended archive target without exporting.",
    )
    parser.add_argument(
        "--max-delete-rows",
        type=int,
        default=DEFAULT_MAX_DELETE_ROWS,
        help="Abort before delete if the eligible row count exceeds this threshold.",
    )
    cutoff_group = parser.add_mutually_exclusive_group()
    cutoff_group.add_argument(
        "--run-date",
        help="UTC run date in YYYY-MM-DD form used to derive a stable daily cutoff boundary.",
    )
    cutoff_group.add_argument(
        "--cutoff-timestamp",
        help="Explicit UTC cutoff timestamp override in ISO 8601 form.",
    )
    args = parser.parse_args()

    if args.retention_days <= 0:
        raise ValueError("retention_days must be positive")
    if args.max_delete_rows <= 0:
        raise ValueError("max_delete_rows must be positive")

    return BronzeArchiveConfig(
        project_id=args.project_id,
        archive_uri_prefix=args.archive_uri_prefix,
        source_table=args.source_table,
        retention_days=args.retention_days,
        delete_after_export=args.delete_after_export,
        dry_run=args.dry_run,
        max_delete_rows=args.max_delete_rows,
        run_date=_parse_run_date(args.run_date) if args.run_date else None,
        cutoff_timestamp=_parse_iso_datetime(args.cutoff_timestamp)
        if args.cutoff_timestamp
        else None,
    )


def main() -> int:
    config = parse_args()

    try:
        summary = archive_bronze(config)
    except BronzeArchiveFailure as exc:
        emit_summary(exc.summary)
        return 1
    except Exception as exc:
        emit_summary(build_unhandled_failure_summary(config, exc))
        return 1

    emit_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
