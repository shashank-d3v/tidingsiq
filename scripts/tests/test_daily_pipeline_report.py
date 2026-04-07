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
            now_utc=now,
        )

        self.assertEqual(action, "healthy")

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
        self.assertEqual(payload["top_exclusions"][0]["bucket"], "below_threshold")

    def test_build_summary_line_contains_marker_and_key_counts(self) -> None:
        report = {
            "generated_at": "2026-04-07T12:00:00+00:00",
            "latest_run_at": "2026-04-07T06:05:00+00:00",
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
        self.assertIn("top_exclusions=below_threshold:449,soft_deny_without_exception:78", line)


if __name__ == "__main__":
    unittest.main()
