from __future__ import annotations

from datetime import datetime, timezone
import unittest

from scripts.daily_pipeline_report import (
    SUMMARY_MARKER,
    build_report_payload,
    build_summary_line,
    determine_action_needed,
)


class DailyPipelineReportTest(unittest.TestCase):
    def test_determine_action_needed_healthy(self) -> None:
        now = datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc)
        latest_gold_ingested_at = datetime(2026, 4, 7, 4, 30, tzinfo=timezone.utc)

        action = determine_action_needed(
            latest_gold_ingested_at=latest_gold_ingested_at,
            gold_row_count=628,
            eligible_row_count=72,
            bronze_window_is_complete=True,
            now_utc=now,
        )

        self.assertEqual(action, "healthy")

    def test_empty_attempt_overrides_fresh_gold_health(self):
        now = datetime(2026, 9, 29, 6, tzinfo=timezone.utc)
        payload = build_report_payload(
            latest_metrics={
                "audit_run_at": now, "latest_gold_ingested_at": now,
                "gold_row_count": 100,
                "latest_bronze_ingestion_is_complete": False,
                "latest_bronze_ingestion_expected_file_count": 4,
                "latest_bronze_ingestion_downloaded_file_count": 0,
            },
            exclusion_counts={"eligible": 100}, generated_at=now,
        )
        self.assertEqual(payload["bronze_window_status"], "empty")
        self.assertEqual(payload["action_needed"], "gdelt_window_empty")
        self.assertIn("bronze_files=0/4", build_summary_line(payload))

    def test_no_live_ingestion_is_unknown_instead_of_healthy(self):
        now = datetime(2026, 9, 29, 6, tzinfo=timezone.utc)
        self.assertEqual(determine_action_needed(
            latest_gold_ingested_at=now, gold_row_count=100,
            eligible_row_count=100, bronze_window_is_complete=None, now_utc=now,
        ), "gdelt_window_unknown")

    def test_determine_action_needed_flags_stale_feed(self) -> None:
        now = datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc)
        latest_gold_ingested_at = datetime(2026, 4, 6, 10, 0, tzinfo=timezone.utc)

        action = determine_action_needed(
            latest_gold_ingested_at=latest_gold_ingested_at,
            gold_row_count=628,
            eligible_row_count=72,
            now_utc=now,
        )

        self.assertEqual(action, "gold_stale")

    def test_determine_action_needed_flags_third_low_volume_window(self) -> None:
        now = datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc)

        action = determine_action_needed(
            latest_gold_ingested_at=datetime(2026, 4, 7, 6, 0, tzinfo=timezone.utc),
            gold_row_count=628,
            eligible_row_count=72,
            bronze_window_is_complete=True,
            consecutive_complete_low_volume_run_count=3,
            now_utc=now,
        )

        self.assertEqual(action, "gdelt_low_volume_failure")

    def test_determine_action_needed_flags_partial_before_low_volume_warning(self) -> None:
        now = datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc)

        action = determine_action_needed(
            latest_gold_ingested_at=datetime(2026, 4, 7, 6, 0, tzinfo=timezone.utc),
            gold_row_count=628,
            eligible_row_count=72,
            bronze_window_is_complete=False,
            consecutive_complete_low_volume_run_count=1,
            now_utc=now,
        )

        self.assertEqual(action, "gdelt_window_partial")

    def test_determine_action_needed_enforces_full_precedence_contract(self) -> None:
        now = datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc)
        fresh = datetime(2026, 4, 7, 6, 0, tzinfo=timezone.utc)
        stale = datetime(2026, 4, 6, 6, 0, tzinfo=timezone.utc)
        scenarios = [
            ("gold_empty", 0, 0, stale, False, 3),
            ("eligible_feed_empty", 10, 0, stale, False, 3),
            ("gold_stale", 10, 1, stale, False, 3),
            ("gdelt_low_volume_failure", 10, 1, fresh, False, 3),
            ("gdelt_window_partial", 10, 1, fresh, False, 2),
            ("gdelt_low_volume_warning", 10, 1, fresh, True, 1),
            ("healthy", 10, 1, fresh, True, 0),
        ]

        for expected, gold_rows, eligible_rows, latest_gold, complete, streak in scenarios:
            with self.subTest(expected=expected):
                self.assertEqual(
                    determine_action_needed(
                        latest_gold_ingested_at=latest_gold,
                        gold_row_count=gold_rows,
                        eligible_row_count=eligible_rows,
                        bronze_window_is_complete=complete,
                        consecutive_complete_low_volume_run_count=streak,
                        now_utc=now,
                    ),
                    expected,
                )

    def test_build_report_payload_includes_counts_and_action(self) -> None:
        generated_at = datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc)
        latest_metrics = {
            "audit_run_at": datetime(2026, 4, 7, 6, 5, tzinfo=timezone.utc),
            "bronze_row_count": 644,
            "silver_row_count": 644,
            "silver_canonical_row_count": 628,
            "silver_duplicate_row_count": 16,
            "gold_row_count": 628,
            "gold_avg_happy_factor": 42.88,
            "gold_max_happy_factor": 100.0,
            "latest_gold_ingested_at": datetime(2026, 4, 7, 6, 0, tzinfo=timezone.utc),
            "latest_bronze_source_window_start": datetime(
                2026, 4, 7, 5, 15, tzinfo=timezone.utc
            ),
            "latest_bronze_source_window_end": datetime(
                2026, 4, 7, 6, 0, tzinfo=timezone.utc
            ),
            "latest_bronze_ingestion_expected_file_count": 4,
            "latest_bronze_ingestion_downloaded_file_count": 4,
            "latest_bronze_ingestion_is_complete": True,
            "latest_bronze_ingestion_low_volume": False,
            "consecutive_complete_low_volume_run_count": 0,
        }
        exclusion_counts = {
            "eligible": 72,
            "below_threshold": 449,
            "soft_deny_without_exception": 78,
        }

        payload = build_report_payload(
            latest_metrics=latest_metrics,
            exclusion_counts=exclusion_counts,
            generated_at=generated_at,
        )

        self.assertEqual(payload["eligible_row_count"], 72)
        self.assertEqual(payload["ineligible_row_count"], 527)
        self.assertEqual(payload["action_needed"], "healthy")
        self.assertEqual(payload["bronze_window_status"], "complete")
        self.assertEqual(payload["bronze_files_downloaded"], 4)
        self.assertEqual(payload["top_exclusions"][0]["bucket"], "below_threshold")

    def test_build_summary_line_contains_marker_and_key_counts(self) -> None:
        report = {
            "generated_at": "2026-04-07T12:00:00+00:00",
            "latest_run_at": "2026-04-07T06:05:00+00:00",
            "bronze_window_status": "complete",
            "bronze_files_downloaded": 4,
            "bronze_files_expected": 4,
            "bronze_low_volume": False,
            "bronze_low_volume_streak": 0,
            "bronze_row_count": 644,
            "silver_row_count": 644,
            "silver_canonical_row_count": 628,
            "silver_duplicate_row_count": 16,
            "gold_row_count": 628,
            "eligible_row_count": 72,
            "ineligible_row_count": 556,
            "gold_avg_happy_factor": 42.88,
            "gold_max_happy_factor": 100.0,
            "top_exclusions": [
                {"bucket": "below_threshold", "rows": 449},
                {"bucket": "soft_deny_without_exception", "rows": 78},
            ],
            "action_needed": "healthy",
        }

        line = build_summary_line(report)

        self.assertIn(SUMMARY_MARKER, line)
        self.assertIn("eligible=72", line)
        self.assertIn("bronze_files=4/4", line)
        self.assertIn("top_exclusions=below_threshold:449,soft_deny_without_exception:78", line)


if __name__ == "__main__":
    unittest.main()
