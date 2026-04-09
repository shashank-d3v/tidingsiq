from __future__ import annotations

import html

import streamlit as st

from constants import EXPLORE_PAGE_SIZE, RECOMMENDED_PAGE_SIZE
from query_builder import (
    build_eligibility_breakdown,
    build_score_distribution,
    build_source_rankings,
    build_timeline_data,
    paginate_rows,
)
from ui_helpers import (
    format_float,
    format_geography,
    format_language,
    format_relative_time,
    format_timestamp,
    render_empty_state,
    render_metric_card,
    render_pagination,
    score_badge_class,
)


def render_article_card(row: dict[str, object], *, compact: bool = False) -> None:
    title = html.escape(str(row.get("title") or "Untitled article"))
    source_name = html.escape(str(row.get("source_name") or "Unknown source"))
    url = str(row.get("url") or "").strip()
    link_target = html.escape(url) if url else ""
    published_value = row.get("published_at") or row.get("ingested_at")
    published_display = format_relative_time(published_value)
    published_detail = format_timestamp(published_value)
    language = html.escape(format_language(row.get("language")))
    geography = html.escape(format_geography(row.get("mentioned_country_name")))
    tone_score = html.escape(format_float(row.get("tone_score"), digits=1))
    happy_factor = format_float(row.get("happy_factor"), digits=1)
    badge_class = (
        score_badge_class(float(row["happy_factor"]))
        if row.get("happy_factor") is not None
        else score_badge_class(None)
    )
    compact_class = " tiq-card-compact" if compact else ""

    if url:
        headline_html = (
            f'<a class="tiq-card-headline" href="{link_target}" '
            f'target="_blank" rel="noopener noreferrer">{title}</a>'
        )
        footer_link = (
            f'<a href="{link_target}" target="_blank" rel="noopener noreferrer" '
            f'style="color:#151515;text-decoration:none;font-weight:700;">Read article</a>'
        )
    else:
        headline_html = f'<div class="tiq-card-headline">{title}</div>'
        footer_link = '<span style="font-weight:700;color:#676b63;">No source URL</span>'

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


