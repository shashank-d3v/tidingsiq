from __future__ import annotations

from pathlib import Path
import streamlit as st

st.set_page_config(
    page_title="TidingsIQ",
    page_icon=str(Path(__file__).resolve().parent / "assets" / "tiq-icon.ico"),
    layout="wide",
    initial_sidebar_state="collapsed",
)

from constants import (  # noqa: E402
    DEFAULT_PROJECT_ID,
    DEFAULT_TABLE_FQN,
    LOOKBACK_OPTIONS,
    PAGE_BRIEF,
    PAGE_METHODOLOGY,
    PAGE_PULSE,
    QUERY_ROW_LIMIT,
)
from data_access import load_feed, load_pipeline_status, load_pulse_dashboard  # noqa: E402
from query_builder import (  # noqa: E402
    FeedQueryConfig,
    build_visible_feed_state,
    dedupe_story_rows,
)
from ui_helpers import (  # noqa: E402
    render_global_header,
    render_loading_state,
    render_pipeline_status,
)
from ui_pages import render_brief, render_methodology, render_pulse  # noqa: E402
from ui_styles import APP_CSS  # noqa: E402


def _initialize_state() -> None:
    st.session_state.setdefault("current_page", PAGE_BRIEF)
    st.session_state.setdefault("recommended_page", 1)
    st.session_state.setdefault("sidebar_collapsed", False)
    st.session_state.setdefault("feed_sort_order", "Least optimistic first")
    st.session_state.setdefault("selected_languages", [])
    st.session_state.setdefault("selected_geographies", [])
    st.session_state.setdefault("selected_serving_date", "All")
    st.session_state.setdefault("cached_rows", [])
    st.session_state.setdefault("cached_lookback_days", None)


def _load_cached_brief_rows(lookback_days: int) -> list[dict[str, object]]:
    if st.session_state.get("cached_lookback_days") != lookback_days:
        config = FeedQueryConfig(
            table_fqn=DEFAULT_TABLE_FQN,
            lookback_days=lookback_days,
            row_limit=QUERY_ROW_LIMIT,
        )
        loading_placeholder = st.empty()
        render_loading_state(
            "Refreshing the brief and calibrating the latest trend line.",
            container=loading_placeholder,
        )
        try:
            rows, _ = load_feed(DEFAULT_PROJECT_ID, config)
        except Exception as exc:  # pragma: no cover - UI fallback
            loading_placeholder.empty()
            st.error(f"Query failed: {exc}")
            st.stop()
        loading_placeholder.empty()
        st.session_state["cached_rows"] = dedupe_story_rows(rows)
        st.session_state["cached_lookback_days"] = lookback_days

    return list(st.session_state.get("cached_rows", []))


def main() -> None:
    _initialize_state()
    st.markdown(APP_CSS, unsafe_allow_html=True)
    current_page = str(st.session_state.get("current_page", PAGE_BRIEF))
    lookback_days = int(st.session_state.get("lookback_days", LOOKBACK_OPTIONS[0]))
    feed_sort_order = str(
        st.session_state.get("feed_sort_order", "Least optimistic first")
    )
    if lookback_days == 1 and feed_sort_order in {"Most recent news", "Oldest news"}:
        st.session_state["feed_sort_order"] = "Least optimistic first"
        feed_sort_order = "Least optimistic first"
    rows: list[dict[str, object]] = []

    def _row_language(row: dict[str, object]) -> str:
        value = row.get("language")
        text = str(value or "").strip()
        if not text or text.lower() == "und":
            return "Unknown"
        return text.upper()

    def _row_geography(row: dict[str, object]) -> str:
        value = row.get("mentioned_country_name")
        text = str(value or "").strip()
        return text if text else "Unknown"

    if current_page == PAGE_BRIEF:
        rows = _load_cached_brief_rows(lookback_days)
        selected_languages = list(st.session_state.get("selected_languages", []))
        selected_geographies = list(st.session_state.get("selected_geographies", []))
        selected_serving_date = str(st.session_state.get("selected_serving_date", "All"))

        language_options = sorted(
            {lang for lang in (_row_language(row) for row in rows) if lang != "Unknown"}
        )
        geography_options = sorted(
            {geo for geo in (_row_geography(row) for row in rows) if geo != "Unknown"}
        )
        serving_date_options = sorted(
            {
                str(row.get("serving_date"))
                for row in rows
                if row.get("serving_date") is not None
            },
            reverse=True,
        )
        st.session_state["selected_languages"] = [
            lang for lang in selected_languages if lang in language_options
        ]
        st.session_state["selected_geographies"] = [
            geo for geo in selected_geographies if geo in geography_options
        ]
        if selected_serving_date != "All" and selected_serving_date not in serving_date_options:
            st.session_state["selected_serving_date"] = "All"
            selected_serving_date = "All"

        filter_signature = (
            lookback_days,
            tuple(sorted(selected_languages)),
            tuple(sorted(selected_geographies)),
            selected_serving_date,
        )
        if st.session_state.get("filter_signature") != filter_signature:
            st.session_state["filter_signature"] = filter_signature
            st.session_state["recommended_page"] = 1
    else:
        selected_languages = []
        selected_geographies = []
        selected_serving_date = "All"

    pulse_dashboard = None
    if current_page == PAGE_PULSE:
        pulse_dashboard = load_pulse_dashboard(DEFAULT_PROJECT_ID, DEFAULT_TABLE_FQN)
        pipeline_status = (
            dict(pulse_dashboard.get("latest_snapshot") or {})
            if pulse_dashboard is not None
            else None
        )
    else:
        pipeline_status = load_pipeline_status(DEFAULT_PROJECT_ID, DEFAULT_TABLE_FQN)
    pipeline_status_markup = render_pipeline_status(pipeline_status)

    render_global_header(
        current_page=current_page,
        pipeline_status_markup=pipeline_status_markup,
    )

    filtered_rows = rows
    if selected_languages:
        selected_language_set = {str(value) for value in selected_languages}
        filtered_rows = [
            row for row in filtered_rows if _row_language(row) in selected_language_set
        ]
    if selected_geographies:
        selected_geo_set = {str(value) for value in selected_geographies}
        filtered_rows = [
            row for row in filtered_rows if _row_geography(row) in selected_geo_set
        ]
    if selected_serving_date != "All":
        filtered_rows = [
            row for row in filtered_rows if str(row.get("serving_date")) == selected_serving_date
        ]

    visible_feed_state = build_visible_feed_state(
        filtered_rows,
        feed_sort_order=feed_sort_order,
    )

    if current_page == PAGE_BRIEF:
        render_brief(
            lookback_days=lookback_days,
            feed_sort_order=feed_sort_order,
            summary=visible_feed_state.summary,
            recommended_rows=visible_feed_state.recommended_rows,
        )
    elif current_page == PAGE_PULSE:
        render_pulse(
            pulse_dashboard=pulse_dashboard,
        )
    else:
        render_methodology()


if __name__ == "__main__":
    main()
