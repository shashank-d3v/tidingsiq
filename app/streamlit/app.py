from __future__ import annotations

import html
import os
from datetime import datetime, timezone
from typing import Final

import streamlit as st
from google.cloud import bigquery

from query_builder import (
    FeedQueryConfig,
    build_eligibility_breakdown,
    build_feed_query,
    build_score_distribution,
    build_source_rankings,
    build_timeline_data,
    paginate_rows,
    split_feed_rows,
    summarize_feed,
)


DEFAULT_PROJECT_ID = os.getenv("TIDINGSIQ_GCP_PROJECT", "tidingsiq-dev")
DEFAULT_TABLE_FQN = os.getenv(
    "TIDINGSIQ_GOLD_TABLE",
    f"{DEFAULT_PROJECT_ID}.gold.positive_news_feed",
)

PAGE_BRIEF: Final[str] = "The Brief"
PAGE_PULSE: Final[str] = "Pulse"
PAGE_METHODOLOGY: Final[str] = "Methodology"
LOOKBACK_OPTIONS: Final[list[int]] = [1, 3, 7, 30]
RESULT_LIMIT_OPTIONS: Final[list[int]] = [25, 50, 100, 200]
RECOMMENDED_PAGE_SIZE: Final[int] = 10
EXPLORE_PAGE_SIZE: Final[int] = 6


st.set_page_config(
    page_title="TidingsIQ",
    layout="wide",
    initial_sidebar_state="expanded",
)


APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Playfair+Display:wght@700&family=Outfit:wght@600;700&display=swap');

:root {
  --tiq-mint: #00d17a;
  --tiq-mint-soft: #e8fbf1;
  --tiq-amber: #ffb800;
  --tiq-charcoal: #1a1a1a;
  --tiq-offwhite: #f7f7f5;
  --tiq-border: #ecece7;
  --tiq-slate: #6f766f;
  --tiq-card-shadow: 0 8px 30px rgba(26, 26, 26, 0.05);
}

.stApp {
  background: var(--tiq-offwhite);
}

[data-testid="stSidebar"] {
  background: #ffffff;
  border-right: 1px solid var(--tiq-border);
}

[data-testid="stSidebar"] .stRadio > div {
  gap: 0.5rem;
}

[data-testid="stSidebar"] .stRadio label {
  background: #ffffff;
  border: 1px solid transparent;
  border-radius: 14px;
  color: var(--tiq-slate);
  font-weight: 600;
  padding: 0.75rem 0.9rem;
}

[data-testid="stSidebar"] .stRadio label:has(input:checked) {
  background: var(--tiq-mint-soft);
  border-color: #d3f5e4;
  color: #105b3a;
}