def render_brief(
    *,
    lookback_days: int,
    summary: dict[str, float | int],
    recommended_rows: list[dict[str, object]],
    more_to_explore_rows: list[dict[str, object]],
) -> None:
    st.markdown(
        '<div class="tiq-page-title">Today\'s Global Optimism</div>',
        unsafe_allow_html=True,
    )

    metric_columns = st.columns(4)
    with metric_columns[0]:
        render_metric_card("Stories In View", summary["row_count"])
    with metric_columns[1]:
        render_metric_card("Avg Happy Factor", summary["avg_happy_factor"])
    with metric_columns[2]:
        render_metric_card("Peak Positivity", summary["max_happy_factor"])
    with metric_columns[3]:
        render_metric_card("Active Sources", summary["source_count"])

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
        render_empty_state("No recommended stories matched the current filters.")
    else:
        for row in paginated_recommended:
            render_article_card(row)
        render_pagination(
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
                render_article_card(row, compact=True)

        render_pagination(
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


def render_pulse(rows: list[dict[str, object]]) -> None:
    st.markdown('<div class="tiq-page-title">Pulse</div>', unsafe_allow_html=True)

    if not rows:
        render_empty_state("No records matched the current filters, so there is nothing to chart.")
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
                    "x": {
                        "field": "serving_date",
                        "type": "ordinal",
                        "title": "Serving date",
                        "axis": {"labelColor": "#151515", "titleColor": "#151515"},
                    },
                    "y": {
                        "field": "story_count",
                        "type": "quantitative",
                        "title": "Stories",
                        "axis": {"labelColor": "#151515", "titleColor": "#151515"},
                    },
                    "color": {
                        "field": "eligible_count",
                        "type": "quantitative",
                        "title": "Eligible stories",
                        "scale": {"scheme": "greens"},
                        "legend": {"labelColor": "#151515", "titleColor": "#151515"},
                    },
                    "tooltip": [
                        {"field": "serving_date", "type": "ordinal", "title": "Serving date"},
                        {"field": "story_count", "type": "quantitative", "title": "Stories"},
                        {"field": "eligible_count", "type": "quantitative", "title": "Eligible stories"},
                    ],
                },
                "config": {"view": {"stroke": None}},
            },
            width="stretch",
        )
    with timeline_right:
        st.vega_lite_chart(
            timeline_data,
            {
                "mark": {"type": "line", "point": True, "strokeWidth": 3, "color": "#00c975"},
                "encoding": {
                    "x": {
                        "field": "serving_date",
                        "type": "ordinal",
                        "title": "Serving date",
                        "axis": {"labelColor": "#151515", "titleColor": "#151515"},
                    },
                    "y": {
                        "field": "avg_happy_factor",
                        "type": "quantitative",
                        "title": "Avg happy factor",
                        "axis": {"labelColor": "#151515", "titleColor": "#151515"},
                    },
                    "tooltip": [
                        {"field": "serving_date", "type": "ordinal", "title": "Serving date"},
                        {"field": "avg_happy_factor", "type": "quantitative", "title": "Avg happy factor"},
                    ],
                },
                "config": {"view": {"stroke": None}},
            },
            width="stretch",
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
                    "mark": {"type": "bar", "cornerRadiusEnd": 4, "color": "#00c975"},
                    "encoding": {
                        "x": {
                            "field": "story_count",
                            "type": "quantitative",
                            "title": "Eligible stories",
                            "axis": {"labelColor": "#151515", "titleColor": "#151515"},
                        },
                        "y": {
                            "field": "source_name",
                            "type": "ordinal",
                            "sort": "-x",
                            "title": None,
                            "axis": {"labelColor": "#151515"},
                        },
                        "tooltip": [
                            {"field": "source_name", "type": "ordinal", "title": "Source"},
                            {"field": "story_count", "type": "quantitative", "title": "Eligible stories"},
                            {"field": "avg_happy_factor", "type": "quantitative", "title": "Avg happy factor"},
                        ],
                    },
                    "config": {"view": {"stroke": None}},
                },
                width="stretch",
            )
        else:
            render_empty_state("No eligible stories are available for source ranking.")

    with chart_right:
        _render_chart_card(
            "Score Distribution",
            "How the current filtered stories are distributed across the happy-factor range.",
        )
        st.vega_lite_chart(
            score_distribution,
            {
                "mark": {
                    "type": "bar",
                    "cornerRadiusTopLeft": 4,
                    "cornerRadiusTopRight": 4,
                    "color": "#d79600",
                },
                "encoding": {
                    "x": {
                        "field": "bucket",
                        "type": "ordinal",
                        "title": "Happy-factor bucket",
                        "axis": {"labelColor": "#151515", "titleColor": "#151515"},
                    },
                    "y": {
                        "field": "story_count",
                        "type": "quantitative",
                        "title": "Stories",
                        "axis": {"labelColor": "#151515", "titleColor": "#151515"},
                    },
                    "tooltip": [
                        {"field": "bucket", "type": "ordinal", "title": "Bucket"},
                        {"field": "story_count", "type": "quantitative", "title": "Stories"},
                    ],
                },
                "config": {"view": {"stroke": None}},
            },
            width="stretch",
        )

    st.markdown("<div style='height:0.4rem;'></div>", unsafe_allow_html=True)
    _render_chart_card(
        "Eligibility Breakdown",
        "How the current filtered feed divides between eligible stories and the persisted exclusion reasons.",
    )
    st.vega_lite_chart(
        eligibility_breakdown,
        {
            "mark": {"type": "bar", "cornerRadiusEnd": 4, "color": "#151515"},
            "encoding": {
                "x": {
                    "field": "story_count",
                    "type": "quantitative",
                    "title": "Stories",
                    "axis": {"labelColor": "#151515", "titleColor": "#151515"},
                },
                "y": {
                    "field": "bucket",
                    "type": "ordinal",
                    "sort": "-x",
                    "title": None,
                    "axis": {"labelColor": "#151515"},
                },
                "tooltip": [
                    {"field": "bucket", "type": "ordinal", "title": "Bucket"},
                    {"field": "story_count", "type": "quantitative", "title": "Stories"},
                ],
            },
            "config": {"view": {"stroke": None}},
        },
        width="stretch",
    )


def render_methodology() -> None:
    st.markdown('<div class="tiq-page-title">Methodology</div>', unsafe_allow_html=True)

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
