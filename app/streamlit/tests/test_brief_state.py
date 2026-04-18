from __future__ import annotations

import unittest

from app.streamlit.brief_state import (
    build_geography_options_signature,
    build_language_options_signature,
    build_rows_signature,
    build_scope_signature,
    reset_page_on_scope_change,
    resolve_brief_filter_state,
)


class BriefStateTest(unittest.TestCase):
    def test_scope_change_resets_page_to_one(self) -> None:
        previous_scope_signature = build_scope_signature(7, ["EN"], ["India"])
        next_scope_signature = build_scope_signature(30, ["EN"], ["India"])

        next_page = reset_page_on_scope_change(
            previous_scope_signature,
            next_scope_signature,
            4,
        )

        self.assertEqual(next_page, 1)

    def test_sort_change_keeps_page_and_only_changes_rows_signature(self) -> None:
        scope_signature = build_scope_signature(7, ["EN"], ["India"])
        previous_rows_signature = build_rows_signature(
            scope_signature,
            "Most optimistic first",
            3,
            10,
        )
        next_rows_signature = build_rows_signature(
            scope_signature,
            "Least optimistic first",
            3,
            10,
        )

        self.assertEqual(previous_rows_signature[0], next_rows_signature[0])
        self.assertEqual(previous_rows_signature[2], next_rows_signature[2])
        self.assertNotEqual(previous_rows_signature[1], next_rows_signature[1])
        self.assertEqual(
            reset_page_on_scope_change(scope_signature, scope_signature, 3),
            3,
        )

    def test_page_change_only_changes_rows_signature(self) -> None:
        scope_signature = build_scope_signature(7, ["EN"], ["India"])
        previous_rows_signature = build_rows_signature(
            scope_signature,
            "Most optimistic first",
            1,
            10,
        )
        next_rows_signature = build_rows_signature(
            scope_signature,
            "Most optimistic first",
            2,
            10,
        )

        self.assertEqual(previous_rows_signature[0], next_rows_signature[0])
        self.assertEqual(previous_rows_signature[1], next_rows_signature[1])
        self.assertNotEqual(previous_rows_signature[2], next_rows_signature[2])

    def test_resolve_brief_filter_state_prunes_invalid_selections_and_stabilizes_options(self) -> None:
        language_calls: list[tuple[int, tuple[str, ...]]] = []
        geography_calls: list[tuple[int, tuple[str, ...]]] = []

        def load_language_options(
            lookback_days: int,
            selected_geographies: tuple[str, ...],
        ) -> list[str]:
            language_calls.append((lookback_days, selected_geographies))
            if selected_geographies == ("France",):
                return ["EN"]
            return ["DE", "EN"]

        def load_geography_options(
            lookback_days: int,
            selected_languages: tuple[str, ...],
        ) -> list[str]:
            geography_calls.append((lookback_days, selected_languages))
            if selected_languages == ("EN",):
                return ["France", "United States"]
            return ["France"]

        selected_languages, selected_geographies, language_options, geography_options = (
            resolve_brief_filter_state(
                lookback_days=7,
                selected_languages=["DE", "EN"],
                selected_geographies=["France", "Nowhere"],
                load_language_options=load_language_options,
                load_geography_options=load_geography_options,
            )
        )

        self.assertEqual(selected_languages, ["EN"])
        self.assertEqual(selected_geographies, ["France"])
        self.assertEqual(language_options, ["EN"])
        self.assertEqual(geography_options, ["France", "United States"])
        self.assertEqual(
            language_calls,
            [
                build_language_options_signature(7, ["France", "Nowhere"]),
                build_language_options_signature(7, ["France"]),
            ],
        )
        self.assertEqual(
            geography_calls,
            [
                build_geography_options_signature(7, ["DE", "EN"]),
                build_geography_options_signature(7, ["EN"]),
            ],
        )

    def test_resolve_brief_filter_state_keeps_selected_filters_visible_when_preserving(self) -> None:
        language_calls: list[tuple[int, tuple[str, ...]]] = []
        geography_calls: list[tuple[int, tuple[str, ...]]] = []

        def load_language_options(
            lookback_days: int,
            selected_geographies: tuple[str, ...],
        ) -> list[str]:
            language_calls.append((lookback_days, selected_geographies))
            return []

        def load_geography_options(
            lookback_days: int,
            selected_languages: tuple[str, ...],
        ) -> list[str]:
            geography_calls.append((lookback_days, selected_languages))
            return []

        selected_languages, selected_geographies, language_options, geography_options = (
            resolve_brief_filter_state(
                lookback_days=3,
                selected_languages=["EN"],
                selected_geographies=["India"],
                load_language_options=load_language_options,
                load_geography_options=load_geography_options,
                preserve_selected_in_options=True,
            )
        )

        self.assertEqual(selected_languages, ["EN"])
        self.assertEqual(selected_geographies, ["India"])
        self.assertEqual(language_options, ["EN"])
        self.assertEqual(geography_options, ["India"])
        self.assertEqual(
            language_calls,
            [build_language_options_signature(3, ["India"])],
        )
        self.assertEqual(
            geography_calls,
            [build_geography_options_signature(3, ["EN"])],
        )


if __name__ == "__main__":
    unittest.main()
