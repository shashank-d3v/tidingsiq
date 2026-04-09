from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.streamlit.query_builder import (
    FeedQueryConfig,
    build_eligibility_breakdown,
    build_feed_query,
    build_score_distribution,
    build_source_rankings,
    build_timeline_data,
    dedupe_story_rows,
    paginate_rows,
    split_feed_rows,
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
        self.assertEqual(parameter_map["row_limit"], 200)
        self.assertEqual(
            parameter_map["published_after"],
            datetime(2026, 3, 3, 0, 0, tzinfo=timezone.utc),
        )
        self.assertIn("language", sql.lower())
        self.assertIn("mentioned_country_name", sql.lower())
        self.assertIn("exclusion_reason", sql.lower())

    def test_build_feed_query_has_metadata_columns_but_no_metadata_parameters(self) -> None:
        sql, parameters = build_feed_query(
            FeedQueryConfig(table_fqn="tidingsiq-dev.gold.positive_news_feed")
        )

        parameter_names = [name for name, _, _ in parameters]

        self.assertIn("language", sql.lower())
        self.assertIn("mentioned_country_name", sql.lower())
        self.assertNotIn("language", parameter_names)

    def test_build_feed_query_falls_back_for_missing_optional_metadata_columns(self) -> None:
        sql, _ = build_feed_query(
            FeedQueryConfig(table_fqn="tidingsiq-dev.gold.positive_news_feed"),
            available_columns={
                "source_record_id",
                "article_id",
                "serving_date",
                "published_at",
                "source_name",
                "title",
                "url",
                "tone_score",
                "base_happy_factor",
                "happy_factor",
                "happy_factor_version",
                "is_positive_feed_eligible",
                "positive_guardrail_version",
                "exclusion_reason",
                "allow_hit_count",
                "soft_deny_hit_count",
                "hard_deny_hit_count",
                "ingested_at",
            },
        )

        self.assertIn("cast(null as string) as language", sql.lower())
        self.assertIn("cast(null as string) as mentioned_country_name", sql.lower())

    def test_build_feed_query_can_disable_eligibility_filter(self) -> None:
        sql, _ = build_feed_query(
            FeedQueryConfig(
                table_fqn="tidingsiq-dev.gold.positive_news_feed",
                eligible_only=False,
            )
        )

        self.assertIn("with recommended as", sql.lower())
        self.assertIn("exclusion_reason = 'below_threshold'", sql.lower())

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

    def test_split_feed_rows_separates_recommended_and_more_to_explore(self) -> None:
        recommended, more_to_explore = split_feed_rows(
            [
                {"article_id": "a", "is_positive_feed_eligible": True},
                {
                    "article_id": "b",
                    "is_positive_feed_eligible": False,
                    "exclusion_reason": "below_threshold",
                },
                {
                    "article_id": "c",
                    "is_positive_feed_eligible": False,
                    "exclusion_reason": "hard_deny_term",
                },
            ]
        )

        self.assertEqual([row["article_id"] for row in recommended], ["a"])
        self.assertEqual([row["article_id"] for row in more_to_explore], ["b"])

    def test_dedupe_story_rows_keeps_first_story_variant(self) -> None:
        deduped = dedupe_story_rows(
            [
                {
                    "article_id": "a",
                    "source_name": "iheart.com",
                    "title": "Jennifer Lopez Celebrates 'New Beginnings' With Easter Selfies",
                },
                {
                    "article_id": "b",
                    "source_name": "iheart.com",
                    "title": "Jennifer Lopez Celebrates 'New Beginnings' With Easter Selfies | Magic 107.7.",
                },
                {
                    "article_id": "c",
                    "source_name": "justjared.com",
                    "title": (
                        "Netflix Launches Interactive Playground App for Kids to Play Games & Explore "
                        "with Beloved Characters: Photo 5304735 | Dr Seuss, Ms. Rachel, Netflix, "
                        "Peppa Pig, Sesame Street Photos"
                    ),
                },
                {
                    "article_id": "d",
                    "source_name": "justjared.com",
                    "title": (
                        "Netflix Launches Interactive Playground App for Kids to Play Games & Explore "
                        "with Beloved Characters: Photo 5304749 | Dr Seuss, Ms. Rachel, Netflix, "
                        "Peppa Pig, Sesame Street Photos"
                    ),
                },
                {"article_id": "e", "source_name": "Source B", "title": "Different"},
            ]
        )

        self.assertEqual([row["article_id"] for row in deduped], ["a", "c", "e"])

    def test_build_timeline_data_aggregates_story_and_eligibility_counts(self) -> None:
        timeline = build_timeline_data(
            [
                {
                    "serving_date": "2026-04-01",
                    "is_positive_feed_eligible": True,
                    "happy_factor": 80.0,
                },
                {
                    "serving_date": "2026-04-01",
                    "is_positive_feed_eligible": False,
                    "happy_factor": 60.0,
                },
                {
                    "serving_date": "2026-04-02",
                    "is_positive_feed_eligible": True,
                    "happy_factor": 70.0,
                },
            ]
        )

        self.assertEqual(
            timeline,
            [
                {
                    "serving_date": "2026-04-01",
                    "story_count": 2,
                    "eligible_count": 1,
                    "avg_happy_factor": 70.0,
                },
                {
                    "serving_date": "2026-04-02",
                    "story_count": 1,
                    "eligible_count": 1,
                    "avg_happy_factor": 70.0,
                },
            ],
        )

    def test_build_source_rankings_uses_only_eligible_rows(self) -> None:
        rankings = build_source_rankings(
            [
                {
                    "source_name": "Source A",
                    "is_positive_feed_eligible": True,
                    "happy_factor": 80.0,
                },
                {
                    "source_name": "Source A",
                    "is_positive_feed_eligible": True,
                    "happy_factor": 70.0,
                },
                {
                    "source_name": "Source B",
                    "is_positive_feed_eligible": False,
                    "happy_factor": 95.0,
                },
            ]
        )

        self.assertEqual(
            rankings,
            [
                {
                    "source_name": "Source A",
                    "story_count": 2,
                    "avg_happy_factor": 75.0,
                }
            ],
        )

    def test_build_score_distribution_includes_below_threshold_bucket(self) -> None:
        distribution = build_score_distribution(
            [
                {"happy_factor": 62.0},
                {"happy_factor": 68.0},
                {"happy_factor": 72.0},
                {"happy_factor": 88.0},
            ]
        )

        self.assertEqual(
            distribution,
            [
                {"bucket": "Below 65", "story_count": 1},
                {"bucket": "65-70", "story_count": 1},
                {"bucket": "70-75", "story_count": 1},
                {"bucket": "75-80", "story_count": 0},
                {"bucket": "80-85", "story_count": 0},
                {"bucket": "85+", "story_count": 1},
            ],
        )

    def test_build_eligibility_breakdown_counts_all_reason_buckets(self) -> None:
        breakdown = build_eligibility_breakdown(
            [
                {"is_positive_feed_eligible": True, "exclusion_reason": None},
                {
                    "is_positive_feed_eligible": False,
                    "exclusion_reason": "below_threshold",
                },
                {
                    "is_positive_feed_eligible": False,
                    "exclusion_reason": "hard_deny_term",
                },
            ]
        )

        self.assertEqual(
            breakdown,
            [
                {"bucket": "Eligible", "story_count": 1},
                {"bucket": "Below Threshold", "story_count": 1},
                {"bucket": "Hard Deny Term", "story_count": 1},
                {"bucket": "Soft Deny Without Exception", "story_count": 0},
                {"bucket": "Missing Title", "story_count": 0},
                {"bucket": "Missing URL", "story_count": 0},
            ],
        )

    def test_paginate_rows_clamps_out_of_range_page(self) -> None:
        page_rows, current_page, total_pages, total_rows = paginate_rows(
            [{"id": str(i)} for i in range(11)],
            page_number=9,
            page_size=10,
        )

        self.assertEqual(total_rows, 11)
        self.assertEqual(total_pages, 2)
        self.assertEqual(current_page, 2)
        self.assertEqual(page_rows, [{"id": "10"}])


if __name__ == "__main__":
    unittest.main()
