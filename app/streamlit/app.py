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
    LOOKBACK_OPTIONS,
    PAGE_BRIEF,
    PAGE_METHODOLOGY,
    PAGE_PULSE,
    RECOMMENDED_PAGE_SIZE,
    resolve_runtime_config,
)
from brief_state import (  # noqa: E402
    build_geography_options_signature,
    build_language_options_signature,
    build_rows_signature,
    build_scope_signature,
    clamp_page_number,
    compute_total_pages,
    reset_page_on_scope_change,
    resolve_brief_filter_state,
)
from data_access import (  # noqa: E402
    load_brief_geography_options,
    load_brief_language_options,
    load_brief_rows,
    load_brief_scope_summary,
    load_pipeline_status,
    load_pulse_dashboard,
)
from query_builder import (  # noqa: E402
    BriefGeographyOptionsQueryConfig,
    BriefLanguageOptionsQueryConfig,
    BriefRowsQueryConfig,
    BriefScopeQueryConfig,
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
    st.session_state.setdefault("lookback_days", LOOKBACK_OPTIONS[2])
    st.session_state.setdefault("feed_sort_order", "Most optimistic first")
    st.session_state.setdefault("selected_languages", [])
    st.session_state.setdefault(
        "draft_selected_languages",
        list(st.session_state["selected_languages"]),
    )
    st.session_state.setdefault("selected_geographies", [])
    st.session_state.setdefault(
        "draft_selected_geographies",
        list(st.session_state["selected_geographies"]),
    )
    st.session_state.setdefault("brief_last_lookback_days", None)
    st.session_state.setdefault("brief_scope_signature", None)
    st.session_state.setdefault("last_loaded_page", None)
    st.session_state.setdefault("last_loaded_brief_scope_signature", None)
    st.session_state.setdefault("last_loaded_brief_rows_signature", None)


def _resolve_loading_message(
    *,
    current_page: str,
    brief_scope_signature: tuple[int, tuple[str, ...], tuple[str, ...]] | None,
    brief_rows_signature: tuple[
        tuple[int, tuple[str, ...], tuple[str, ...]], str, int, int
    ]
    | None,
) -> str | None:
    last_loaded_page = st.session_state.get("last_loaded_page")
    if last_loaded_page != current_page:
        if current_page == PAGE_PULSE:
            return "Loading the latest pipeline pulse from the warehouse."
        if current_page == PAGE_BRIEF:
            return "Refreshing the brief and calibrating the latest trend line."
        return "Loading the next section."

    if current_page != PAGE_BRIEF:
        return None

    if st.session_state.get("last_loaded_brief_scope_signature") != brief_scope_signature:
        return "Refreshing the brief and calibrating the latest trend line."
    if st.session_state.get("last_loaded_brief_rows_signature") != brief_rows_signature:
        return "Refreshing the brief and calibrating the latest trend line."
    return None


def main() -> None:
    try:
        project_id, table_fqn = resolve_runtime_config()
    except RuntimeError as exc:
        st.error(str(exc))
        st.stop()

    _initialize_state()
    st.markdown(APP_CSS, unsafe_allow_html=True)
    current_page = str(st.session_state.get("current_page", PAGE_BRIEF))
    lookback_days = int(st.session_state.get("lookback_days", LOOKBACK_OPTIONS[0]))
    feed_sort_order = str(
        st.session_state.get("feed_sort_order", "Most optimistic first")
    )
    if feed_sort_order not in {"Most optimistic first", "Least optimistic first"}:
        st.session_state["feed_sort_order"] = "Most optimistic first"
        feed_sort_order = "Most optimistic first"
    rows: list[dict[str, object]] = []
    summary: dict[str, float | int] = {
        "row_count": 0,
        "avg_happy_factor": 0.0,
        "max_happy_factor": 0.0,
        "source_count": 0,
    }
    total_rows = 0
    total_pages = 1
    loading_placeholder = None
    scope_signature = None
    rows_signature = None

    if current_page == PAGE_BRIEF:
        selected_languages = list(st.session_state.get("selected_languages", []))
        selected_geographies = list(st.session_state.get("selected_geographies", []))
        current_page_number = int(st.session_state.get("recommended_page", 1))
        preview_scope_signature = build_scope_signature(
            lookback_days,
            selected_languages,
            selected_geographies,
        )
        preview_rows_signature = build_rows_signature(
            preview_scope_signature,
            feed_sort_order,
            current_page_number,
            RECOMMENDED_PAGE_SIZE,
        )
        previous_lookback_days = st.session_state.get("brief_last_lookback_days")
        lookback_changed = (
            previous_lookback_days is not None
            and int(previous_lookback_days) != lookback_days
        )
    else:
        selected_languages = []
        selected_geographies = []
        language_options = []
        geography_options = []
        preview_scope_signature = None
        preview_rows_signature = None

    loading_message = _resolve_loading_message(
        current_page=current_page,
        brief_scope_signature=preview_scope_signature,
        brief_rows_signature=preview_rows_signature,
    )
    if loading_message is not None:
        loading_placeholder = st.empty()
        render_loading_state(
            loading_message,
            container=loading_placeholder,
            variant="page",
        )

    if current_page == PAGE_BRIEF:
        try:
            selected_languages, selected_geographies, language_options, geography_options = (
                resolve_brief_filter_state(
                    lookback_days=lookback_days,
                    selected_languages=selected_languages,
                    selected_geographies=selected_geographies,
                    load_language_options=lambda scoped_lookback, scoped_geographies: (
                        load_brief_language_options(
                            project_id,
                            BriefLanguageOptionsQueryConfig(
                                table_fqn=table_fqn,
                                lookback_days=scoped_lookback,
                                selected_geographies=scoped_geographies,
                            ),
                        )
                    ),
                    load_geography_options=lambda scoped_lookback, scoped_languages: (
                        load_brief_geography_options(
                            project_id,
                            BriefGeographyOptionsQueryConfig(
                                table_fqn=table_fqn,
                                lookback_days=scoped_lookback,
                                selected_languages=scoped_languages,
                            ),
                        )
                    ),
                    preserve_selected_in_options=lookback_changed,
                )
            )
            st.session_state["selected_languages"] = selected_languages
            st.session_state["selected_geographies"] = selected_geographies
            st.session_state["draft_selected_languages"] = list(selected_languages)
            st.session_state["draft_selected_geographies"] = list(
                selected_geographies
            )
            st.session_state["brief_last_lookback_days"] = lookback_days
            st.session_state["lookback_days"] = lookback_days
            st.session_state["feed_sort_order"] = feed_sort_order

            scope_signature = build_scope_signature(
                lookback_days,
                selected_languages,
                selected_geographies,
            )
            language_options_signature = build_language_options_signature(
                lookback_days,
                selected_geographies,
            )
            geography_options_signature = build_geography_options_signature(
                lookback_days,
                selected_languages,
            )
            st.session_state["brief_language_options_signature"] = (
                language_options_signature
            )
            st.session_state["brief_geography_options_signature"] = (
                geography_options_signature
            )

            current_page_number = reset_page_on_scope_change(
                st.session_state.get("brief_scope_signature"),
                scope_signature,
                current_page_number,
            )
            st.session_state["brief_scope_signature"] = scope_signature

            summary = load_brief_scope_summary(
                project_id,
                BriefScopeQueryConfig(
                    table_fqn=table_fqn,
                    lookback_days=scope_signature[0],
                    selected_languages=scope_signature[1],
                    selected_geographies=scope_signature[2],
                ),
            )
            total_rows = int(summary["row_count"])
            total_pages = compute_total_pages(total_rows, RECOMMENDED_PAGE_SIZE)
            current_page_number = clamp_page_number(
                current_page_number,
                total_rows,
                RECOMMENDED_PAGE_SIZE,
            )
            st.session_state["recommended_page"] = current_page_number

            rows_signature = build_rows_signature(
                scope_signature,
                feed_sort_order,
                current_page_number,
                RECOMMENDED_PAGE_SIZE,
            )
            st.session_state["brief_rows_signature"] = rows_signature
            rows, _ = load_brief_rows(
                project_id,
                BriefRowsQueryConfig(
                    table_fqn=table_fqn,
                    lookback_days=rows_signature[0][0],
                    selected_languages=rows_signature[0][1],
                    selected_geographies=rows_signature[0][2],
                    sort_order=rows_signature[1],
                    page_number=rows_signature[2],
                    page_size=rows_signature[3],
                ),
            )
        except Exception as exc:  # pragma: no cover - UI fallback
            if loading_placeholder is not None:
                loading_placeholder.empty()
            st.error(f"Query failed: {exc}")
            st.stop()

    pulse_dashboard = None
    try:
        if current_page == PAGE_PULSE:
            pulse_dashboard = load_pulse_dashboard(project_id, table_fqn)
            pipeline_status = (
                dict(pulse_dashboard.get("latest_snapshot") or {})
                if pulse_dashboard is not None
                else None
            )
        else:
            pipeline_status = load_pipeline_status(project_id, table_fqn)
    except Exception as exc:  # pragma: no cover - UI fallback
        if loading_placeholder is not None:
            loading_placeholder.empty()
        st.error(f"Query failed: {exc}")
        st.stop()

    if loading_placeholder is not None:
        loading_placeholder.empty()

    st.session_state["last_loaded_page"] = current_page
    if current_page == PAGE_BRIEF:
        st.session_state["last_loaded_brief_scope_signature"] = scope_signature
        st.session_state["last_loaded_brief_rows_signature"] = rows_signature
    pipeline_status_markup = render_pipeline_status(pipeline_status)

    render_global_header(
        current_page=current_page,
        pipeline_status_markup=pipeline_status_markup,
    )

    if current_page == PAGE_BRIEF:
        render_brief(
            language_options=language_options,
            geography_options=geography_options,
            summary=summary,
            recommended_rows=rows,
            current_page=int(st.session_state.get("recommended_page", 1)),
            total_pages=total_pages,
            total_rows=total_rows,
        )
    elif current_page == PAGE_PULSE:
        render_pulse(
            pulse_dashboard=pulse_dashboard,
        )
    else:
        render_methodology()


if __name__ == "__main__":
    main()
