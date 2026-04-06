from __future__ import annotations

import os
from datetime import datetime, timezone

import streamlit as st
from google.cloud import bigquery

from query_builder import (
    FeedQueryConfig,
    build_feed_query,
    summarize_feed,
)


DEFAULT_PROJECT_ID = os.getenv("TIDINGSIQ_GCP_PROJECT", "tidingsiq-dev")
DEFAULT_TABLE_FQN = os.getenv(
    "TIDINGSIQ_GOLD_TABLE",
    f"{DEFAULT_PROJECT_ID}.gold.positive_news_feed",
)


st.set_page_config(
    page_title="TidingsIQ",
    layout="wide",
)


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


def _format_timestamp(value: object) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return "Unknown"


def main() -> None:
    st.title("TidingsIQ")
    st.caption(
        "Positive news intelligence feed built on GDELT, BigQuery, Bruin, and Streamlit."
    )

    with st.sidebar:
        st.header("Filters")
        project_id = st.text_input("GCP project", value=DEFAULT_PROJECT_ID)
        table_fqn = st.text_input("Gold table", value=DEFAULT_TABLE_FQN)
        min_happy_factor = st.slider(
            "Minimum Happy Factor",
            min_value=0,
            max_value=100,
            value=70,
            step=5,
        )
        lookback_days = st.slider(
            "Lookback window (days)",
            min_value=1,
            max_value=30,
            value=7,
            step=1,
        )
        row_limit = st.slider(
            "Max rows",
            min_value=10,
            max_value=100,
            value=25,
            step=5,
        )

    config = FeedQueryConfig(
        table_fqn=table_fqn,
        min_happy_factor=min_happy_factor,
        lookback_days=lookback_days,
        row_limit=row_limit,
    )

    try:
        rows, sql = load_feed(project_id, config)
    except Exception as exc:  # pragma: no cover - UI fallback
        st.error(f"Query failed: {exc}")
        st.stop()

    summary = summarize_feed(rows)
    metric_one, metric_two, metric_three, metric_four = st.columns(4)
    metric_one.metric("Articles", summary["row_count"])
    metric_two.metric("Avg Happy Factor", summary["avg_happy_factor"])
    metric_three.metric("Max Happy Factor", summary["max_happy_factor"])
    metric_four.metric("Sources", summary["source_count"])

    st.subheader("Results")
    if not rows:
        st.info("No records matched the current filters.")
    else:
        for row in rows:
            title = str(row.get("title") or "Untitled article")
            url = row.get("url")
            source_name = row.get("source_name") or "Unknown source"
            published_at = _format_timestamp(row.get("published_at") or row.get("ingested_at"))
            happy_factor = row.get("happy_factor")
            tone_score = row.get("tone_score")

            if url:
                st.markdown(f"### [{title}]({url})")
            else:
                st.markdown(f"### {title}")

            st.caption(
                f"{published_at}  |  {source_name}  |  "
                f"happy_factor={happy_factor}  |  tone_score={tone_score}"
            )

    with st.expander("Query details"):
        st.code(sql, language="sql")
        st.write(
            {
                "project_id": project_id,
                "table_fqn": table_fqn,
                "min_happy_factor": min_happy_factor,
                "lookback_days": lookback_days,
                "row_limit": row_limit,
            }
        )


if __name__ == "__main__":
    main()
