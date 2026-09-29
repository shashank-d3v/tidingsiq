"""Exercise the production metrics SELECT with small relational fixtures.

SQLite runs the common SQL subset; adapters supply BigQuery aggregate names.
This verifies result semantics without requiring credentials or warehouse writes.
"""
import pathlib
import sqlite3
import unittest


class LogicalOr:
    def __init__(self):
        self.value = None

    def step(self, value):
        if value is not None:
            self.value = bool(self.value) or bool(value)

    def finalize(self):
        return self.value


class CountIf:
    def __init__(self):
        self.value = 0

    def step(self, value):
        self.value += bool(value)

    def finalize(self):
        return self.value


class PipelineRunMetricsTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.row_factory = sqlite3.Row
        self.db.create_aggregate('logical_or', 1, LogicalOr)
        self.db.create_aggregate('countif', 1, CountIf)
        self.db.create_function('greatest', 2, lambda a, b: None if a is None or b is None else max(a, b))
        for dataset in ('bronze', 'silver', 'gold'):
            self.db.execute(f"ATTACH DATABASE ':memory:' AS {dataset}")
        self.db.executescript('''
          CREATE TABLE bronze.gdelt_news_raw (
            ingestion_id TEXT, ingested_at TEXT, source_window_start TEXT, source_window_end TEXT,
            bronze_run_accepted_row_count INT, bronze_run_malformed_ratio REAL,
            bronze_run_expected_file_count INT, bronze_run_downloaded_file_count INT,
            bronze_run_missing_file_count INT, bronze_run_is_complete INT,
            bronze_run_is_backfill INT, bronze_run_low_volume INT);
          CREATE TABLE bronze.gdelt_ingestion_attempts (
            ingestion_id TEXT, latest_ingested_at TEXT, source_window_start TEXT, source_window_end TEXT,
            accepted_row_count INT, malformed_ratio REAL, expected_file_count INT,
            downloaded_file_count INT, missing_file_count INT, is_complete INT,
            is_backfill INT, low_volume INT);
          CREATE TABLE silver.gdelt_news_refined (is_duplicate INT);
          INSERT INTO silver.gdelt_news_refined VALUES (0);
          CREATE TABLE gold.positive_news_feed (happy_factor REAL, ingested_at TEXT, published_at TEXT);
          INSERT INTO gold.positive_news_feed VALUES (80, '2026-09-29 06:00:00', '2026-09-29 04:00:00');
        ''')
        path = pathlib.Path(__file__).resolve().parents[1] / 'assets/gold/pipeline_run_metrics.sql'
        self.sql = path.read_text().split('@bruin */', 1)[1].replace('current_timestamp()', 'CURRENT_TIMESTAMP')

    def add(self, table, name, hour, *, files=4, backfill=False, low_volume=False):
        self.db.execute(f'INSERT INTO bronze.{table} VALUES ({",".join("?" for _ in range(12))})', (
            name, f'2026-09-29 {hour:02}:00:00', '2026-09-29 00:00:00', '2026-09-29 00:45:00',
            0 if files == 0 else 100, 0.0, 4, files, 4-files, files == 4, backfill, low_volume,
        ))

    def snapshot(self):
        rows = self.db.execute(self.sql).fetchall()
        self.assertEqual(len(rows), 1)
        return dict(rows[0])

    def test_backfill_only_still_emits_warehouse_snapshot(self):
        self.add('gdelt_news_raw', 'backfill', 7, backfill=True)
        row = self.snapshot()
        self.assertEqual(row['bronze_row_count'], 1)
        self.assertEqual(row['gold_row_count'], 1)
        self.assertIsNone(row['latest_bronze_ingestion_is_complete'])
        self.assertIsNone(row['latest_bronze_ingestion_accepted_row_count'])

    def test_empty_attempt_replaces_prior_complete_status(self):
        self.add('gdelt_news_raw', 'previous', 6)
        self.add('gdelt_ingestion_attempts', 'empty', 7, files=0, low_volume=None)
        row = self.snapshot()
        self.assertEqual(row['latest_bronze_ingestion_downloaded_file_count'], 0)
        self.assertEqual(row['latest_bronze_ingestion_missing_file_count'], 4)
        self.assertEqual(row['latest_bronze_ingestion_accepted_row_count'], 0)
        self.assertFalse(row['latest_bronze_ingestion_is_complete'])

    def test_later_backfill_does_not_hide_empty_live_attempt(self):
        self.add('gdelt_news_raw', 'previous', 6)
        self.add('gdelt_ingestion_attempts', 'empty', 7, files=0, low_volume=None)
        self.add('gdelt_ingestion_attempts', 'repair', 8, backfill=True)
        self.assertFalse(self.snapshot()['latest_bronze_ingestion_is_complete'])

    def test_next_success_clears_empty_status(self):
        self.add('gdelt_ingestion_attempts', 'empty', 7, files=0, low_volume=None)
        self.add('gdelt_ingestion_attempts', 'success', 8)
        self.assertTrue(self.snapshot()['latest_bronze_ingestion_is_complete'])

    def test_history_and_ledger_do_not_double_count_low_volume_runs(self):
        for name, hour in [('one', 6), ('two', 7)]:
            self.add('gdelt_news_raw', name, hour, low_volume=True)
            self.add('gdelt_ingestion_attempts', name, hour, low_volume=True)
        self.assertEqual(self.snapshot()['consecutive_complete_low_volume_run_count'], 2)

    def test_empty_warehouse_keeps_one_unknown_snapshot(self):
        row = self.snapshot()
        self.assertEqual(row['bronze_row_count'], 0)
        self.assertIsNone(row['latest_bronze_ingestion_is_complete'])
