from __future__ import annotations

import html
from datetime import date
from datetime import datetime, timedelta, timezone

import streamlit as st

from constants import PAGE_BRIEF, PAGE_METHODOLOGY, PAGE_PULSE


def render_logo(*, is_collapsed: bool = False) -> None:
    logo_state_class = "tiq-logo-collapsed" if is_collapsed else "tiq-logo-expanded"
    st.markdown(
        f"""
        <div class="tiq-logo {logo_state_class}">
          <div class="tiq-logo-mark-wrap">
            <div class="tiq-logo-mark"><span class="tiq-logo-mark-letter">T</span></div>
            <div class="tiq-logo-sparkle" aria-hidden="true">✦</div>
          </div>
          <div class="tiq-logo-copy">
            <div class="tiq-logo-wordmark">Tidings<span>IQ</span></div>
            <div class="tiq-logo-tagline">Positive Intel</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_global_header(*, current_page: str, pipeline_status_markup: str) -> None:
    nav_items = [PAGE_BRIEF, PAGE_PULSE, PAGE_METHODOLOGY]
    st.session_state.setdefault("header_segmented_nav", current_page)
    header_container = st.container()
    with header_container:
        st.markdown('<div class="tiq-global-header-anchor"></div>', unsafe_allow_html=True)
        left_col, status_col = st.columns([7.8, 0.8], gap="small")
        with left_col:
            brand_col, nav_col = st.columns([1.35, 6.65], gap="small")
            with brand_col:
                render_logo()
            with nav_col:
                st.markdown('<div class="tiq-global-nav-anchor"></div>', unsafe_allow_html=True)
                selected_page = st.segmented_control(
                    "Section",
                    options=nav_items,
                    default=current_page,
                    key="header_segmented_nav",
                    format_func=lambda page: {
                        PAGE_BRIEF: "⊞ The Brief",
                        PAGE_PULSE: "∿ Pulse",
                        PAGE_METHODOLOGY: "ⓘ Methodology",
                    }[page],
                    label_visibility="collapsed",
                    width="content",
                )
                if selected_page and selected_page != current_page:
                    st.session_state["current_page"] = selected_page
                    st.rerun()
        with status_col:
            st.markdown('<div class="tiq-global-status-anchor"></div>', unsafe_allow_html=True)
            st.markdown(pipeline_status_markup, unsafe_allow_html=True)


def _metric_icon_svg(icon_name: str) -> str:
    icons = {
        "stories": """
            <svg viewBox="0 0 32 32" aria-hidden="true">
              <rect x="5" y="7" width="22" height="18" rx="5"></rect>
              <path d="M10 12.5h12M10 16h9M10 19.5h7"></path>
              <path d="M20.5 7v18"></path>
            </svg>
        """,
        "average": """
            <svg viewBox="0 0 32 32" aria-hidden="true">
              <path d="M7 20.5c2.2-5 5.2-7.5 9-7.5 2.5 0 4.2.8 5.6 2.2 1 .9 1.8 2 3.4 3.3"></path>
              <path d="M20.5 10.5l4.5 1.4-1.4 4.5"></path>
              <circle cx="11" cy="22.5" r="1.6"></circle>
            </svg>
        """,
        "peak": """
            <svg viewBox="0 0 32 32" aria-hidden="true">
              <path d="M7.5 22.5L13 17l4 3.5 7.5-8"></path>
              <path d="M19.5 12.5H24v4.5"></path>
              <path d="M8 26h16"></path>
            </svg>
        """,
        "sources": """
            <svg viewBox="0 0 32 32" aria-hidden="true">
              <circle cx="16" cy="16" r="8.5"></circle>
              <path d="M7.5 16h17"></path>
              <path d="M16 7.5c2.5 2.2 4 5.2 4 8.5s-1.5 6.3-4 8.5"></path>
              <path d="M16 7.5c-2.5 2.2-4 5.2-4 8.5s1.5 6.3 4 8.5"></path>
            </svg>
        """,
    }
    return icons.get(icon_name, icons["stories"])


def render_metric_card(
    label: str,
    value: object,
    *,
    icon_name: str | None = None,
    accent_class: str = "tiq-metric-card-mint",
) -> None:
    icon_markup = ""
    if icon_name:
        icon_markup = (
            f'<div class="tiq-metric-icon">{_metric_icon_svg(icon_name)}</div>'
        )

    st.markdown(
        f"""
        <div class="tiq-metric-card {html.escape(accent_class)}">
          <div class="tiq-metric-card-top">
            <div class="tiq-metric-label">{html.escape(label)}</div>
            {icon_markup}
          </div>
          <div class="tiq-metric-value">{html.escape(str(value))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def score_badge_class(score: float | None) -> str:
    if score is None:
        return "tiq-score-soft"
    if score >= 85:
        return "tiq-score-strong"
    if score >= 70:
        return "tiq-score-mid"
    return "tiq-score-soft"


def format_timestamp(value: object) -> str:
    parsed_value = _coerce_datetime(value)
    if parsed_value is not None:
        value = parsed_value.astimezone(timezone.utc)
        month = value.strftime("%b")
        day = value.day
        year = value.year
        return f"{month} {day}, {year} (UTC)"
    return "Unknown"


def format_relative_time(value: object) -> str:
    parsed_value = _coerce_datetime(value)
    if parsed_value is None:
        return "Unknown"
    local_value = parsed_value.astimezone()
    local_now = datetime.now().astimezone()
    if local_value.date() == local_now.date():
        return "Today"
    if local_value.date() == (local_now.date() - timedelta(days=1)):
        return "Yesterday"
    if local_value.year == local_now.year:
        return local_value.strftime("%b %-d")
    return local_value.strftime("%b %-d, %Y")


def format_language(value: object) -> str:
    language = str(value or "").strip().lower()
    if not language or language == "und":
        return "Unknown"
    return language.upper()


def format_geography(value: object) -> str:
    geography = str(value or "").strip()
    return geography if geography else "Unknown"


def format_float(value: object, digits: int = 1) -> str:
    if value is None:
        return "Unknown"
    return f"{float(value):.{digits}f}"


def render_empty_state(message: str, *, tone: str = "default") -> None:
    tone_class = " tiq-empty-state-soft" if tone == "soft" else ""
    st.markdown(
        f'<div class="tiq-empty-state{tone_class}">{html.escape(message)}</div>',
        unsafe_allow_html=True,
    )


def render_loading_state(message: str, *, container: object | None = None) -> None:
    target = container if container is not None else st
    target.markdown(
        f"""
        <div class="tiq-loading-state" role="status" aria-live="polite">
          <div class="tiq-loading-graphic" aria-hidden="true">
            <span class="tiq-loading-bar tiq-loading-bar-1"></span>
            <span class="tiq-loading-bar tiq-loading-bar-2"></span>
            <span class="tiq-loading-bar tiq-loading-bar-3"></span>
            <span class="tiq-loading-bar tiq-loading-bar-4"></span>
            <span class="tiq-loading-line"></span>
          </div>
          <div class="tiq-loading-copy">{html.escape(message)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _coerce_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if isinstance(value, str) and value.strip():
        normalized_value = value.strip().replace("Z", "+00:00")
        try:
            parsed_value = datetime.fromisoformat(normalized_value)
        except ValueError:
            return None
        if parsed_value.tzinfo is None:
            return parsed_value.replace(tzinfo=timezone.utc)
        return parsed_value
    return None


def render_pagination(
    *,
    state_key: str,
    current_page: int,
    total_pages: int,
    total_rows: int,
    page_size: int,
    label: str,
) -> None:
    if total_rows <= page_size:
        return

    start_item = ((current_page - 1) * page_size) + 1
    end_item = min(current_page * page_size, total_rows)
    st.markdown('<div class="tiq-pagination-anchor"></div>', unsafe_allow_html=True)
    info_col, prev_col, next_col = st.columns([6, 1, 1])
    with info_col:
        st.markdown(
            (
                f'<div class="tiq-small-note">Showing {start_item}-{end_item} of '
                f"{total_rows} {html.escape(label)}. Page {current_page} of {total_pages}.</div>"
            ),
            unsafe_allow_html=True,
        )
    with prev_col:
        if st.button(
            "Previous",
            key=f"{state_key}_prev",
            width="stretch",
            disabled=current_page <= 1,
        ):
            st.session_state[state_key] = current_page - 1
            st.rerun()
    with next_col:
        if st.button(
            "Next",
            key=f"{state_key}_next",
            width="stretch",
            disabled=current_page >= total_pages,
        ):
            st.session_state[state_key] = current_page + 1
            st.rerun()


def render_pipeline_status(status: dict[str, object] | None) -> str:
    if status is not None:
        return """
        <div class="tiq-status-chip">
          <span class="tiq-status-dot"></span>
          <span>LIVE GOLD FEED</span>
        </div>
        """

    return """
    <div class="tiq-status-chip">
      <span class="tiq-status-dot"></span>
      <span>GOLD FEED READY</span>
    </div>
    """
