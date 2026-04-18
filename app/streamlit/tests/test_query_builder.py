from __future__ import annotations

import unittest

from app.streamlit.query_builder import (
    BriefGeographyOptionsQueryConfig,
    BriefLanguageOptionsQueryConfig,
    BriefRowsQueryConfig,
    BriefScopeQueryConfig,
    FeedQueryConfig,
    build_eligibility_breakdown,
    build_feed_query,
    build_brief_geography_options_query,
    build_brief_language_options_query,
    build_brief_rows_query,
    build_brief_scope_summary_query,
    build_score_distribution,
    build_source_rankings,
    build_timeline_data,
    dedupe_story_rows,
    paginate_rows,
    summarize_feed,
)
class QueryBuilderTest(unittest.TestCase):
    def test_build_feed_query_clamps_lookback_and_row_limit(self) -> None:
        sql, parameters = build_feed_query(
            FeedQueryConfig(
                table_fqn="example-project.gold.positive_news_feed",
                lookback_days=90,
                row_limit=999,
            )
        )

        parameter_map = {name: value for name, _, value in parameters}

        self.assertIn("limit @row_limit", sql.lower())
        self.assertEqual(parameter_map["lookback_days"], 30)
        self.assertEqual(parameter_map["row_limit"], 200)

    def test_build_brief_rows_query_clamps_scope_and_applies_filters_sort_and_pagination(self) -> None:
        sql, parameters = build_brief_rows_query(
            BriefRowsQueryConfig(
                table_fqn="example-project.gold.positive_news_feed",
                lookback_days=90,
                selected_languages=("FR", "EN"),
                selected_geographies=("India", "France"),
                sort_order="Least optimistic first",
                page_number=3,
                page_size=10,
            ),
        )

        parameter_map = {parameter.name: parameter.value for parameter in parameters}

        self.assertIn('serving_date >= date_sub(current_date("utc")', sql.lower())
        self.assertIn("is_positive_feed_eligible = true", sql.lower())
        self.assertIn("selected_languages", sql)
        self.assertIn("selected_geographies", sql)
        self.assertIn("limit @page_size", sql.lower())
        self.assertIn("offset @offset_rows", sql.lower())
        self.assertIn("order by happy_factor asc", sql.lower())
        self.assertEqual(parameter_map["lookback_days"], 30)
        self.assertEqual(parameter_map["selected_languages"], ("EN", "FR"))
        self.assertEqual(parameter_map["selected_geographies"], ("France", "India"))
        self.assertEqual(parameter_map["page_size"], 10)
        self.assertEqual(parameter_map["offset_rows"], 20)

    def test_build_brief_rows_query_clamps_page_size_upper_bound(self) -> None:
        _, parameters = build_brief_rows_query(
            BriefRowsQueryConfig(
                table_fqn="example-project.gold.positive_news_feed",
                page_size=500,
            )
        )

        parameter_map = {parameter.name: parameter.value for parameter in parameters}

        self.assertEqual(parameter_map["page_size"], 200)

    def test_build_brief_rows_query_defaults_to_most_optimistic_order(self) -> None:
        sql, parameters = build_brief_rows_query(
            BriefRowsQueryConfig(
                table_fqn="example-project.gold.positive_news_feed",
                sort_order="not-a-real-option",
            )
        )

        parameter_map = {parameter.name: parameter.value for parameter in parameters}

        self.assertIn("order by happy_factor desc", sql.lower())
        self.assertEqual(parameter_map["page_size"], 10)
        self.assertEqual(parameter_map["offset_rows"], 0)

    def test_build_brief_rows_query_falls_back_for_missing_optional_metadata_columns(self) -> None:
        sql, _ = build_brief_rows_query(
            BriefRowsQueryConfig(table_fqn="example-project.gold.positive_news_feed"),
            available_columns={
                "article_id",
                "serving_date",
                "published_at",
                "source_name",
                "title",
                "url",
                "tone_score",
                "happy_factor",
                "ingested_at",
            },
        )

        self.assertIn("cast(null as string) as language", sql.lower())
        self.assertIn("cast(null as string) as mentioned_country_name", sql.lower())

    def test_build_brief_scope_summary_query_excludes_sort_and_pagination(self) -> None:
        sql, parameters = build_brief_scope_summary_query(
            BriefScopeQueryConfig(
                table_fqn="example-project.gold.positive_news_feed",
                lookback_days=7,
                selected_languages=("EN",),
                selected_geographies=("India",),
            )
        )

        parameter_names = [parameter.name for parameter in parameters]

        self.assertIn("count(*) as row_count", sql.lower())
        self.assertIn("avg_happy_factor", sql.lower())
        self.assertIn("max_happy_factor", sql.lower())
        self.assertIn("source_count", sql.lower())
        self.assertNotIn("order by", sql.lower())
        self.assertNotIn("limit", sql.lower())
        self.assertNotIn("offset", sql.lower())
        self.assertNotIn("page_size", parameter_names)
        self.assertNotIn("offset_rows", parameter_names)

    def test_build_brief_language_options_query_depends_only_on_geography_scope(self) -> None:
        sql, parameters = build_brief_language_options_query(
            BriefLanguageOptionsQueryConfig(
                table_fqn="example-project.gold.positive_news_feed",
                lookback_days=7,
                selected_geographies=("India",),
            )
        )

        parameter_names = [parameter.name for parameter in parameters]

        self.assertIn("select distinct", sql.lower())
        self.assertIn("language", sql.lower())
        self.assertIn("selected_geographies", sql)
        self.assertNotIn("selected_languages", parameter_names)
        self.assertIn("language != 'UND'".lower(), sql.lower())

    def test_build_brief_geography_options_query_depends_only_on_language_scope(self) -> None:
        sql, parameters = build_brief_geography_options_query(
            BriefGeographyOptionsQueryConfig(
                table_fqn="example-project.gold.positive_news_feed",
                lookback_days=7,
                selected_languages=("EN",),
            )
        )

        parameter_names = [parameter.name for parameter in parameters]

        self.assertIn("select distinct", sql.lower())
        self.assertIn("geography", sql.lower())
        self.assertIn("selected_languages", sql)
        self.assertNotIn("selected_geographies", parameter_names)
        self.assertIn("lower(geography) != 'unknown'", sql.lower())

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
