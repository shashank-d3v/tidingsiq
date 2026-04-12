from __future__ import annotations

from pathlib import Path
import unittest


SQL_PATH = Path("pipeline/bruin/assets/gold/positive_news_feed_v3_shadow.sql")


class PositiveNewsFeedV3ShadowContractTest(unittest.TestCase):
    def test_shadow_table_keeps_app_critical_columns(self) -> None:
        sql = SQL_PATH.read_text(encoding="utf-8")

        for column_name in (
            "happy_factor",
            "is_positive_feed_eligible",
            "exclusion_reason",
            "allow_hit_count",
            "soft_deny_hit_count",
            "hard_deny_hit_count",
        ):
            self.assertIn(column_name, sql)

    def test_score_explanation_mentions_component_drivers(self) -> None:
        sql = SQL_PATH.read_text(encoding="utf-8")

        self.assertIn("score_explanation", sql)
        self.assertIn("positivity_score", sql)
        self.assertIn("suitability_score", sql)
        self.assertIn("url_quality_status", sql)
        self.assertIn("source_quality_tier", sql)


if __name__ == "__main__":
    unittest.main()
