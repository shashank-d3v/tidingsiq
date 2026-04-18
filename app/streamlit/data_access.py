from __future__ import annotations

from google.cloud import bigquery
import streamlit as st

from query_builder import (
    BriefGeographyOptionsQueryConfig,
    BriefLanguageOptionsQueryConfig,
    BriefRowsQueryConfig,
    BriefScopeQueryConfig,
    FeedQueryConfig,
    QueryParameterSpec,
    build_brief_geography_options_query,
    build_brief_language_options_query,
    build_brief_rows_query,
    build_brief_scope_summary_query,
    build_feed_query,
)


@st.cache_resource
def get_bigquery_client(project_id: str) -> bigquery.Client:
    return bigquery.Client(project=project_id)


def _to_query_parameters(
    parameters: list[tuple[str, str, object]] | list[QueryParameterSpec],
) -> list[bigquery.ArrayQueryParameter | bigquery.ScalarQueryParameter]:
    query_parameters: list[
        bigquery.ArrayQueryParameter | bigquery.ScalarQueryParameter
    ] = []
    for parameter in parameters:
        if isinstance(parameter, QueryParameterSpec):
            if parameter.is_array:
                query_parameters.append(
                    bigquery.ArrayQueryParameter(
                        parameter.name,
                        parameter.type_name,
                        list(parameter.value),
                    )
                )
            else:
                query_parameters.append(
                    bigquery.ScalarQueryParameter(
                        parameter.name,
                        parameter.type_name,
                        parameter.value,
                    )
                )
            continue

        name, type_name, value = parameter
        query_parameters.append(
            bigquery.ScalarQueryParameter(name, type_name, value)
        )
    return query_parameters


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