[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stSlider label,
[data-testid="stSidebar"] .stRadio label p {
  font-family: "Inter", sans-serif;
}

.tiq-brand {
  color: var(--tiq-charcoal);
  font-family: "Playfair Display", serif;
  font-size: 2rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  margin-bottom: 1rem;
}

.tiq-caption {
  color: var(--tiq-slate);
  font-family: "Inter", sans-serif;
  font-size: 0.95rem;
  line-height: 1.6;
  margin-bottom: 1.5rem;
  max-width: 42rem;
}

.tiq-page-title {
  color: var(--tiq-charcoal);
  font-family: "Playfair Display", serif;
  font-size: 3.3rem;
  font-weight: 700;
  letter-spacing: -0.04em;
  line-height: 1.04;
  margin: 0 0 0.75rem;
}

.tiq-page-subtitle {
  color: var(--tiq-slate);
  font-family: "Inter", sans-serif;
  font-size: 1.05rem;
  line-height: 1.7;
  margin-bottom: 2rem;
  max-width: 46rem;
}

.tiq-section-header {
  align-items: baseline;
  border-bottom: 1px solid var(--tiq-border);
  display: flex;
  justify-content: space-between;
  margin: 0 0 1rem;
  padding-bottom: 0.9rem;
}

.tiq-section-title {
  color: var(--tiq-charcoal);
  font-family: "Playfair Display", serif;
  font-size: 1.75rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  margin: 0;
}

.tiq-section-subtitle {
  color: var(--tiq-slate);
  font-family: "Inter", sans-serif;
  font-size: 0.92rem;
  margin-top: 0.2rem;
}

.tiq-pill {
  background: var(--tiq-mint-soft);
  border-radius: 999px;
  color: #14724a;
  display: inline-block;
  font-family: "Inter", sans-serif;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  margin-left: 0.7rem;
  padding: 0.22rem 0.55rem;
  text-transform: uppercase;
  vertical-align: middle;
}

.tiq-card {
  background: #ffffff;
  border: 1px solid var(--tiq-border);
  border-radius: 28px;
  box-shadow: var(--tiq-card-shadow);
  margin-bottom: 1rem;
  padding: 1.4rem 1.5rem;
}

.tiq-card-compact {
  min-height: 195px;
}

.tiq-card-headline {
  color: var(--tiq-charcoal);
  display: block;
  font-family: "Playfair Display", serif;
  font-size: 1.35rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.25;
  margin: 0.85rem 0 1rem;
  text-decoration: none;
}

.tiq-card-headline:hover {
  color: #14724a;
}

.tiq-card-meta-row,
.tiq-card-footer {
  color: var(--tiq-slate);
  display: flex;
  flex-wrap: wrap;
  font-family: "Inter", sans-serif;
  font-size: 0.82rem;
  gap: 0.75rem;
}

.tiq-card-footer {
  border-top: 1px solid #f0f0eb;
  justify-content: space-between;
  margin-top: 1.1rem;
  padding-top: 1rem;
}

.tiq-source-line {
  align-items: center;
  color: #8c9087;
  display: flex;
  flex-wrap: wrap;
  font-family: "Inter", sans-serif;
  font-size: 0.76rem;
  font-weight: 700;
  gap: 0.5rem;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}

.tiq-score-badge {
  border-radius: 999px;
  display: inline-block;
  font-family: "Inter", sans-serif;
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.35rem 0.7rem;
}

.tiq-score-strong {
  background: #e8fbf1;
  border: 1px solid #c8f0db;
  color: #14724a;
}

.tiq-score-mid {
  background: #f3fff9;
  border: 1px solid #dcf7ea;
  color: #1f8a5a;
}

.tiq-score-soft {
  background: #fff6e2;
  border: 1px solid #ffe4a5;
  color: #986a00;
}

.tiq-mini-chip {
  background: #f6f6f1;
  border-radius: 999px;
  color: #5f655e;
  display: inline-block;
  font-family: "Inter", sans-serif;
  font-size: 0.74rem;
  font-weight: 600;
  padding: 0.25rem 0.55rem;
}

.tiq-metric-card {
  background: #ffffff;
  border: 1px solid var(--tiq-border);
  border-radius: 26px;
  box-shadow: var(--tiq-card-shadow);
  padding: 1.15rem 1.2rem;
}

.tiq-metric-label {
  color: #8c9087;
  font-family: "Inter", sans-serif;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  margin-bottom: 0.5rem;
  text-transform: uppercase;
}

.tiq-metric-value {
  color: var(--tiq-charcoal);
  font-family: "Outfit", sans-serif;
  font-size: 2rem;
  font-weight: 700;
}

.tiq-status-card {
  background: #f7faf8;
  border: 1px solid var(--tiq-border);
  border-radius: 22px;
  margin-top: 1rem;
  padding: 1rem 1rem 0.95rem;
}

.tiq-status-label {
  color: #8c9087;
  font-family: "Inter", sans-serif;
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  margin-bottom: 0.45rem;
  text-transform: uppercase;
}

.tiq-status-line {
  align-items: center;
  color: #14724a;
  display: flex;
  font-family: "Inter", sans-serif;
  font-size: 0.88rem;
  font-weight: 600;
  gap: 0.45rem;
}

.tiq-status-dot {
  background: var(--tiq-mint);
  border-radius: 999px;
  display: inline-block;
  height: 0.55rem;
  width: 0.55rem;
}

.tiq-status-detail {
  color: var(--tiq-slate);
  font-family: "Inter", sans-serif;
  font-size: 0.82rem;
  margin-top: 0.45rem;
}

.tiq-empty-state {
  background: #ffffff;
  border: 1px dashed #d9ddd5;
  border-radius: 28px;
  color: var(--tiq-slate);
  font-family: "Inter", sans-serif;
  padding: 2.5rem 1.4rem;
  text-align: center;
}

.tiq-method-card {
  background: #ffffff;
  border: 1px solid var(--tiq-border);
  border-radius: 30px;
  box-shadow: var(--tiq-card-shadow);
  margin-bottom: 1rem;
  padding: 1.5rem;
}

.tiq-method-title {
  color: var(--tiq-charcoal);
  font-family: "Playfair Display", serif;
  font-size: 1.45rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0 0 0.75rem;
}

.tiq-method-body {
  color: var(--tiq-slate);
  font-family: "Inter", sans-serif;
  font-size: 0.98rem;
  line-height: 1.75;
}

.tiq-method-body strong {
  color: var(--tiq-charcoal);
}

.tiq-small-note {
  color: var(--tiq-slate);
  font-family: "Inter", sans-serif;
  font-size: 0.82rem;
  margin-top: 0.3rem;
}

.block-container {
  padding-top: 2rem;
  padding-bottom: 3rem;
}
</style>
"""


@st.cache_resource
def get_bigquery_client(project_id: str) -> bigquery.Client:
    return bigquery.Client(project=project_id)


def _to_query_parameters(
    parameters: list[tuple[str, str, object]],
) -> list[bigquery.ScalarQueryParameter]:
    return [
        bigquery.ScalarQueryParameter(name, type_name, value)
        for name, type_name, value in parameters
    ]


@st.cache_data(ttl=300, show_spinner=False)
def load_feed(
    project_id: str,
    config: FeedQueryConfig,
) -> tuple[list[dict[str, object]], str]:
    client = get_bigquery_client(project_id)
    sql, parameter_specs = build_feed_query(config)
    query_job = client.query(
        sql,
        job_config=bigquery.QueryJobConfig(
            query_parameters=_to_query_parameters(parameter_specs)
        ),
    )
    rows = [dict(row.items()) for row in query_job.result()]
    return rows, sql


@st.cache_data(ttl=300, show_spinner=False)
def load_pipeline_status(project_id: str, table_fqn: str) -> dict[str, object] | None:
    metrics_table = _build_metrics_table_fqn(table_fqn)
    if metrics_table is None:
        return None

    sql = f"""
select
  audit_run_at,
  gold_row_count,
  latest_gold_ingested_at,
  latest_gold_published_at
from `{metrics_table}`
order by audit_run_at desc
limit 1
"""
    client = get_bigquery_client(project_id)
    try:
        rows = list(client.query(sql).result())
    except Exception:
        return None
    if not rows:
        return None
    return dict(rows[0].items())


def _build_metrics_table_fqn(table_fqn: str) -> str | None:
    parts = table_fqn.split(".")
    if len(parts) != 3:
        return None
    return f"{parts[0]}.{parts[1]}.pipeline_run_metrics"


def _render_metric_card(label: str, value: object) -> None:
    st.markdown(
        f"""
        <div class="tiq-metric-card">
          <div class="tiq-metric-label">{html.escape(label)}</div>
          <div class="tiq-metric-value">{html.escape(str(value))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _score_badge_class(score: float | None) -> str:
    if score is None:
        return "tiq-score-soft"
    if score >= 85:
        return "tiq-score-strong"
    if score >= 70:
        return "tiq-score-mid"
    return "tiq-score-soft"


def _format_timestamp(value: object) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return "Unknown"


def _format_relative_time(value: object) -> str:
    if not isinstance(value, datetime):
        return "Unknown"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    now_utc = datetime.now(timezone.utc)
    delta = now_utc - value.astimezone(timezone.utc)
    total_seconds = int(max(delta.total_seconds(), 0))
    if total_seconds < 3600:
        minutes = max(1, total_seconds // 60)
        return f"{minutes}m ago"
    if total_seconds < 86400:
        hours = total_seconds // 3600
        return f"{hours}h ago"
    days = total_seconds // 86400
    return f"{days}d ago"


def _format_language(value: object) -> str:
    language = str(value or "").strip().lower()
    if not language or language == "und":
        return "Unknown"
    return language.upper()


def _format_geography(value: object) -> str:
    geography = str(value or "").strip()
    return geography if geography else "Unknown"


def _format_float(value: object, digits: int = 1) -> str:
    if value is None:
        return "Unknown"
    return f"{float(value):.{digits}f}"


def _render_article_card(row: dict[str, object], *, compact: bool = False) -> None:
    title = html.escape(str(row.get("title") or "Untitled article"))
    source_name = html.escape(str(row.get("source_name") or "Unknown source"))
    url = str(row.get("url") or "").strip()
    link_target = html.escape(url) if url else ""
    published_value = row.get("published_at") or row.get("ingested_at")
    published_display = _format_relative_time(published_value)
    published_detail = _format_timestamp(published_value)
    language = html.escape(_format_language(row.get("language")))
    geography = html.escape(_format_geography(row.get("mentioned_country_name")))
    tone_score = html.escape(_format_float(row.get("tone_score"), digits=1))
    happy_factor = _format_float(row.get("happy_factor"), digits=1)
    badge_class = _score_badge_class(float(row["happy_factor"])) if row.get("happy_factor") is not None else _score_badge_class(None)
    compact_class = " tiq-card-compact" if compact else ""

    if url:
        headline_html = (
            f'<a class="tiq-card-headline" href="{link_target}" '
            f'target="_blank" rel="noopener noreferrer">{title}</a>'
        )
        footer_link = (
            f'<a href="{link_target}" target="_blank" rel="noopener noreferrer" '
            f'style="color:#1a1a1a;text-decoration:none;font-weight:700;">Read article</a>'
        )
    else:
        headline_html = f'<div class="tiq-card-headline">{title}</div>'
        footer_link = '<span style="font-weight:700;color:#8c9087;">No source URL</span>'

    st.markdown(
        f"""
        <div class="tiq-card{compact_class}">
          <div style="align-items:flex-start;display:flex;gap:1rem;justify-content:space-between;">
            <div class="tiq-source-line">{source_name}</div>
            <div class="tiq-score-badge {badge_class}">{html.escape(happy_factor)} Happy Factor</div>
          </div>
          {headline_html}
          <div class="tiq-card-meta-row">
            <span class="tiq-mini-chip">Language: {language}</span>
            <span class="tiq-mini-chip">Mentioned geography: {geography}</span>
          </div>
          <div class="tiq-card-footer">
            <div class="tiq-card-meta-row">
              <span>{html.escape(published_display)}</span>
              <span>Tone: {tone_score}</span>
              <span>{html.escape(published_detail)}</span>
            </div>
            <div>{footer_link}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_pagination(
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
            use_container_width=True,
            disabled=current_page <= 1,
        ):
            st.session_state[state_key] = current_page - 1
            st.rerun()
    with next_col:
        if st.button(
            "Next",
            key=f"{state_key}_next",
            use_container_width=True,
            disabled=current_page >= total_pages,
        ):
            st.session_state[state_key] = current_page + 1
            st.rerun()


def _render_empty_state(message: str) -> None:
    st.markdown(
        f'<div class="tiq-empty-state">{html.escape(message)}</div>',
        unsafe_allow_html=True,
    )


def _render_brief(
    *,
    lookback_days: int,
    summary: dict[str, float | int],
    recommended_rows: list[dict[str, object]],
    more_to_explore_rows: list[dict[str, object]],
) -> None:
    st.markdown(
        """
        <div class="tiq-page-title">Today's Global Optimism</div>
        <div class="tiq-page-subtitle">
          A curated readout of constructive stories from the live Gold feed, ranked by
          guardrailed happy factor and grouped into trusted picks versus broader stories worth exploring.
        </div>
        """,
        unsafe_allow_html=True,
    )

    metric_columns = st.columns(4)
    with metric_columns[0]:
        _render_metric_card("Stories In View", summary["row_count"])
    with metric_columns[1]:
        _render_metric_card("Avg Happy Factor", summary["avg_happy_factor"])
    with metric_columns[2]:
        _render_metric_card("Peak Positivity", summary["max_happy_factor"])
    with metric_columns[3]:
        _render_metric_card("Active Sources", summary["source_count"])

    st.markdown("<div style='height:1.25rem;'></div>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="tiq-section-header">
          <div>
            <div class="tiq-section-title">Recommended <span class="tiq-pill">Trusted</span></div>
            <div class="tiq-section-subtitle">
              Best positive picks from the last {lookback_days} day{'s' if lookback_days != 1 else ''}.
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    paginated_recommended, current_page, total_pages, total_rows = paginate_rows(
        recommended_rows,
        page_number=int(st.session_state.get("recommended_page", 1)),
        page_size=RECOMMENDED_PAGE_SIZE,
    )
    st.session_state["recommended_page"] = current_page

    if not recommended_rows:
        _render_empty_state("No recommended stories matched the current filters.")
    else:
        for row in paginated_recommended:
            _render_article_card(row)
        _render_pagination(
            state_key="recommended_page",
            current_page=current_page,
            total_pages=total_pages,
            total_rows=total_rows,
            page_size=RECOMMENDED_PAGE_SIZE,
            label="recommended stories",
        )

    if more_to_explore_rows:
        st.markdown("<div style='height:1.5rem;'></div>", unsafe_allow_html=True)
        st.markdown(
            """
            <div class="tiq-section-header">
              <div>
                <div class="tiq-section-title">More To Explore</div>
                <div class="tiq-section-subtitle">
                  Stories that fell below the default feed threshold but may still be worth a look.
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        paginated_explore, current_explore_page, explore_total_pages, explore_total_rows = paginate_rows(
            more_to_explore_rows,
            page_number=int(st.session_state.get("explore_page", 1)),
            page_size=EXPLORE_PAGE_SIZE,
        )
        st.session_state["explore_page"] = current_explore_page

        explore_columns = st.columns(2)
        for index, row in enumerate(paginated_explore):
            with explore_columns[index % 2]:
                _render_article_card(row, compact=True)

        _render_pagination(
            state_key="explore_page",
            current_page=current_explore_page,
            total_pages=explore_total_pages,
            total_rows=explore_total_rows,
            page_size=EXPLORE_PAGE_SIZE,
            label="exploratory stories",
        )


def _render_chart_card(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="tiq-method-card" style="margin-bottom:0.75rem;">
          <div class="tiq-method-title" style="font-size:1.2rem;margin-bottom:0.35rem;">{html.escape(title)}</div>
          <div class="tiq-small-note">{html.escape(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_pulse(rows: list[dict[str, object]]) -> None:
    st.markdown(
        """
        <div class="tiq-page-title">Pulse</div>
        <div class="tiq-page-subtitle">
          A live analytical readout of the current Gold feed: how positivity shifts over time,
          which sources contribute the most eligible stories, and how the feed is shaped by guardrails.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not rows:
        _render_empty_state("No records matched the current filters, so there is nothing to chart.")
        return

    timeline_data = build_timeline_data(rows)
    source_rankings = build_source_rankings(rows)
    score_distribution = build_score_distribution(rows)
    eligibility_breakdown = build_eligibility_breakdown(rows)

    _render_chart_card(
        "Positivity Over Time",
        "Daily story volume, eligible-story volume, and average happy factor across the current filtered feed.",
    )
    timeline_left, timeline_right = st.columns(2)
    with timeline_left:
        st.vega_lite_chart(
            timeline_data,
            {
                "mark": {"type": "bar", "cornerRadiusEnd": 3},
                "encoding": {
                    "x": {"field": "serving_date", "type": "ordinal", "title": "Serving date"},
                    "y": {"field": "story_count", "type": "quantitative", "title": "Stories"},
                    "color": {
                        "field": "eligible_count",
                        "type": "quantitative",
                        "title": "Eligible stories",
                        "scale": {"scheme": "greens"},
                    },
                    "tooltip": [
                        {"field": "serving_date", "type": "ordinal", "title": "Serving date"},
                        {"field": "story_count", "type": "quantitative", "title": "Stories"},
                        {
                            "field": "eligible_count",
                            "type": "quantitative",
                            "title": "Eligible stories",
                        },
                    ],
                },
            },
            use_container_width=True,
        )
    with timeline_right:
        st.vega_lite_chart(
            timeline_data,
            {
                "mark": {"type": "line", "point": True, "strokeWidth": 3, "color": "#00d17a"},
                "encoding": {
                    "x": {"field": "serving_date", "type": "ordinal", "title": "Serving date"},
                    "y": {
                        "field": "avg_happy_factor",
                        "type": "quantitative",
                        "title": "Avg happy factor",
                    },
                    "tooltip": [
                        {"field": "serving_date", "type": "ordinal", "title": "Serving date"},
                        {
                            "field": "avg_happy_factor",
                            "type": "quantitative",
                            "title": "Avg happy factor",
                        },
                    ],
                },
            },
            use_container_width=True,
        )

    chart_left, chart_right = st.columns(2)
    with chart_left:
        _render_chart_card(
            "Top Positive Sources",
            "Eligible-story counts in the current filtered window, with average happy factor for context.",
        )
        if source_rankings:
            st.vega_lite_chart(
                source_rankings,
                {
                    "mark": {"type": "bar", "cornerRadiusEnd": 4, "color": "#00d17a"},
                    "encoding": {
                        "x": {
                            "field": "story_count",
                            "type": "quantitative",
                            "title": "Eligible stories",
                        },
                        "y": {
                            "field": "source_name",
                            "type": "ordinal",
                            "sort": "-x",
                            "title": None,
                        },
                        "tooltip": [
                            {"field": "source_name", "type": "ordinal", "title": "Source"},
                            {
                                "field": "story_count",
                                "type": "quantitative",
                                "title": "Eligible stories",
                            },
                            {
                                "field": "avg_happy_factor",
                                "type": "quantitative",
                                "title": "Avg happy factor",
                            },
                        ],
                    },
                },
                use_container_width=True,
            )
        else:
            _render_empty_state("No eligible stories are available for source ranking.")

    with chart_right:
        _render_chart_card(
            "Score Distribution",
            "How the current filtered stories are distributed across the happy-factor range.",
        )
        st.vega_lite_chart(
            score_distribution,
            {
                "mark": {"type": "bar", "cornerRadiusTopLeft": 4, "cornerRadiusTopRight": 4, "color": "#ffb800"},
                "encoding": {
                    "x": {"field": "bucket", "type": "ordinal", "title": "Happy-factor bucket"},
                    "y": {"field": "story_count", "type": "quantitative", "title": "Stories"},
                    "tooltip": [
                        {"field": "bucket", "type": "ordinal", "title": "Bucket"},
                        {"field": "story_count", "type": "quantitative", "title": "Stories"},
                    ],
                },
            },
            use_container_width=True,
        )

    st.markdown("<div style='height:0.4rem;'></div>", unsafe_allow_html=True)
    _render_chart_card(
        "Eligibility Breakdown",
        "How the current filtered feed divides between eligible stories and the persisted exclusion reasons.",
    )
    st.vega_lite_chart(
        eligibility_breakdown,
        {
            "mark": {"type": "bar", "cornerRadiusEnd": 4, "color": "#1a1a1a"},
            "encoding": {
                "x": {"field": "story_count", "type": "quantitative", "title": "Stories"},
                "y": {
                    "field": "bucket",
                    "type": "ordinal",
                    "sort": "-x",
                    "title": None,
                },
                "tooltip": [
                    {"field": "bucket", "type": "ordinal", "title": "Bucket"},
                    {"field": "story_count", "type": "quantitative", "title": "Stories"},
                ],
            },
        },
        use_container_width=True,
    )


def _render_methodology() -> None:
    st.markdown(
        """
        <div class="tiq-page-title">Methodology</div>
        <div class="tiq-page-subtitle">
          The feed is intentionally explainable: score logic lives in Gold, eligibility is persisted,
          and the app remains a thin presentation layer over the warehouse.
        </div>
        """,
        unsafe_allow_html=True,
    )

    sections = [
        (
            "What TidingsIQ Measures",
            """
            <strong>TidingsIQ ranks constructive stories.</strong> The app is not claiming to measure
            objective happiness or emotional truth. It is a positive-news intelligence feed built to surface
            stories that are more constructive and more suitable for a positive experience.
            """,
        ),
        (
            "How The Score Works",
            """
            <strong>base_happy_factor</strong> is a tone-normalized score on a 0 to 100 scale. The final
            <strong>happy_factor</strong> applies title allow bonuses and deny penalties on top of that base score.
            The current persisted score version is the guardrailed tone model, so the app reads a warehouse result
            rather than recalculating sentiment in the frontend.
            """,
        ),
        (
            "How Feed Eligibility Works",
            """
            <strong>Score and eligibility are separate.</strong> An article can have a persisted score and still be excluded
            from the default feed. The current eligibility gate requires a happy factor of at least <strong>65</strong>,
            blocks hard-deny title hits, and excludes unresolved soft-deny titles. That is why the app can show
            both trusted recommendations and below-threshold stories without inventing new logic in the UI.
            """,
        ),
        (
            "How The Data Pipeline Works",
            """
            <strong>Bronze</strong> lands GDELT article metadata. <strong>Silver</strong> normalizes and deduplicates it.
            <strong>Gold</strong> computes the final happy factor, guardrail metadata, eligibility state, and the detected
            language plus article-mentioned geography that the app now displays. <strong>Streamlit</strong> then reads only
            the Gold serving table and presents the feed locally on your device.
            """,
        ),
        (
            "Known Limitations",
            """
            <strong>Language can be inferred.</strong> The detected language metadata is useful, but it should not be presented
            as guaranteed source language. <strong>Mentioned geography reflects article geography</strong>, not publisher origin.
            The feed is batch-oriented rather than real-time, and title guardrails improve explainability without pretending
            to fully understand every article context.
            """,
        ),
    ]

    for title, body in sections:
        st.markdown(
            f"""
            <div class="tiq-method-card">
              <div class="tiq-method-title">{html.escape(title)}</div>
              <div class="tiq-method-body">{body}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_pipeline_status(status: dict[str, object] | None, rows: list[dict[str, object]]) -> str:
    if status is not None:
        latest_ingested_at = _format_timestamp(status.get("latest_gold_ingested_at"))
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
          <div class="tiq-status-detail">Latest observed ingestion: {html.escape(_format_timestamp(latest_ingested_at))}</div>
        </div>
        """

    return """
    <div class="tiq-status-card">
      <div class="tiq-status-label">Pipeline Status</div>
      <div class="tiq-status-line"><span class="tiq-status-dot"></span>Gold table reachable</div>
      <div class="tiq-status-detail">No rows matched the current filters.</div>
    </div>
    """


def _initialize_state() -> None:
    st.session_state.setdefault("current_page", PAGE_BRIEF)
    st.session_state.setdefault("recommended_page", 1)
    st.session_state.setdefault("explore_page", 1)


def main() -> None:
    _initialize_state()
    st.markdown(APP_CSS, unsafe_allow_html=True)

    with st.sidebar:
        st.markdown('<div class="tiq-brand">TidingsIQ</div>', unsafe_allow_html=True)
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
            value=65,
            step=5,
        )
        lookback_days = st.radio(
            "Lookback Window",
            options=LOOKBACK_OPTIONS,
            horizontal=True,
            format_func=lambda value: f"{value}d",
        )
        row_limit = st.selectbox(
            "Result Limit",
            options=RESULT_LIMIT_OPTIONS,
            index=RESULT_LIMIT_OPTIONS.index(100),
            format_func=lambda value: f"{value} rows",
        )
        status_placeholder = st.empty()

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

    pipeline_status = load_pipeline_status(DEFAULT_PROJECT_ID, DEFAULT_TABLE_FQN)
    status_placeholder.markdown(
        _render_pipeline_status(pipeline_status, rows),
        unsafe_allow_html=True,
    )

    recommended_rows, more_to_explore_rows = split_feed_rows(rows)
    visible_rows = recommended_rows + more_to_explore_rows
    summary = summarize_feed(visible_rows)

    st.markdown(
        """
        <div class="tiq-caption">
          Positive news intelligence built on GDELT, BigQuery, Bruin, and Streamlit.
          This local-first experience reads live data from the Gold serving table and keeps ranking logic in the warehouse.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if current_page == PAGE_BRIEF:
        _render_brief(
            lookback_days=lookback_days,
            summary=summary,
            recommended_rows=recommended_rows,
            more_to_explore_rows=more_to_explore_rows,
        )
    elif current_page == PAGE_PULSE:
        _render_pulse(rows)
    else:
        _render_methodology()


if __name__ == "__main__":
    main()
