from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.streamlit.query_builder import (
    FeedQueryConfig,
    build_visible_feed_state,
    build_eligibility_breakdown,
    build_feed_query,
    build_score_distribution,
    build_source_rankings,
    build_timeline_data,
    dedupe_story_rows,
    paginate_rows,
    summarize_feed,
)


def _make_row(
    article_id: str,
    *,
    happy_factor: float,
    is_positive_feed_eligible: bool,
    exclusion_reason: str | None = None,
    serving_date: str = "2026-04-01",
    source_name: str = "Source A",
    title: str | None = None,
    tone_score: float = 1.5,
    hard_deny_hit_count: int = 0,
) -> dict[str, object]:
    return {
        "article_id": article_id,
        "source_name": source_name,
        "title": title or f"Story {article_id}",
        "url": f"https://example.com/{article_id}",
        "serving_date": serving_date,
        "happy_factor": happy_factor,
        "tone_score": tone_score,
        "hard_deny_hit_count": hard_deny_hit_count,
        "soft_deny_hit_count": 0,
        "is_positive_feed_eligible": is_positive_feed_eligible,
        "exclusion_reason": exclusion_reason,
    }


class QueryBuilderTest(unittest.TestCase):
    def test_build_feed_query_clamps_lookback_and_row_limit_for_eligible_feed(self) -> None:
        sql, parameters = build_feed_query(
            FeedQueryConfig(
                table_fqn="tidingsiq-dev.gold.positive_news_feed",
                lookback_days=90,
                row_limit=500,
            ),
        )

        parameter_map = {name: value for name, _, value in parameters}

        self.assertIn('serving_date >= date_sub(current_date("utc")', sql.lower())
        self.assertIn("is_positive_feed_eligible = true", sql)
        self.assertEqual(parameter_map["row_limit"], 200)
        self.assertEqual(parameter_map["lookback_days"], 30)
        self.assertIn("language", sql.lower())
        self.assertIn("mentioned_country_name", sql.lower())
        self.assertIn("exclusion_reason", sql.lower())
        self.assertNotIn("below_threshold", sql.lower())
        self.assertNotIn("min_happy_factor", parameter_map)

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

    def test_build_visible_feed_state_returns_empty_state_for_no_rows(self) -> None:
        state = build_visible_feed_state(
            [],
            feed_sort_order="Least optimistic first",
        )

        self.assertEqual(state.recommended_rows, [])
        self.assertEqual(state.visible_rows, [])
        self.assertEqual(state.summary["row_count"], 0)
        self.assertEqual(build_timeline_data(state.visible_rows), [])
        self.assertEqual(build_score_distribution(state.visible_rows)[0]["story_count"], 0)

    def test_build_visible_feed_state_only_recommended_rows_match_pulse_totals(self) -> None:
        state = build_visible_feed_state(
            [
                _make_row("a", happy_factor=68.0, is_positive_feed_eligible=True),
                _make_row("b", happy_factor=81.0, is_positive_feed_eligible=True),
            ],
            feed_sort_order="Least optimistic first",
        )

        self.assertEqual([row["article_id"] for row in state.recommended_rows], ["a", "b"])
        self.assertEqual(len(state.visible_rows), 2)
        self.assertEqual(state.summary["row_count"], len(state.visible_rows))
        self.assertEqual(
            sum(point["story_count"] for point in build_timeline_data(state.visible_rows)),
            len(state.visible_rows),
        )

    def test_build_visible_feed_state_hides_non_eligible_rows(self) -> None:
        state = build_visible_feed_state(
            [
                _make_row(
                    "x",
                    happy_factor=48.0,
                    is_positive_feed_eligible=False,
                    exclusion_reason="below_threshold",
                ),
                _make_row(
                    "y",
                    happy_factor=52.0,
                    is_positive_feed_eligible=False,
                    exclusion_reason="below_threshold",
                    source_name="Source B",
                ),
            ],
            feed_sort_order="Least optimistic first",
        )

        self.assertEqual(state.recommended_rows, [])
        self.assertEqual(state.visible_rows, [])
        self.assertEqual(state.summary["row_count"], len(state.visible_rows))
        self.assertEqual(build_source_rankings(state.visible_rows), [])
        self.assertEqual(
            sum(bucket["story_count"] for bucket in build_score_distribution(state.visible_rows)),
            len(state.visible_rows),
        )

    def test_build_visible_feed_state_mixed_rows_keeps_only_recommended_rows_in_sync(self) -> None:
        state = build_visible_feed_state(
            [
                _make_row(
                    "rec-1",
                    happy_factor=72.0,
                    is_positive_feed_eligible=True,
                    serving_date="2026-04-01",
                ),
                _make_row(
                    "rec-2",
                    happy_factor=83.0,
                    is_positive_feed_eligible=True,
                    serving_date="2026-04-02",
                    source_name="Source B",
                ),
                _make_row(
                    "exp-1",
                    happy_factor=58.0,
                    is_positive_feed_eligible=False,
                    exclusion_reason="below_threshold",
                    serving_date="2026-04-02",
                ),
            ],
            feed_sort_order="Least optimistic first",
        )

        self.assertEqual([row["article_id"] for row in state.visible_rows], ["rec-1", "rec-2"])
        self.assertEqual(state.summary["row_count"], len(state.visible_rows))
        self.assertEqual(
            sum(point["story_count"] for point in build_timeline_data(state.visible_rows)),
            len(state.visible_rows),
        )
        self.assertEqual(
            sum(bucket["story_count"] for bucket in build_score_distribution(state.visible_rows)),
            len(state.visible_rows),
        )

    def test_build_visible_feed_state_reverses_sort_order_for_recommended_rows(self) -> None:
        state = build_visible_feed_state(
            [
                _make_row("rec-1", happy_factor=72.0, is_positive_feed_eligible=True),
                _make_row("rec-2", happy_factor=84.0, is_positive_feed_eligible=True),
            ],
            feed_sort_order="Most optimistic first",
        )

        self.assertEqual([row["article_id"] for row in state.recommended_rows], ["rec-2", "rec-1"])

    def test_build_visible_feed_state_sorts_by_most_recent_news(self) -> None:
        state = build_visible_feed_state(
            [
                _make_row(
                    "rec-older",
                    happy_factor=88.0,
                    is_positive_feed_eligible=True,
                    title="Older",
                )
                | {"published_at": datetime(2026, 4, 1, 8, 0, tzinfo=timezone.utc)},
                _make_row(
                    "rec-newer",
                    happy_factor=70.0,
                    is_positive_feed_eligible=True,
                    title="Newer",
                )
                | {"published_at": datetime(2026, 4, 2, 8, 0, tzinfo=timezone.utc)},
            ],
            feed_sort_order="Most recent news",
        )

        self.assertEqual([row["article_id"] for row in state.recommended_rows], ["rec-newer", "rec-older"])

    def test_build_visible_feed_state_sorts_by_oldest_news(self) -> None:
        state = build_visible_feed_state(
            [
                _make_row(
                    "rec-newer",
                    happy_factor=75.0,
                    is_positive_feed_eligible=True,
                    title="Newer",
                )
                | {"published_at": datetime(2026, 4, 2, 8, 0, tzinfo=timezone.utc)},
                _make_row(
                    "rec-older",
                    happy_factor=71.0,
                    is_positive_feed_eligible=True,
                    title="Older",
                )
                | {"published_at": datetime(2026, 4, 1, 8, 0, tzinfo=timezone.utc)},
            ],
            feed_sort_order="Oldest news",
        )

        self.assertEqual([row["article_id"] for row in state.recommended_rows], ["rec-older", "rec-newer"])

    def test_build_visible_feed_state_sorts_by_recent_news_using_string_dates_and_fallbacks(self) -> None:
        state = build_visible_feed_state(
            [
                _make_row(
                    "fallback-serving-date",
                    happy_factor=78.0,
                    is_positive_feed_eligible=True,
                )
                | {"published_at": None, "ingested_at": None, "serving_date": "2026-04-01"},
                _make_row(
                    "string-published-at",
                    happy_factor=66.0,
                    is_positive_feed_eligible=True,
                )
                | {"published_at": "2026-04-02T08:00:00+00:00"},
            ],
            feed_sort_order="Most recent news",
        )

        self.assertEqual(
            [row["article_id"] for row in state.recommended_rows],
            ["string-published-at", "fallback-serving-date"],
        )

    def test_build_visible_feed_state_keeps_pulse_scope_to_visible_eligible_rows(self) -> None:
        state = build_visible_feed_state(
            [
                _make_row("rec-1", happy_factor=74.0, is_positive_feed_eligible=True),
                _make_row(
                    "exp-hidden",
                    happy_factor=58.0,
                    is_positive_feed_eligible=False,
                    exclusion_reason="below_threshold",
                ),
                _make_row(
                    "hard-deny",
                    happy_factor=90.0,
                    is_positive_feed_eligible=False,
                    exclusion_reason="hard_deny_term",
                ),
            ],
            feed_sort_order="Least optimistic first",
        )

        self.assertEqual([row["article_id"] for row in state.visible_rows], ["rec-1"])
        self.assertEqual(state.summary["row_count"], len(state.visible_rows))
        self.assertLessEqual(
            sum(point["story_count"] for point in build_timeline_data(state.visible_rows)),
            len(state.visible_rows),
        )
        self.assertLessEqual(
            sum(bucket["story_count"] for bucket in build_score_distribution(state.visible_rows)),
            len(state.visible_rows),
        )


if __name__ == "__main__":
    unittest.main()
