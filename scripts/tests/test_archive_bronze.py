from __future__ import annotations

import unittest
from datetime import date, datetime, timezone

from scripts.archive_bronze import (
    BronzeArchiveConfig,
    BronzeArchiveFailure,
    SUMMARY_MARKER,
    archive_bronze,
    build_archive_uri,
    build_count_sql,
    build_delete_sql,
    build_export_sql,
    build_summary_line,
    resolve_cutoff_timestamp,
)


class FakeQueryJob:
    def __init__(
        self,
        rows: list[dict[str, object]] | None = None,
        *,
        num_dml_affected_rows: int | None = None,
    ) -> None:
        self._rows = rows or []
        self.num_dml_affected_rows = num_dml_affected_rows

    def result(self) -> list[dict[str, object]]:
        return self._rows


class FakeClient:
    def __init__(self, jobs: list[FakeQueryJob]) -> None:
        self.jobs = list(jobs)
        self.queries: list[dict[str, object]] = []

    def query(self, sql: str, job_config=None):
        self.queries.append({"sql": sql, "job_config": job_config})
        if not self.jobs:
            raise AssertionError("No fake query job configured for query.")
        return self.jobs.pop(0)


class FakeScalarQueryParameter:
    def __init__(self, name: str, param_type: str, value: object) -> None:
        self.name = name
        self.param_type = param_type
        self.value = value


class FakeQueryJobConfig:
    def __init__(self, query_parameters=None, table_definitions=None) -> None:
        self.query_parameters = query_parameters or []
        self.table_definitions = table_definitions or {}


class FakeExternalConfig:
    def __init__(self, source_format: str) -> None:
        self.source_format = source_format
        self.source_uris: list[str] = []


class FakeBigQueryModule:
    ScalarQueryParameter = FakeScalarQueryParameter
    QueryJobConfig = FakeQueryJobConfig
    ExternalConfig = FakeExternalConfig


