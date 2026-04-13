from __future__ import annotations

import html

import streamlit as st

from constants import RECOMMENDED_PAGE_SIZE
from query_builder import paginate_rows
from ui_helpers import (
    format_float,
    format_geography,
    format_language,
    format_relative_time,
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
    language_value = format_language(row.get("language"))
    geography_value = format_geography(row.get("mentioned_country_name"))
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

    metadata_chips: list[str] = []
    if language_value != "Unknown":
        metadata_chips.append(
            f'<span class="tiq-mini-chip">Language: {html.escape(language_value)}</span>'
        )
    if geography_value != "Unknown":
        metadata_chips.append(
            f'<span class="tiq-mini-chip">Mentioned geography: {html.escape(geography_value)}</span>'
        )
    metadata_chips_html = "".join(metadata_chips)

    st.markdown(
        f"""
        <div class="tiq-card{compact_class}">
          <div style="align-items:flex-start;display:flex;gap:1rem;justify-content:space-between;">
            <div class="tiq-source-line">{source_name}</div>
            <div class="tiq-score-badge {badge_class}">{html.escape(happy_factor)} Happy Factor</div>
          </div>
          {headline_html}
          <div class="tiq-card-meta-row">
            {metadata_chips_html}
          </div>
          <div class="tiq-card-footer">
            <div class="tiq-card-meta-row">
              <span>{html.escape(published_display)}</span>
              <span>Tone: {tone_score}</span>
            </div>
            <div>{footer_link}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_page_masthead(
    *,
    title: str,
) -> None:
    masthead_container = st.container()
    with masthead_container:
        st.markdown('<div class="tiq-masthead-anchor"></div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="tiq-page-title tiq-masthead-title">{html.escape(title)}</div>',
            unsafe_allow_html=True,
        )
        # Date intentionally hidden for now pending the next masthead iteration.


def render_brief(
    *,
    lookback_days: int,
    feed_sort_order: str,
    summary: dict[str, float | int],
    recommended_rows: list[dict[str, object]],
) -> None:
    _render_page_masthead(
        title="Today's Global Optimism",
    )

    metric_columns = st.columns(4)
    with metric_columns[0]:
        render_metric_card(
            "Stories In View",
            summary["row_count"],
            icon_name="stories",
            accent_class="tiq-metric-card-mint",
        )
    with metric_columns[1]:
        render_metric_card(
            "Avg Happy Factor",
            summary["avg_happy_factor"],
            icon_name="average",
            accent_class="tiq-metric-card-sun",
        )
    with metric_columns[2]:
        render_metric_card(
            "Peak Positivity",
            summary["max_happy_factor"],
            icon_name="peak",
            accent_class="tiq-metric-card-sky",
        )
    with metric_columns[3]:
        render_metric_card(
            "Active Sources",
            summary["source_count"],
            icon_name="sources",
            accent_class="tiq-metric-card-ink",
        )

    st.markdown("<div style='height:0.8rem;'></div>", unsafe_allow_html=True)

    header_left, header_right = st.columns([6.5, 3.5], gap="medium")
    with header_left:
        st.markdown(
            f"""
            <div class="tiq-brief-header-copy">
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
    with header_right:
        st.markdown('<div class="tiq-sort-control-anchor"></div>', unsafe_allow_html=True)
        sort_label_col, sort_input_col = st.columns([1.15, 2.85], gap="small")
        with sort_label_col:
            st.markdown(
                '<div class="tiq-sort-inline-label">Sort feed</div>',
                unsafe_allow_html=True,
            )
        with sort_input_col:
            st.selectbox(
                "Sort feed",
                options=(
                    ["Least optimistic first", "Most optimistic first"]
                    if lookback_days == 1
                    else [
                        "Least optimistic first",
                        "Most optimistic first",
                        "Most recent news",
                        "Oldest news",
                    ]
                ),
                index=(
                    ["Least optimistic first", "Most optimistic first"]
                    if lookback_days == 1
                    else [
                        "Least optimistic first",
                        "Most optimistic first",
                        "Most recent news",
                        "Oldest news",
                    ]
                ).index(
                    feed_sort_order
                    if feed_sort_order
                    in (
                        {"Least optimistic first", "Most optimistic first"}
                        if lookback_days == 1
                        else {
                            "Least optimistic first",
                            "Most optimistic first",
                            "Most recent news",
                            "Oldest news",
                        }
                    )
                    else "Least optimistic first"
                ),
                key="feed_sort_order",
                label_visibility="collapsed",
            )
    st.markdown('<div class="tiq-section-divider"></div>', unsafe_allow_html=True)

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


def _format_count(value: object) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "0"


def _safe_percent(numerator: object, denominator: object) -> float:
    try:
        denominator_value = float(denominator)
        if denominator_value <= 0:
            return 0.0
        return round((float(numerator) / denominator_value) * 100, 1)
    except (TypeError, ValueError):
        return 0.0


def _render_supporting_stats(items: list[tuple[str, str]]) -> None:
    if not items:
        return
    columns = st.columns(len(items), gap="small")
    for column, (label, value) in zip(columns, items):
        with column:
            st.markdown(
                f"""
                <div class="tiq-pulse-stat-card">
                  <div class="tiq-pulse-stat-label">{html.escape(label)}</div>
                  <div class="tiq-pulse-stat-value">{html.escape(value)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _largest_bucket(rows: list[dict[str, object]]) -> tuple[str, int]:
    if not rows:
        return ("None", 0)
    top_row = max(rows, key=lambda row: int(row.get("row_count", 0)))
    return (
        str(top_row.get("bucket") or "None"),
        int(top_row.get("row_count", 0)),
    )


def render_pulse(
    *,
    pulse_dashboard: dict[str, object] | None,
) -> None:
    _render_page_masthead(
        title="Pulse",
    )

    if pulse_dashboard is None:
        render_empty_state(
            "Pipeline pulse is unavailable right now because the warehouse aggregates could not be loaded."
        )
        return

    latest_snapshot = dict(pulse_dashboard.get("latest_snapshot") or {})
    stage_snapshot = list(pulse_dashboard.get("stage_snapshot") or [])
    exclusion_breakdown = list(pulse_dashboard.get("exclusion_breakdown") or [])
    pipeline_trend = list(pulse_dashboard.get("pipeline_trend") or [])
    silver_cleanup_trend = list(pulse_dashboard.get("silver_cleanup_trend") or [])
    score_distribution = list(pulse_dashboard.get("score_distribution") or [])

    if not latest_snapshot:
        render_empty_state(
            "Pipeline pulse is unavailable right now because the latest warehouse snapshot is missing."
        )
        return

    bronze_row_count = int(latest_snapshot.get("bronze_row_count", 0))
    silver_row_count = int(latest_snapshot.get("silver_row_count", 0))
    silver_canonical_row_count = int(latest_snapshot.get("silver_canonical_row_count", 0))
    silver_duplicate_row_count = int(latest_snapshot.get("silver_duplicate_row_count", 0))
    gold_row_count = int(latest_snapshot.get("gold_row_count", 0))
    eligible_row_count = int(latest_snapshot.get("eligible_row_count", 0))
    ineligible_row_count = int(latest_snapshot.get("ineligible_row_count", 0))

    top_exclusion_bucket, top_exclusion_count = _largest_bucket(exclusion_breakdown)
    top_score_bucket, top_score_count = _largest_bucket(score_distribution)

    _render_chart_card(
        "From Intake To Feed",
        "A compact snapshot of how the current story pool narrows from landed records to feed-eligible stories.",
    )
    st.vega_lite_chart(
        stage_snapshot,
        {
            "height": 300,
            "transform": [
                {"joinaggregate": [{"op": "max", "field": "row_count", "as": "max_row_count"}]},
                {
                    "calculate": "datum.row_count + datum.max_row_count * 0.06",
                    "as": "label_row_count",
                },
            ],
            "layer": [
                {
                    "mark": {"type": "bar", "cornerRadiusTopLeft": 8, "cornerRadiusTopRight": 8},
                    "encoding": {
                        "x": {
                            "field": "stage",
                            "type": "ordinal",
                            "sort": [
                                "Bronze Landed",
                                "Silver Normalized",
                                "Silver Canonical",
                                "Gold Scored",
                                "Gold Eligible",
                            ],
                            "title": None,
                            "axis": {"labelAngle": -18, "labelColor": "#151515", "titleColor": "#151515"},
                        },
                        "y": {
                            "field": "row_count",
                            "type": "quantitative",
                            "title": "Rows",
                            "scale": {"nice": True},
                            "axis": {"labelColor": "#151515", "titleColor": "#151515"},
                        },
                        "color": {
                            "field": "stage",
                            "type": "nominal",
                            "legend": None,
                            "scale": {
                                "domain": [
                                    "Bronze Landed",
                                    "Silver Normalized",
                                    "Silver Canonical",
                                    "Gold Scored",
                                    "Gold Eligible",
                                ],
                                "range": ["#9aa094", "#72d9a8", "#00c975", "#2459a6", "#d79600"],
                            },
                        },
                        "tooltip": [
                            {"field": "stage", "type": "ordinal", "title": "Stage"},
                            {"field": "row_count", "type": "quantitative", "title": "Rows"},
                        ],
                    },
                },
                {
                    "mark": {
                        "type": "text",
                        "dy": -10,
                        "font": "Inter",
                        "fontSize": 12,
                        "fontWeight": 700,
                        "color": "#151515",
                    },
                    "encoding": {
                        "x": {
                            "field": "stage",
                            "type": "ordinal",
                            "sort": [
                                "Bronze Landed",
                                "Silver Normalized",
                                "Silver Canonical",
                                "Gold Scored",
                                "Gold Eligible",
                            ],
                        },
                        "y": {"field": "label_row_count", "type": "quantitative"},
                        "text": {"field": "row_count", "type": "quantitative", "format": ",d"},
                    },
                },
            ],
            "config": {"view": {"stroke": None}},
        },
        width="stretch",
    )
    _render_supporting_stats(
        [
            ("Bronze Landed", _format_count(bronze_row_count)),
            ("Silver Canonical Share", f"{_safe_percent(silver_canonical_row_count, silver_row_count)}%"),
            ("Gold Eligibility Share", f"{_safe_percent(eligible_row_count, gold_row_count)}%"),
        ]
    )

    st.markdown("<div style='height:0.6rem;'></div>", unsafe_allow_html=True)
    chart_left, chart_right = st.columns(2, gap="large")
    with chart_left:
        _render_chart_card(
            "Why Stories Do Not Reach The Feed",
            "This pie chart breaks the non-served Gold rows into the reasons they were excluded, so the viewer can see exactly what is present in the warehouse but not shown in the final feed.",
        )
        if exclusion_breakdown:
            st.vega_lite_chart(
                exclusion_breakdown,
                {
                    "mark": {"type": "arc", "innerRadius": 52, "outerRadius": 118},
                    "encoding": {
                        "theta": {"field": "row_count", "type": "quantitative"},
                        "color": {
                            "field": "bucket",
                            "type": "nominal",
                            "title": "Exclusion reason",
                            "scale": {
                                "range": ["#d79600", "#151515", "#5d7cf5", "#c96a20", "#8a8f86"]
                            },
                            "legend": {"labelColor": "#151515", "titleColor": "#151515"},
                        },
                        "tooltip": [
                            {"field": "bucket", "type": "nominal", "title": "Reason"},
                            {"field": "row_count", "type": "quantitative", "title": "Rows"},
                        ],
                    },
                    "config": {"view": {"stroke": None}},
                },
                width="stretch",
            )
            _render_supporting_stats(
                [
                    ("Not Served Rows", _format_count(ineligible_row_count)),
                    ("Largest Exclusion", top_exclusion_bucket),
                    ("Rows In Largest Bucket", _format_count(top_exclusion_count)),
                ]
            )
        else:
            render_empty_state("No excluded Gold rows are currently available to chart.", tone="soft")

    with chart_right:
        _render_chart_card(
            "Pipeline Trend Over Time",
            "Recent run history for Bronze landed rows, Silver canonical rows, and Gold scored rows. This makes step changes and pipeline instability visible immediately.",
        )
        if pipeline_trend:
            st.vega_lite_chart(
                pipeline_trend,
                {
                    "mark": {"type": "line", "point": True, "strokeWidth": 3},
                    "encoding": {
                        "x": {
                            "field": "run_label",
                            "type": "ordinal",
                            "title": "Recent pipeline runs",
                            "axis": {"labelColor": "#151515", "titleColor": "#151515"},
                        },
                        "y": {
                            "field": "row_count",
                            "type": "quantitative",
                            "title": "Rows",
                            "axis": {"labelColor": "#151515", "titleColor": "#151515"},
                        },
                        "color": {
                            "field": "stage",
                            "type": "nominal",
                            "title": "Stage",
                            "scale": {
                                "domain": [
                                    "Bronze Landed",
                                    "Silver Canonical",
                                    "Gold Scored",
                                ],
                                "range": ["#8a8f86", "#00c975", "#151515"],
                            },
                            "legend": {"labelColor": "#151515", "titleColor": "#151515"},
                        },
                        "tooltip": [
                            {"field": "run_label", "type": "ordinal", "title": "Run"},
                            {"field": "stage", "type": "nominal", "title": "Stage"},
                            {"field": "row_count", "type": "quantitative", "title": "Rows"},
                        ],
                    },
                    "config": {"view": {"stroke": None}},
                },
                width="stretch",
            )
            _render_supporting_stats(
                [
                    ("Latest Run", format_timestamp(latest_snapshot.get("audit_run_at"))),
                    ("Bronze To Gold Retention", f"{_safe_percent(gold_row_count, bronze_row_count)}%"),
                    ("Latest Gold Update", format_timestamp(latest_snapshot.get("latest_gold_ingested_at"))),
                ]
            )
        else:
            render_empty_state("No recent pipeline trend history is available to chart.", tone="soft")

    st.markdown("<div style='height:0.6rem;'></div>", unsafe_allow_html=True)
    chart_left, chart_right = st.columns(2, gap="large")
    with chart_left:
        _render_chart_card(
            "Silver Cleanup Efficiency",
            "Each recent run is split into canonical Silver rows and duplicate Silver rows, making the cleanup work of the Silver layer visible without adding operational clutter.",
        )
        if silver_cleanup_trend:
            st.vega_lite_chart(
                silver_cleanup_trend,
                {
                    "mark": {"type": "bar", "cornerRadiusTopLeft": 4, "cornerRadiusTopRight": 4},
                    "encoding": {
                        "x": {
                            "field": "run_label",
                            "type": "ordinal",
                            "title": "Recent pipeline runs",
                            "axis": {"labelColor": "#151515", "titleColor": "#151515"},
                        },
                        "y": {
                            "field": "row_count",
                            "type": "quantitative",
                            "title": "Rows",
                            "axis": {"labelColor": "#151515", "titleColor": "#151515"},
                        },
                        "color": {
                            "field": "bucket",
                            "type": "nominal",
                            "title": "Silver row type",
                            "scale": {
                                "domain": ["Silver Canonical", "Silver Duplicates"],
                                "range": ["#00c975", "#d79600"],
                            },
                            "legend": {"labelColor": "#151515", "titleColor": "#151515"},
                        },
                        "tooltip": [
                            {"field": "run_label", "type": "ordinal", "title": "Run"},
                            {"field": "bucket", "type": "nominal", "title": "Silver row type"},
                            {"field": "row_count", "type": "quantitative", "title": "Rows"},
                        ],
                    },
                    "config": {"view": {"stroke": None}},
                },
                width="stretch",
            )
            _render_supporting_stats(
                [
                    ("Canonical Silver Rows", _format_count(silver_canonical_row_count)),
                    ("Duplicate Silver Rows", _format_count(silver_duplicate_row_count)),
                    ("Duplicate Share", f"{_safe_percent(silver_duplicate_row_count, silver_row_count)}%"),
                ]
            )
        else:
            render_empty_state("No recent Silver cleanup history is available to chart.", tone="soft")

    with chart_right:
        _render_chart_card(
            "Gold Score Distribution",
            "A histogram of all current Gold rows by happy-factor bucket. This shows whether the warehouse is dominated by strong candidates, borderline rows, or clearly weak stories.",
        )
        if score_distribution:
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
                            "sort": None,
                            "axis": {"labelColor": "#151515", "titleColor": "#151515"},
                        },
                        "y": {
                            "field": "row_count",
                            "type": "quantitative",
                            "title": "Rows",
                            "axis": {"labelColor": "#151515", "titleColor": "#151515"},
                        },
                        "tooltip": [
                            {"field": "bucket", "type": "ordinal", "title": "Bucket"},
                            {"field": "row_count", "type": "quantitative", "title": "Rows"},
                        ],
                    },
                    "config": {"view": {"stroke": None}},
                },
                width="stretch",
            )
            _render_supporting_stats(
                [
                    ("Average Happy Factor", format_float(latest_snapshot.get("gold_avg_happy_factor"), digits=1)),
                    ("Peak Happy Factor", format_float(latest_snapshot.get("gold_max_happy_factor"), digits=1)),
                    ("Largest Score Bucket", f"{top_score_bucket} ({_format_count(top_score_count)})"),
                ]
            )
        else:
            render_empty_state("No Gold score distribution is available to chart.", tone="soft")


def render_methodology() -> None:
    _render_page_masthead(
        title="Methodology",
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
            from the Brief. The current feed reads the warehouse-defined eligible set directly, without an app-side
            minimum happy-factor slider and without a separate below-threshold exploration section. In practice that
            means the Brief shows only the stories Gold has already marked as positive-feed eligible.
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
