from __future__ import annotations

import unittest
from datetime import datetime, timezone

from scripts.archive_bronze import (
    build_archive_uri,
    build_count_sql,
    build_delete_sql,
    build_export_sql,
)


class ArchiveBronzeTest(unittest.TestCase):
    def test_build_archive_uri_uses_run_timestamp(self) -> None:
        uri = build_archive_uri(
            "gs://tidingsiq-bronze-archive/manual",
            run_started_at=datetime(2026, 4, 2, 12, 30, tzinfo=timezone.utc),
        )

        self.assertEqual(
            uri,
            "gs://tidingsiq-bronze-archive/manual/bronze_gdelt_news_raw/exported_at=20260402T123000Z/*.parquet",
        )

    def test_build_count_sql_targets_ingested_at_cutoff(self) -> None:
        sql = build_count_sql("tidingsiq-dev.bronze.gdelt_news_raw")

        self.assertIn("from `tidingsiq-dev.bronze.gdelt_news_raw`", sql.lower())
        self.assertIn("where ingested_at < @cutoff_timestamp", sql.lower())

    def test_build_export_sql_uses_export_data_statement(self) -> None:
        sql = build_export_sql(
            "tidingsiq-dev.bronze.gdelt_news_raw",
            "gs://bucket/manual/*.parquet",
            datetime(2026, 2, 1, tzinfo=timezone.utc),
        )

        self.assertIn("export data options(", sql.lower())
        self.assertIn("format='PARQUET'".lower(), sql.lower())
        self.assertIn("where ingested_at < timestamp('2026-02-01 00:00:00+00:00')", sql.lower())

    def test_build_delete_sql_targets_same_cutoff(self) -> None:
        sql = build_delete_sql(
            "tidingsiq-dev.bronze.gdelt_news_raw",
            datetime(2026, 2, 1, tzinfo=timezone.utc),
        )

        self.assertIn("delete from `tidingsiq-dev.bronze.gdelt_news_raw`", sql.lower())
        self.assertIn("where ingested_at < timestamp('2026-02-01 00:00:00+00:00')", sql.lower())


if __name__ == "__main__":
    unittest.main()
