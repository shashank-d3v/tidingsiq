from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.streamlit.query_builder import (
    FeedQueryConfig,
    build_feed_query,
    summarize_feed,
)


class QueryBuilderTest(unittest.TestCase):
    def test_build_feed_query_clamps_with_eligibility_filter(self) -> None:
        sql, parameters = build_feed_query(
            FeedQueryConfig(
                table_fqn="tidingsiq-dev.gold.positive_news_feed",
                min_happy_factor=130,
                lookback_days=90,
                row_limit=500,
                eligible_only=True,
            ),
            now_utc=datetime(2026, 4, 2, 0, 0, tzinfo=timezone.utc),
        )

        parameter_map = {name: value for name, _, value in parameters}

        self.assertIn("serving_date >= date(@published_after)", sql)
        self.assertIn("is_positive_feed_eligible = true", sql)
        self.assertEqual(parameter_map["min_happy_factor"], 100.0)
        self.assertEqual(parameter_map["row_limit"], 100)
        self.assertEqual(
            parameter_map["published_after"],
            datetime(2026, 3, 3, 0, 0, tzinfo=timezone.utc),
        )

    def test_build_feed_query_has_no_language_parameter(self) -> None:
        sql, parameters = build_feed_query(
            FeedQueryConfig(table_fqn="tidingsiq-dev.gold.positive_news_feed")
        )

        parameter_names = [name for name, _, _ in parameters]

        self.assertNotIn("language", sql.lower())
        self.assertNotIn("language", parameter_names)

    def test_build_feed_query_can_disable_eligibility_filter(self) -> None:
        sql, _ = build_feed_query(
            FeedQueryConfig(
                table_fqn="tidingsiq-dev.gold.positive_news_feed",
                eligible_only=False,
            )
        )

        self.assertNotIn("is_positive_feed_eligible = true", sql)

    def test_summarize_feed_returns_expected_metrics(self) -> None:
        summary = summarize_feed(
            [
                {"happy_factor": 72.5, "source_name": "Source A"},
                {"happy_factor": 81.0, "source_name": "Source B"},
                {"happy_factor": 64.0, "source_name": "Source A"},
            ]
        )

        self.assertEqual(summary["row_count"], 3)
        self.assertEqual(summary["avg_happy_factor"], 72.5)
        self.assertEqual(summary["max_happy_factor"], 81.0)
        self.assertEqual(summary["source_count"], 2)


if __name__ == "__main__":
    unittest.main()