@st.cache_data(ttl=60, show_spinner=False)
def load_brief_rows(
    project_id: str,
    config: BriefRowsQueryConfig,
) -> tuple[list[dict[str, object]], str]:
    client = get_bigquery_client(project_id)
    available_columns = get_table_columns(project_id, config.table_fqn)
    sql, parameter_specs = build_brief_rows_query(
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


@st.cache_data(ttl=120, show_spinner=False)
def load_brief_scope_summary(
    project_id: str,
    config: BriefScopeQueryConfig,
) -> dict[str, float | int]:
    client = get_bigquery_client(project_id)
    available_columns = get_table_columns(project_id, config.table_fqn)
    sql, parameter_specs = build_brief_scope_summary_query(
        config,
        available_columns=available_columns,
    )
    rows = [dict(row.items()) for row in client.query(
        sql,
        job_config=bigquery.QueryJobConfig(
            query_parameters=_to_query_parameters(parameter_specs)
        ),
    ).result()]
    if not rows:
        return {
            "row_count": 0,
            "avg_happy_factor": 0.0,
            "max_happy_factor": 0.0,
            "source_count": 0,
        }

    summary_row = rows[0]
    return {
        "row_count": int(summary_row.get("row_count") or 0),
        "avg_happy_factor": float(summary_row.get("avg_happy_factor") or 0.0),
        "max_happy_factor": float(summary_row.get("max_happy_factor") or 0.0),
        "source_count": int(summary_row.get("source_count") or 0),
    }


@st.cache_data(ttl=120, show_spinner=False)
def load_brief_language_options(
    project_id: str,
    config: BriefLanguageOptionsQueryConfig,
) -> list[str]:
    client = get_bigquery_client(project_id)
    available_columns = get_table_columns(project_id, config.table_fqn)
    sql, parameter_specs = build_brief_language_options_query(
        config,
        available_columns=available_columns,
    )
    rows = client.query(
        sql,
        job_config=bigquery.QueryJobConfig(
            query_parameters=_to_query_parameters(parameter_specs)
        ),
    ).result()
    return [str(row["language"]) for row in rows if row.get("language")]


@st.cache_data(ttl=120, show_spinner=False)
def load_brief_geography_options(
    project_id: str,
    config: BriefGeographyOptionsQueryConfig,
) -> list[str]:
    client = get_bigquery_client(project_id)
    available_columns = get_table_columns(project_id, config.table_fqn)
    sql, parameter_specs = build_brief_geography_options_query(
        config,
        available_columns=available_columns,
    )
    rows = client.query(
        sql,
        job_config=bigquery.QueryJobConfig(
            query_parameters=_to_query_parameters(parameter_specs)
        ),
    ).result()
    return [str(row["geography"]) for row in rows if row.get("geography")]


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


@st.cache_data(ttl=300, show_spinner=False)
def load_pulse_dashboard(
    project_id: str,
    table_fqn: str,
) -> dict[str, object] | None:
    metrics_table = build_metrics_table_fqn(table_fqn)
    if metrics_table is None:
        return None

    client = get_bigquery_client(project_id)
    metrics_rows = _load_recent_metrics_rows(client, metrics_table)
    if not metrics_rows:
        return None
    latest_snapshot = _build_latest_snapshot(metrics_rows[0])
    gold_bundle = _load_gold_pulse_bundle(client, table_fqn)
    latest_snapshot["eligible_row_count"] = gold_bundle["eligible_row_count"]
    latest_snapshot["ineligible_row_count"] = gold_bundle["ineligible_row_count"]

    return {
        "latest_snapshot": latest_snapshot,
        "stage_snapshot": _build_stage_snapshot_rows(latest_snapshot),
        "exclusion_breakdown": gold_bundle["exclusion_breakdown"],
        "pipeline_trend": _build_pipeline_trend(metrics_rows),
        "silver_cleanup_trend": _build_silver_cleanup_trend(metrics_rows),
        "score_distribution": gold_bundle["score_distribution"],
    }


def build_metrics_table_fqn(table_fqn: str) -> str | None:
    parts = table_fqn.split(".")
    if len(parts) != 3:
        return None
    return f"{parts[0]}.{parts[1]}.pipeline_run_metrics"


def _load_recent_metrics_rows(
    client: bigquery.Client,
    metrics_table_fqn: str,
    *,
    limit: int = 12,
) -> list[dict[str, object]]:
    sql = f"""
select
  audit_run_at,
  bronze_row_count,
  silver_row_count,
  silver_canonical_row_count,
  silver_duplicate_row_count,
  gold_row_count,
  gold_avg_happy_factor,
  gold_max_happy_factor,
  latest_gold_ingested_at
from `{metrics_table_fqn}`
order by audit_run_at desc
limit {limit}
"""
    return [dict(row.items()) for row in client.query(sql).result()]


def _build_latest_snapshot(metrics_row: dict[str, object]) -> dict[str, object]:
    return {
        "audit_run_at": metrics_row.get("audit_run_at"),
        "bronze_row_count": int(metrics_row.get("bronze_row_count", 0)),
        "silver_row_count": int(metrics_row.get("silver_row_count", 0)),
        "silver_canonical_row_count": int(metrics_row.get("silver_canonical_row_count", 0)),
        "silver_duplicate_row_count": int(metrics_row.get("silver_duplicate_row_count", 0)),
        "gold_row_count": int(metrics_row.get("gold_row_count", 0)),
        "gold_avg_happy_factor": metrics_row.get("gold_avg_happy_factor"),
        "gold_max_happy_factor": metrics_row.get("gold_max_happy_factor"),
        "latest_gold_ingested_at": metrics_row.get("latest_gold_ingested_at"),
    }


def _build_stage_snapshot_rows(latest_snapshot: dict[str, object]) -> list[dict[str, object]]:
    return [
        {
            "stage": "Bronze Landed",
            "row_count": int(latest_snapshot.get("bronze_row_count", 0)),
        },
        {
            "stage": "Silver Normalized",
            "row_count": int(latest_snapshot.get("silver_row_count", 0)),
        },
        {
            "stage": "Silver Canonical",
            "row_count": int(latest_snapshot.get("silver_canonical_row_count", 0)),
        },
        {
            "stage": "Gold Scored",
            "row_count": int(latest_snapshot.get("gold_row_count", 0)),
        },
        {
            "stage": "Gold Eligible",
            "row_count": int(latest_snapshot.get("eligible_row_count", 0)),
        },
    ]


def _load_gold_pulse_bundle(
    client: bigquery.Client,
    table_fqn: str,
) -> dict[str, object]:
    sql = f"""
with base as (
  select
    is_positive_feed_eligible,
    exclusion_reason,
    case
      when happy_factor < 65 then 'Below 65'
      when happy_factor < 70 then '65-70'
      when happy_factor < 75 then '70-75'
      when happy_factor < 80 then '75-80'
      when happy_factor < 85 then '80-85'
      else '85+'
    end as score_bucket,
    case
      when happy_factor < 65 then 1
      when happy_factor < 70 then 2
      when happy_factor < 75 then 3
      when happy_factor < 80 then 4
      when happy_factor < 85 then 5
      else 6
    end as score_bucket_order
  from `{table_fqn}`
),
summary_rows as (
  select
    'summary' as section,
    'eligible_row_count' as bucket,
    countif(is_positive_feed_eligible) as row_count,
    0 as bucket_order
  from base
  union all
  select
    'summary' as section,
    'ineligible_row_count' as bucket,
    countif(not is_positive_feed_eligible) as row_count,
    0 as bucket_order
  from base
),
exclusion_rows as (
  select
    'exclusion' as section,
    exclusion_reason as bucket,
    count(*) as row_count,
    0 as bucket_order
  from base
  where is_positive_feed_eligible = false
  group by exclusion_reason
),
score_rows as (
  select
    'score' as section,
    score_bucket as bucket,
    count(*) as row_count,
    score_bucket_order as bucket_order
  from base
  group by score_bucket, score_bucket_order
)
select *
from summary_rows
union all
select *
from exclusion_rows
union all
select *
from score_rows
order by section, bucket_order, bucket
"""
    labels = {
        "below_threshold": "Below Threshold",
        "hard_deny_term": "Hard Deny Term",
        "soft_deny_without_exception": "Soft Deny Without Exception",
        "missing_title": "Missing Title",
        "missing_url": "Missing URL",
    }
    exclusion_counts = {key: 0 for key in labels}
    summary_counts = {
        "eligible_row_count": 0,
        "ineligible_row_count": 0,
    }
    score_distribution: list[dict[str, object]] = []

    for row in client.query(sql).result():
        section = str(row["section"])
        bucket = str(row["bucket"] or "")
        row_count = int(row["row_count"])
        if section == "summary" and bucket in summary_counts:
            summary_counts[bucket] = row_count
        elif section == "exclusion" and bucket in exclusion_counts:
            exclusion_counts[bucket] = row_count
        elif section == "score":
            score_distribution.append(
                {
                    "bucket": bucket,
                    "bucket_order": int(row["bucket_order"]),
                    "row_count": row_count,
                }
            )

    return {
        "eligible_row_count": summary_counts["eligible_row_count"],
        "ineligible_row_count": summary_counts["ineligible_row_count"],
        "exclusion_breakdown": [
            {"bucket": labels[key], "row_count": exclusion_counts[key]}
            for key in labels
            if exclusion_counts[key] > 0
        ],
        "score_distribution": score_distribution,
    }


def _build_pipeline_trend(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    chart_rows: list[dict[str, object]] = []
    for row in reversed(rows):
        audit_run_at = row.get("audit_run_at")
        run_label = audit_run_at.strftime("%b %-d") if audit_run_at is not None else "Unknown"
        chart_rows.append(
            {
                "run_label": run_label,
                "stage": "Bronze Landed",
                "row_count": int(row.get("bronze_row_count", 0)),
            }
        )
        chart_rows.append(
            {
                "run_label": run_label,
                "stage": "Silver Canonical",
                "row_count": int(row.get("silver_canonical_row_count", 0)),
            }
        )
        chart_rows.append(
            {
                "run_label": run_label,
                "stage": "Gold Scored",
                "row_count": int(row.get("gold_row_count", 0)),
            }
        )
    return chart_rows


def _build_silver_cleanup_trend(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    chart_rows: list[dict[str, object]] = []
    for row in reversed(rows):
        audit_run_at = row.get("audit_run_at")
        run_label = audit_run_at.strftime("%b %-d") if audit_run_at is not None else "Unknown"
        chart_rows.append(
            {
                "run_label": run_label,
                "bucket": "Silver Canonical",
                "row_count": int(row.get("silver_canonical_row_count", 0)),
            }
        )
        chart_rows.append(
            {
                "run_label": run_label,
                "bucket": "Silver Duplicates",
                "row_count": int(row.get("silver_duplicate_row_count", 0)),
            }
        )
    return chart_rows
