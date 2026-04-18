from __future__ import annotations

from datetime import datetime, timezone
import inspect
import sys
import types
import unittest
from unittest.mock import patch

class _DummyContainer:
    def __enter__(self) -> "_DummyContainer":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


if "streamlit" not in sys.modules:
    sys.modules["streamlit"] = types.SimpleNamespace(
        button=lambda *args, **kwargs: False,
        columns=lambda *args, **kwargs: [],
        container=lambda *args, **kwargs: _DummyContainer(),
        form=lambda *args, **kwargs: _DummyContainer(),
        form_submit_button=lambda *args, **kwargs: False,
        markdown=lambda *args, **kwargs: None,
        multiselect=lambda *args, **kwargs: [],
        popover=lambda *args, **kwargs: _DummyContainer(),
        segmented_control=lambda *args, **kwargs: None,
        session_state={},
        vega_lite_chart=lambda *args, **kwargs: None,
    )

from app.streamlit import ui_pages


class UrlAllowlistTest(unittest.TestCase):
    def test_normalize_safe_article_url_allows_http(self) -> None:
        self.assertEqual(
            ui_pages._normalize_safe_article_url("http://example.com/story"),
            "http://example.com/story",
        )

    def test_normalize_safe_article_url_allows_https(self) -> None:
        self.assertEqual(
            ui_pages._normalize_safe_article_url("HTTPS://example.com/story?x=1#top"),
            "https://example.com/story?x=1#top",
        )

    def test_normalize_safe_article_url_rejects_javascript_scheme(self) -> None:
        self.assertEqual(
            ui_pages._normalize_safe_article_url("javascript:alert(1)"),
            "",
        )

    def test_normalize_safe_article_url_rejects_data_scheme(self) -> None:
        self.assertEqual(
            ui_pages._normalize_safe_article_url("data:text/html,<script>alert(1)</script>"),
            "",
        )

    def test_normalize_safe_article_url_rejects_mailto_scheme(self) -> None:
        self.assertEqual(
            ui_pages._normalize_safe_article_url("mailto:tips@example.com"),
            "",
        )

    def test_normalize_safe_article_url_rejects_malformed_or_missing_scheme_values(self) -> None:
        for value in ("example.com/story", "http:///broken"):
            with self.subTest(value=value):
                self.assertEqual(ui_pages._normalize_safe_article_url(value), "")

    def test_render_article_card_links_only_safe_urls(self) -> None:
        with patch.object(ui_pages, "format_relative_time", return_value="just now"), patch.object(
            ui_pages,
            "format_language",
            return_value="Unknown",
        ), patch.object(
            ui_pages,
            "format_geography",
            return_value="Unknown",
        ), patch.object(
            ui_pages,
            "score_badge_class",
            return_value="tiq-score-positive",
        ), patch.object(ui_pages.st, "markdown") as markdown:
            ui_pages.render_article_card(
                {
                    "title": "Safe story",
                    "source_name": "Example Source",
                    "url": "https://example.com/story",
                    "tone_score": 1.5,
                    "happy_factor": 88.0,
                }
            )
            ui_pages.render_article_card(
                {
                    "title": "Unsafe story",
                    "source_name": "Example Source",
                    "url": "javascript:alert(1)",
                    "tone_score": 1.5,
                    "happy_factor": 88.0,
                }
            )

        safe_markup = markdown.call_args_list[0].args[0]
        unsafe_markup = markdown.call_args_list[1].args[0]

        self.assertIn('href="https://example.com/story"', safe_markup)
        self.assertIn(">Read article</a>", safe_markup)
        self.assertNotIn("href=", unsafe_markup)
        self.assertIn("No source URL", unsafe_markup)


