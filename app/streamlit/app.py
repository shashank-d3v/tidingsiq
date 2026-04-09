from __future__ import annotations

import streamlit as st

from constants import (
    DEFAULT_PROJECT_ID,
    DEFAULT_TABLE_FQN,
    LOOKBACK_OPTIONS,
    PAGE_BRIEF,
    PAGE_METHODOLOGY,
    PAGE_PULSE,
    RESULT_LIMIT_OPTIONS,
)
from data_access import load_feed, load_pipeline_status
from query_builder import (
    FeedQueryConfig,
    dedupe_story_rows,
    split_feed_rows,
    summarize_feed,
)
from ui_helpers import render_logo, render_pipeline_status
from ui_pages import render_brief, render_methodology, render_pulse
from ui_styles import APP_CSS


st.set_page_config(
    page_title="TidingsIQ",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def _initialize_state() -> None:
    st.session_state.setdefault("current_page", PAGE_BRIEF)
    st.session_state.setdefault("recommended_page", 1)
    st.session_state.setdefault("explore_page", 1)
    st.session_state.setdefault("sidebar_collapsed", False)


def main() -> None:
    _initialize_state()
    st.markdown(APP_CSS, unsafe_allow_html=True)
    sidebar_collapsed = bool(st.session_state.get("sidebar_collapsed"))
    current_page = str(st.session_state.get("current_page", PAGE_BRIEF))
    min_happy_factor = int(st.session_state.get("min_happy_factor", 65))
    lookback_days = int(st.session_state.get("lookback_days", LOOKBACK_OPTIONS[0]))
    row_limit = int(st.session_state.get("row_limit", 100))

    if sidebar_collapsed:
        logo_col, expand_col, _ = st.columns([0.9, 1.45, 7.65], gap="small")
        with logo_col:
            render_logo(is_collapsed=True)
        with expand_col:
            st.markdown(
                '<div class="tiq-main-expand-anchor tiq-main-expand-row"></div>',
                unsafe_allow_html=True,
            )
            if st.button("→ Filters", key="expand_sidebar_button", width="stretch"):
                st.session_state["sidebar_collapsed"] = False
                st.rerun()
        content_container = st.container()
        status_placeholder = None
    else:
        rail_col, content_col = st.columns([1.55, 5.45], gap="large")
        with rail_col:
            render_logo(is_collapsed=False)
            if st.button("← Hide filters", key="collapse_sidebar_button", width="stretch"):
                st.session_state["sidebar_collapsed"] = True
                st.rerun()
            current_page = st.radio(
                "Navigate",
                options=[PAGE_BRIEF, PAGE_PULSE, PAGE_METHODOLOGY],
                key="current_page",
                label_visibility="collapsed",
            )
            min_happy_factor = st.slider(
                "Min Happy Factor",
                min_value=0,
                max_value=100,
                value=min_happy_factor,
                step=5,
                key="min_happy_factor",
            )
            lookback_days = st.radio(
                "Lookback Window",
                options=LOOKBACK_OPTIONS,
                horizontal=True,
                index=LOOKBACK_OPTIONS.index(lookback_days),
                format_func=lambda value: f"{value}d",
                key="lookback_days",
            )
            row_limit = st.selectbox(
                "Result Limit",
                options=RESULT_LIMIT_OPTIONS,
                index=RESULT_LIMIT_OPTIONS.index(row_limit),
                format_func=lambda value: f"{value} rows",
                key="row_limit",
            )
            status_placeholder = st.empty()
        content_container = content_col

    filter_signature = (min_happy_factor, lookback_days, row_limit)
    if st.session_state.get("filter_signature") != filter_signature:
        st.session_state["filter_signature"] = filter_signature
        st.session_state["recommended_page"] = 1
        st.session_state["explore_page"] = 1

    config = FeedQueryConfig(
        table_fqn=DEFAULT_TABLE_FQN,
        min_happy_factor=min_happy_factor,
        lookback_days=lookback_days,
        row_limit=row_limit,
        eligible_only=False,
    )

    try:
        rows, _ = load_feed(DEFAULT_PROJECT_ID, config)
    except Exception as exc:  # pragma: no cover - UI fallback
        st.error(f"Query failed: {exc}")
        st.stop()

    rows = dedupe_story_rows(rows)

    pipeline_status = load_pipeline_status(DEFAULT_PROJECT_ID, DEFAULT_TABLE_FQN)
    if status_placeholder is not None:
        status_placeholder.markdown(
            render_pipeline_status(pipeline_status, rows),
            unsafe_allow_html=True,
        )

    recommended_rows, more_to_explore_rows = split_feed_rows(rows)
    visible_rows = recommended_rows + more_to_explore_rows
    summary = summarize_feed(visible_rows)

    with content_container:
        if current_page == PAGE_BRIEF:
            render_brief(
                lookback_days=lookback_days,
                summary=summary,
                recommended_rows=recommended_rows,
                more_to_explore_rows=more_to_explore_rows,
            )
        elif current_page == PAGE_PULSE:
            render_pulse(rows)
        else:
            render_methodology()


if __name__ == "__main__":
    main()
