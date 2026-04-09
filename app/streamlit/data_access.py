from __future__ import annotations

from google.cloud import bigquery
import streamlit as st

from query_builder import FeedQueryConfig, build_feed_query


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
def get_table_columns(project_id: str, table_fqn: str) -> set[str]:
    client = get_bigquery_client(project_id)
    parts = table_fqn.split(".")
    if len(parts) != 3:
        return set()

    project_name, dataset_name, table_name = parts
    sql = f"""
select
  column_name
from `{project_name}.{dataset_name}.INFORMATION_SCHEMA.COLUMNS`
where table_name = @table_name
"""
    rows = client.query(
        sql,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("table_name", "STRING", table_name)
            ]
        ),
    ).result()
    return {str(row["column_name"]) for row in rows}


@st.cache_data(ttl=300, show_spinner=False)
def load_feed(
    project_id: str,
    config: FeedQueryConfig,
) -> tuple[list[dict[str, object]], str]:
    client = get_bigquery_client(project_id)
    available_columns = get_table_columns(project_id, config.table_fqn)
    sql, parameter_specs = build_feed_query(
        config,
        available_columns=available_columns,
    )
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
    metrics_table = build_metrics_table_fqn(table_fqn)
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


def build_metrics_table_fqn(table_fqn: str) -> str | None:
    parts = table_fqn.split(".")
    if len(parts) != 3:
        return None
    return f"{parts[0]}.{parts[1]}.pipeline_run_metrics"
