from __future__ import annotations

import unittest

from scripts.compare_gold_score_versions import (
    SUMMARY_MARKER,
    build_broken_link_mix_sql,
    build_changed_rows_sql,
    build_domain_mix_sql,
    build_exclusion_distribution_sql,
    build_label_precision_sql,
    build_overlap_summary_sql,
    build_summary_line,
)


class CompareGoldScoreVersionsTest(unittest.TestCase):
    def test_overlap_summary_sql_counts_overlap_and_diff(self) -> None:
        sql = build_overlap_summary_sql(
            "tidingsiq-dev.gold.positive_news_feed",
            "tidingsiq-dev.gold.positive_news_feed_v3_shadow",
        )

        self.assertIn("eligible_overlap_count", sql)
        self.assertIn("newly_excluded_count", sql)
        self.assertIn("newly_included_count", sql)

    def test_changed_rows_sql_supports_both_diff_directions(self) -> None:
        include_sql = build_changed_rows_sql(
            "tidingsiq-dev.gold.positive_news_feed",
            "tidingsiq-dev.gold.positive_news_feed_v3_shadow",
            "tidingsiq-dev.silver.gdelt_news_refined",
            change_kind="newly_included",
        )
        exclude_sql = build_changed_rows_sql(
            "tidingsiq-dev.gold.positive_news_feed",
            "tidingsiq-dev.gold.positive_news_feed_v3_shadow",
            "tidingsiq-dev.silver.gdelt_news_refined",
            change_kind="newly_excluded",
        )

        self.assertIn("not current_rows.is_positive_feed_eligible", include_sql)
        self.assertIn("not shadow_rows.is_positive_feed_eligible", exclude_sql)

    def test_distribution_and_precision_queries_reference_expected_columns(self) -> None:
        self.assertIn(
            "coalesce(exclusion_reason, 'eligible')",
            build_exclusion_distribution_sql("tidingsiq-dev.gold.positive_news_feed"),
        )
        self.assertIn(
            "source_domain",
            build_domain_mix_sql(
                "tidingsiq-dev.gold.positive_news_feed_v3_shadow",
                "tidingsiq-dev.silver.gdelt_news_refined",
            ),
        )
        self.assertIn(
            "url_quality_status",
            build_broken_link_mix_sql("tidingsiq-dev.gold.positive_news_feed_v3_shadow"),
        )
        self.assertIn(
            "include_precision",
            build_label_precision_sql(
                "tidingsiq-dev.gold.positive_news_feed_v3_shadow",
                "tidingsiq-dev.gold.scoring_eval_labels",
            ),
        )

    def test_summary_line_uses_expected_marker(self) -> None:
        line = build_summary_line(
            {
                "current_eligible_count": 72,
                "shadow_eligible_count": 64,
                "eligible_overlap_count": 51,
                "newly_included_count": 13,
                "newly_excluded_count": 21,
                "current_include_precision": 0.71,
                "shadow_include_precision": 0.84,
            }
        )

        self.assertTrue(line.startswith(SUMMARY_MARKER))
        self.assertIn("shadow_include_precision=0.84", line)


if __name__ == "__main__":
    unittest.main()