class ArchiveBronzeTest(unittest.TestCase):
    def test_build_archive_uri_uses_cutoff_date_partition(self) -> None:
        uri = build_archive_uri(
            "gs://example-bronze-archive/automated",
            cutoff_timestamp=datetime(2026, 2, 26, 0, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(
            uri,
            "gs://example-bronze-archive/automated/bronze_gdelt_news_raw/cutoff_date=2026-02-26/*.parquet",
        )

    def test_build_count_sql_targets_ingested_at_cutoff(self) -> None:
        sql = build_count_sql("example-project.bronze.gdelt_news_raw")

        self.assertIn("from `example-project.bronze.gdelt_news_raw`", sql.lower())
        self.assertIn("where ingested_at < @cutoff_timestamp", sql.lower())

    def test_build_export_sql_uses_export_data_statement(self) -> None:
        sql = build_export_sql(
            "example-project.bronze.gdelt_news_raw",
            "gs://bucket/automated/*.parquet",
            datetime(2026, 2, 1, tzinfo=timezone.utc),
        )

        self.assertIn("export data options(", sql.lower())
        self.assertIn("format='PARQUET'".lower(), sql.lower())
        self.assertIn(
            "where ingested_at < timestamp('2026-02-01 00:00:00+00:00')",
            sql.lower(),
        )

    def test_build_delete_sql_targets_same_cutoff(self) -> None:
        sql = build_delete_sql(
            "example-project.bronze.gdelt_news_raw",
            datetime(2026, 2, 1, tzinfo=timezone.utc),
        )

        self.assertIn("delete from `example-project.bronze.gdelt_news_raw`", sql.lower())
        self.assertIn(
            "where ingested_at < timestamp('2026-02-01 00:00:00+00:00')",
            sql.lower(),
        )

    def test_resolve_cutoff_timestamp_uses_start_of_run_day(self) -> None:
        cutoff_timestamp = resolve_cutoff_timestamp(
            retention_days=45,
            run_started_at=datetime(2026, 4, 12, 12, 34, tzinfo=timezone.utc),
        )

        self.assertEqual(
            cutoff_timestamp,
            datetime(2026, 2, 26, 0, 0, tzinfo=timezone.utc),
        )

    def test_resolve_cutoff_timestamp_uses_explicit_run_date(self) -> None:
        cutoff_timestamp = resolve_cutoff_timestamp(
            retention_days=45,
            run_started_at=datetime(2026, 4, 12, 12, 34, tzinfo=timezone.utc),
            run_date=date(2026, 4, 15),
        )

        self.assertEqual(
            cutoff_timestamp,
            datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc),
        )

    def test_build_summary_line_emits_marker_and_guardrails(self) -> None:
        line = build_summary_line(
            {
                "status": "deleted",
                "phase_completed": "deleted",
                "cutoff_timestamp": "2026-02-26T00:00:00+00:00",
                "archive_uri": "gs://bucket/path/*.parquet",
                "candidate_row_count": 3,
                "exported_row_count": 3,
                "deleted_row_count": 3,
                "remaining_eligible_row_count": 0,
                "dry_run": False,
                "delete_after_export": True,
                "backlog_detected": False,
            }
        )

        self.assertIn(SUMMARY_MARKER, line)
        self.assertIn("status=deleted", line)
        self.assertIn("remaining_eligible_row_count=0", line)
        self.assertIn("delete_after_export=True", line)

    def test_archive_bronze_dry_run_skips_export_and_delete(self) -> None:
        client = FakeClient([FakeQueryJob([{"row_count": 4}])])
        summary = archive_bronze(
            BronzeArchiveConfig(
                project_id="example-project",
                archive_uri_prefix="gs://bucket/automated",
                dry_run=True,
                run_started_at=datetime(2026, 4, 12, 12, 34, tzinfo=timezone.utc),
            ),
            client=client,
            bigquery_module=FakeBigQueryModule,
        )

        self.assertEqual(summary["status"], "dry_run")
        self.assertEqual(summary["candidate_row_count"], 4)
        self.assertEqual(summary["phase_completed"], "counted")
        self.assertEqual(len(client.queries), 1)

    def test_archive_bronze_deletes_after_successful_reconciliation(self) -> None:
        client = FakeClient(
            [
                FakeQueryJob([{"row_count": 3}]),
                FakeQueryJob(),
                FakeQueryJob([{"row_count": 3}]),
                FakeQueryJob(num_dml_affected_rows=3),
                FakeQueryJob([{"row_count": 0}]),
            ]
        )

        summary = archive_bronze(
            BronzeArchiveConfig(
                project_id="example-project",
                archive_uri_prefix="gs://bucket/automated",
                delete_after_export=True,
                run_started_at=datetime(2026, 4, 12, 12, 34, tzinfo=timezone.utc),
            ),
            client=client,
            bigquery_module=FakeBigQueryModule,
        )

        self.assertEqual(summary["status"], "deleted")
        self.assertEqual(summary["candidate_row_count"], 3)
        self.assertEqual(summary["exported_row_count"], 3)
        self.assertEqual(summary["deleted_row_count"], 3)
        self.assertEqual(summary["remaining_eligible_row_count"], 0)
        self.assertFalse(summary["backlog_detected"])
        self.assertEqual(len(client.queries), 5)
        self.assertEqual(
            client.queries[2]["job_config"].table_definitions["archive_export"].source_uris,
            [
                "gs://bucket/automated/bronze_gdelt_news_raw/cutoff_date=2026-02-26/*.parquet"
            ],
        )

    def test_archive_bronze_blocks_delete_when_export_count_mismatches(self) -> None:
        client = FakeClient(
            [
                FakeQueryJob([{"row_count": 3}]),
                FakeQueryJob(),
                FakeQueryJob([{"row_count": 2}]),
            ]
        )

        with self.assertRaises(BronzeArchiveFailure) as caught:
            archive_bronze(
                BronzeArchiveConfig(
                    project_id="example-project",
                    archive_uri_prefix="gs://bucket/automated",
                    delete_after_export=True,
                    run_started_at=datetime(2026, 4, 12, 12, 34, tzinfo=timezone.utc),
                ),
                client=client,
                bigquery_module=FakeBigQueryModule,
            )

        self.assertIn("exported_row_count did not match", str(caught.exception))
        self.assertEqual(caught.exception.summary["status"], "failed")
        self.assertEqual(caught.exception.summary["phase_completed"], "exported")
        self.assertEqual(len(client.queries), 3)

    def test_archive_bronze_blocks_delete_when_threshold_is_exceeded(self) -> None:
        client = FakeClient(
            [
                FakeQueryJob([{"row_count": 25_000}]),
                FakeQueryJob(),
                FakeQueryJob([{"row_count": 25_000}]),
            ]
        )

        with self.assertRaises(BronzeArchiveFailure) as caught:
            archive_bronze(
                BronzeArchiveConfig(
                    project_id="example-project",
                    archive_uri_prefix="gs://bucket/automated",
                    delete_after_export=True,
                    max_delete_rows=20_000,
                    run_started_at=datetime(2026, 4, 12, 12, 34, tzinfo=timezone.utc),
                ),
                client=client,
                bigquery_module=FakeBigQueryModule,
            )

        self.assertIn("candidate_row_count exceeded max_delete_rows", str(caught.exception))
        self.assertEqual(caught.exception.summary["phase_completed"], "exported")
        self.assertEqual(len(client.queries), 3)

    def test_archive_bronze_fails_when_rows_remain_after_delete(self) -> None:
        client = FakeClient(
            [
                FakeQueryJob([{"row_count": 3}]),
                FakeQueryJob(),
                FakeQueryJob([{"row_count": 3}]),
                FakeQueryJob(num_dml_affected_rows=3),
                FakeQueryJob([{"row_count": 1}]),
            ]
        )

        with self.assertRaises(BronzeArchiveFailure) as caught:
            archive_bronze(
                BronzeArchiveConfig(
                    project_id="example-project",
                    archive_uri_prefix="gs://bucket/automated",
                    delete_after_export=True,
                    run_started_at=datetime(2026, 4, 12, 12, 34, tzinfo=timezone.utc),
                ),
                client=client,
                bigquery_module=FakeBigQueryModule,
            )

        self.assertEqual(caught.exception.summary["remaining_eligible_row_count"], 1)
        self.assertTrue(caught.exception.summary["backlog_detected"])


if __name__ == "__main__":
    unittest.main()
