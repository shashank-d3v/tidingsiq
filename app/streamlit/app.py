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
from data_access import load_feed, load_pipeline_status  # noqa: E402
from query_builder import (  # noqa: E402
    FeedQueryConfig,
    build_visible_feed_state,
    dedupe_story_rows,
)
from ui_helpers import render_logo, render_pipeline_status  # noqa: E402
from ui_pages import render_brief, render_methodology, render_pulse  # noqa: E402
from ui_styles import APP_CSS  # noqa: E402


def _initialize_state() -> None:
    st.session_state.setdefault("current_page", PAGE_BRIEF)
    st.session_state.setdefault("recommended_page", 1)
    st.session_state.setdefault("explore_page", 1)
    st.session_state.setdefault("sidebar_collapsed", False)
    st.session_state.setdefault("feed_sort_order", "Least optimistic first")
    st.session_state.setdefault("selected_languages", [])
    st.session_state.setdefault("selected_geographies", [])
    st.session_state.setdefault("selected_serving_date", "All")
    st.session_state.setdefault("cached_rows", [])
    st.session_state.setdefault("cached_lookback_days", None)


def main() -> None:
    _initialize_state()
    st.markdown(APP_CSS, unsafe_allow_html=True)
    sidebar_collapsed = bool(st.session_state.get("sidebar_collapsed"))
    current_page = str(st.session_state.get("current_page", PAGE_BRIEF))
    min_happy_factor = int(st.session_state.get("min_happy_factor", 65))
    lookback_days = int(st.session_state.get("lookback_days", LOOKBACK_OPTIONS[0]))
    feed_sort_order = str(
        st.session_state.get("feed_sort_order", "Least optimistic first")
    )
    selected_languages = list(st.session_state.get("selected_languages", []))
    selected_geographies = list(st.session_state.get("selected_geographies", []))
    selected_serving_date = str(st.session_state.get("selected_serving_date", "All"))

    if st.session_state.get("cached_lookback_days") != lookback_days:
        config = FeedQueryConfig(
            table_fqn=DEFAULT_TABLE_FQN,
            min_happy_factor=0.0,
            lookback_days=lookback_days,
            row_limit=QUERY_ROW_LIMIT,
            eligible_only=False,
        )
        try:
            with st.spinner("Updating feed..."):
                rows, _ = load_feed(DEFAULT_PROJECT_ID, config)
        except Exception as exc:  # pragma: no cover - UI fallback
            st.error(f"Query failed: {exc}")
            st.stop()
        st.session_state["cached_rows"] = dedupe_story_rows(rows)
        st.session_state["cached_lookback_days"] = lookback_days

    rows = list(st.session_state.get("cached_rows", []))

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

    if sidebar_collapsed:
        rail_col, content_col = st.columns([0.82, 9.18], gap="large")
        with rail_col:
            st.markdown('<div class="tiq-rail-anchor tiq-rail-anchor-collapsed"></div>', unsafe_allow_html=True)
            st.markdown('<div class="tiq-rail-compact-head"></div>', unsafe_allow_html=True)
            header_col, toggle_col = st.columns([1, 1], gap="small")
            with header_col:
                render_logo(is_collapsed=True)
            with toggle_col:
                st.markdown('<div class="tiq-rail-toggle-anchor"></div>', unsafe_allow_html=True)
                if st.button(
                    " ",
                    key="expand_sidebar_button",
                    icon=":material/tune:",
                    width="stretch",
                ):
                    st.session_state["sidebar_collapsed"] = False
                    st.rerun()
        content_container = content_col
        status_placeholder = None
    else:
        rail_col, content_col = st.columns([1.72, 8.28], gap="large")
        with rail_col:
            st.markdown('<div class="tiq-rail-anchor tiq-rail-anchor-expanded"></div>', unsafe_allow_html=True)
            st.markdown('<div class="tiq-rail-head"></div>', unsafe_allow_html=True)
            logo_col, toggle_col = st.columns([7.2, 1], gap="large")
            with logo_col:
                render_logo(is_collapsed=False)
            with toggle_col:
                st.markdown('<div class="tiq-rail-toggle-anchor"></div>', unsafe_allow_html=True)
                if st.button(
                    " ",
                    key="collapse_sidebar_button",
                    icon=":material/close:",
                    width="stretch",
                ):
                    st.session_state["sidebar_collapsed"] = True
                    st.rerun()
            nav_container = st.container()
            with nav_container:
                st.markdown('<div class="tiq-nav-anchor"></div>', unsafe_allow_html=True)
                for page_name, icon in [
                    (PAGE_BRIEF, ":material/grid_view:"),
                    (PAGE_PULSE, ":material/monitoring:"),
                    (PAGE_METHODOLOGY, ":material/info:"),
                ]:
                    button_key = f"nav_{page_name.lower().replace(' ', '_')}"
                    is_active = current_page == page_name
                    if st.button(
                        page_name,
                        key=button_key,
                        width="stretch",
                        type="primary" if is_active else "secondary",
                        icon=icon,
                    ):
                        st.session_state["current_page"] = page_name
                        st.rerun()
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
            selected_languages = st.multiselect(
                "Language",
                options=language_options,
                key="selected_languages",
                placeholder=(
                    "Choose language"
                    if language_options
                    else "No language data in current feed"
                ),
            )
            selected_geographies = st.multiselect(
                "Mentioned geography",
                options=geography_options,
                key="selected_geographies",
                placeholder=(
                    "Choose geography"
                    if geography_options
                    else "No geography data in current feed"
                ),
            )
            selected_serving_date = st.selectbox(
                "Date",
                options=["All"] + serving_date_options,
                index=(["All"] + serving_date_options).index(
                    selected_serving_date if selected_serving_date in serving_date_options else "All"
                ),
                key="selected_serving_date",
            )
            status_placeholder = st.empty()
        content_container = content_col

    filter_signature = (
        min_happy_factor,
        lookback_days,
        tuple(sorted(selected_languages)),
        tuple(sorted(selected_geographies)),
        selected_serving_date,
    )
    if st.session_state.get("filter_signature") != filter_signature:
        st.session_state["filter_signature"] = filter_signature
        st.session_state["recommended_page"] = 1
        st.session_state["explore_page"] = 1

    pipeline_status = None
    if status_placeholder is not None:
        pipeline_status = load_pipeline_status(DEFAULT_PROJECT_ID, DEFAULT_TABLE_FQN)
        status_placeholder.markdown(
            render_pipeline_status(pipeline_status, rows),
            unsafe_allow_html=True,
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
        min_happy_factor=float(min_happy_factor),
        feed_sort_order=feed_sort_order,
    )

    with content_container:
        if current_page == PAGE_BRIEF:
            render_brief(
                lookback_days=lookback_days,
                feed_sort_order=feed_sort_order,
                summary=visible_feed_state.summary,
                recommended_rows=visible_feed_state.recommended_rows,
                more_to_explore_rows=visible_feed_state.more_to_explore_rows,
                more_to_explore_empty_reason=visible_feed_state.more_to_explore_empty_reason,
            )
        elif current_page == PAGE_PULSE:
            render_pulse(visible_feed_state.visible_rows)
        else:
            render_methodology()


if __name__ == "__main__":
    main()
