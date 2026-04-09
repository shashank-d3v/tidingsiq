from __future__ import annotations

import html
from datetime import datetime, timezone

import streamlit as st


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


def render_metric_card(label: str, value: object) -> None:
    st.markdown(
        f"""
        <div class="tiq-metric-card">
          <div class="tiq-metric-label">{html.escape(label)}</div>
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
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        value = value.astimezone(timezone.utc)
        month = value.strftime("%b")
        day = value.day
        year = value.year
        hour = value.strftime("%I").lstrip("0") or "12"
        minute = value.strftime("%M")
        meridiem = value.strftime("%p")
        return f"{month} {day}, {year} at {hour}:{minute} {meridiem} UTC"
    return "Unknown"


def format_relative_time(value: object) -> str:
    if not isinstance(value, datetime):
        return "Unknown"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    now_utc = datetime.now(timezone.utc)
    delta = now_utc - value.astimezone(timezone.utc)
    total_seconds = int(max(delta.total_seconds(), 0))
    if total_seconds < 3600:
        minutes = max(1, total_seconds // 60)
        unit = "minute" if minutes == 1 else "minutes"
        return f"{minutes} {unit} ago"
    if total_seconds < 86400:
        hours = total_seconds // 3600
        unit = "hour" if hours == 1 else "hours"
        return f"{hours} {unit} ago"
    days = total_seconds // 86400
    unit = "day" if days == 1 else "days"
    return f"{days} {unit} ago"


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


def render_empty_state(message: str) -> None:
    st.markdown(
        f'<div class="tiq-empty-state">{html.escape(message)}</div>',
        unsafe_allow_html=True,
    )


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


def render_pipeline_status(status: dict[str, object] | None, rows: list[dict[str, object]]) -> str:
    if status is not None:
        latest_ingested_at = format_timestamp(status.get("latest_gold_ingested_at"))
        gold_row_count = status.get("gold_row_count") or 0
        return f"""
        <div class="tiq-status-card">
          <div class="tiq-status-label">Pipeline Status</div>
          <div class="tiq-status-line"><span class="tiq-status-dot"></span>Connected to Gold Table</div>
          <div class="tiq-status-detail">Latest Gold ingestion: {html.escape(latest_ingested_at)}</div>
          <div class="tiq-status-detail">Current Gold rows: {html.escape(str(gold_row_count))}</div>
        </div>
        """

    if rows:
        latest_ingested_at = max(
            (
                row.get("ingested_at")
                for row in rows
                if isinstance(row.get("ingested_at"), datetime)
            ),
            default=None,
        )
        return f"""
        <div class="tiq-status-card">
          <div class="tiq-status-label">Pipeline Status</div>
          <div class="tiq-status-line"><span class="tiq-status-dot"></span>Connected to Gold Table</div>
          <div class="tiq-status-detail">Latest observed ingestion: {html.escape(format_timestamp(latest_ingested_at))}</div>
        </div>
        """

    return """
    <div class="tiq-status-card">
      <div class="tiq-status-label">Pipeline Status</div>
      <div class="tiq-status-line"><span class="tiq-status-dot"></span>Gold table reachable</div>
      <div class="tiq-status-detail">No rows matched the current filters.</div>
    </div>
    """