class RenderBriefTest(unittest.TestCase):
    def test_ui_pages_do_not_expose_free_form_query_inputs(self) -> None:
        source = inspect.getsource(ui_pages)

        self.assertNotIn("text_input(", source)
        self.assertNotIn("text_area(", source)

    def test_apply_multi_filter_draft_state_commits_only_target_filter(self) -> None:
        session_state = {
            "draft_selected_languages": ["EN", "EN", "FR"],
            "draft_selected_languages_popover_open": True,
            "selected_languages": ["DE"],
            "selected_geographies": ["India"],
        }

        with patch.object(ui_pages.st, "session_state", session_state):
            ui_pages._apply_multi_filter_draft_state(
                "selected_languages",
                "draft_selected_languages",
                "draft_selected_languages_popover_open",
            )

        self.assertEqual(session_state["selected_languages"], ["EN", "FR"])
        self.assertEqual(session_state["selected_geographies"], ["India"])
        self.assertFalse(session_state["draft_selected_languages_popover_open"])

    def test_clear_multi_filter_draft_state_clears_only_target_filter(self) -> None:
        session_state = {
            "draft_selected_languages": ["EN"],
            "draft_selected_geographies": ["India"],
            "draft_selected_languages_popover_open": True,
            "selected_languages": ["EN"],
            "selected_geographies": ["India"],
        }

        with patch.object(ui_pages.st, "session_state", session_state):
            ui_pages._clear_multi_filter_draft_state(
                "selected_languages",
                "draft_selected_languages",
                "draft_selected_languages_popover_open",
            )

        self.assertEqual(session_state["selected_languages"], [])
        self.assertEqual(session_state["draft_selected_languages"], [])
        self.assertEqual(session_state["selected_geographies"], ["India"])
        self.assertEqual(session_state["draft_selected_geographies"], ["India"])
        self.assertFalse(session_state["draft_selected_languages_popover_open"])

    def test_format_multi_filter_summary_uses_first_selected_plus_count(self) -> None:
        self.assertEqual(
            ui_pages._format_multi_filter_summary(
                label="Region",
                selected=["India", "France", "Japan", "India"],
                empty_value="All",
                value_formatter=ui_pages.format_geography,
            ),
            "Region: India +2",
        )

    def test_format_multi_filter_summary_uses_placeholder_when_empty(self) -> None:
        self.assertEqual(
            ui_pages._format_multi_filter_summary(
                label="Language",
                selected=[],
                empty_value="All",
                value_formatter=ui_pages.format_language,
            ),
            "Language: All",
        )

    def test_close_multi_filter_popover_updates_state_when_key_present(self) -> None:
        session_state = {"draft_selected_languages_popover_open": True}

        with patch.object(ui_pages.st, "session_state", session_state):
            ui_pages._close_multi_filter_popover(
                "draft_selected_languages_popover_open"
            )

        self.assertFalse(session_state["draft_selected_languages_popover_open"])

    def test_render_brief_uses_authoritative_pagination_inputs(self) -> None:
        rows = [
            {"article_id": "a", "title": "Story A"},
            {"article_id": "b", "title": "Story B"},
        ]

        with patch.object(ui_pages, "_render_page_masthead"), patch.object(
            ui_pages,
            "_render_brief_filter_bar",
        ), patch.object(ui_pages, "render_metric_card"), patch.object(
            ui_pages,
            "render_article_card",
        ) as render_article_card, patch.object(
            ui_pages,
            "render_pagination",
        ) as render_pagination, patch.object(
            ui_pages,
            "render_empty_state",
        ) as render_empty_state, patch.object(
            ui_pages.st,
            "columns",
            side_effect=[
                [_DummyContainer(), _DummyContainer(), _DummyContainer(), _DummyContainer()],
                [_DummyContainer(), _DummyContainer()],
            ],
        ), patch.object(ui_pages.st, "markdown"):
            ui_pages.render_brief(
                language_options=["EN"],
                geography_options=["India"],
                summary={
                    "row_count": 42,
                    "avg_happy_factor": 74.3,
                    "max_happy_factor": 88.0,
                    "source_count": 11,
                },
                recommended_rows=rows,
                current_page=3,
                total_pages=5,
                total_rows=42,
            )

        self.assertEqual(render_article_card.call_count, 2)
        render_article_card.assert_any_call(rows[0])
        render_article_card.assert_any_call(rows[1])
        render_empty_state.assert_not_called()
        render_pagination.assert_called_once_with(
            state_key="recommended_page",
            current_page=3,
            total_pages=5,
            total_rows=42,
            page_size=ui_pages.RECOMMENDED_PAGE_SIZE,
            label="recommended stories",
        )


class RenderPulseTest(unittest.TestCase):
    def test_render_pulse_supporting_stats_accept_timestamps(self) -> None:
        pulse_dashboard = {
            "latest_snapshot": {
                "audit_run_at": datetime(2026, 4, 17, 8, 30, tzinfo=timezone.utc),
                "bronze_row_count": 120,
                "silver_row_count": 100,
                "silver_canonical_row_count": 94,
                "silver_duplicate_row_count": 6,
                "gold_row_count": 80,
                "eligible_row_count": 42,
                "ineligible_row_count": 38,
                "gold_avg_happy_factor": 73.4,
                "gold_max_happy_factor": 91.0,
                "latest_gold_ingested_at": datetime(
                    2026,
                    4,
                    17,
                    9,
                    0,
                    tzinfo=timezone.utc,
                ),
            },
            "stage_snapshot": [
                {"stage": "Bronze Landed", "row_count": 120},
                {"stage": "Silver Normalized", "row_count": 100},
                {"stage": "Silver Canonical", "row_count": 94},
                {"stage": "Gold Scored", "row_count": 80},
                {"stage": "Gold Eligible", "row_count": 42},
            ],
            "exclusion_breakdown": [{"bucket": "Below Threshold", "row_count": 28}],
            "pipeline_trend": [
                {"run_label": "Apr 15", "stage": "Bronze Landed", "row_count": 110},
                {"run_label": "Apr 15", "stage": "Silver Canonical", "row_count": 90},
                {"run_label": "Apr 15", "stage": "Gold Scored", "row_count": 78},
            ],
            "silver_cleanup_trend": [
                {"run_label": "Apr 15", "bucket": "Silver Canonical", "row_count": 90},
                {"run_label": "Apr 15", "bucket": "Silver Duplicates", "row_count": 8},
            ],
            "score_distribution": [
                {"bucket": "70-75", "bucket_order": 3, "row_count": 24},
                {"bucket": "75-80", "bucket_order": 4, "row_count": 19},
            ],
        }

        with patch.object(ui_pages, "_render_page_masthead"), patch.object(
            ui_pages,
            "_render_chart_card",
        ), patch.object(
            ui_pages,
            "_render_supporting_stats",
        ) as render_supporting_stats, patch.object(
            ui_pages.st,
            "columns",
            side_effect=[
                [_DummyContainer(), _DummyContainer()],
                [_DummyContainer(), _DummyContainer()],
            ],
        ), patch.object(ui_pages.st, "vega_lite_chart"), patch.object(
            ui_pages.st,
            "markdown",
        ):
            ui_pages.render_pulse(pulse_dashboard=pulse_dashboard)

        self.assertGreaterEqual(render_supporting_stats.call_count, 3)


if __name__ == "__main__":
    unittest.main()
