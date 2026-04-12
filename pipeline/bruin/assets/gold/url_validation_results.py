"""@bruin
name: gold.url_validation_results
type: python
connection: bigquery-default

materialization:
  type: table
  strategy: merge

columns:
  - name: normalized_url
    type: string
    primary_key: true
    checks:
      - name: not_null
      - name: unique
  - name: checked_at
    type: timestamp
    checks:
      - name: not_null
  - name: final_url
    type: string
  - name: http_status_code
    type: integer
  - name: redirect_count
    type: integer
    checks:
      - name: not_null
  - name: status
    type: string
    checks:
      - name: not_null
@bruin"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any

import pandas as pd

from pipeline.bruin.url_validation_v3 import (
    is_recheck_due,
    is_syntactically_valid_url,
    validate_url,
)


DEFAULT_SILVER_TABLE = "silver.gdelt_news_refined"
DEFAULT_URL_RESULTS_TABLE = "gold.url_validation_results"
DEFAULT_LOOKBACK_DAYS = 30
DEFAULT_MAX_URLS_PER_RUN = 100
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_REDIRECTS = 5


def materialize(**kwargs: Any) -> pd.DataFrame:
    imported_bigquery = _import_bigquery()
    project_id = _resolve_project_id()
    silver_table_fqn = _table_fqn(project_id, os.getenv("TIDINGSIQ_SILVER_TABLE", DEFAULT_SILVER_TABLE))
    results_table_fqn = _table_fqn(
        project_id,
        os.getenv("TIDINGSIQ_URL_VALIDATION_TABLE", DEFAULT_URL_RESULTS_TABLE),
    )
    client = imported_bigquery.Client(project=project_id)
    lookback_days = int(os.getenv("URL_VALIDATION_LOOKBACK_DAYS", str(DEFAULT_LOOKBACK_DAYS)))
    max_urls_per_run = int(os.getenv("URL_VALIDATION_MAX_URLS", str(DEFAULT_MAX_URLS_PER_RUN)))
    timeout_seconds = float(os.getenv("URL_VALIDATION_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
    max_redirects = int(os.getenv("URL_VALIDATION_MAX_REDIRECTS", str(DEFAULT_MAX_REDIRECTS)))

    candidates = _fetch_recent_candidates(
        client,
        imported_bigquery,
        silver_table_fqn=silver_table_fqn,
        lookback_days=lookback_days,
    )
    existing_results = _fetch_existing_results(client, results_table_fqn)

    now_utc = datetime.now(timezone.utc)
    due_candidates = [
        candidate
        for candidate in candidates
        if is_syntactically_valid_url(candidate["source_url"])
        and is_recheck_due(
            status=existing_results.get(candidate["normalized_url"], {}).get("status"),
            checked_at=existing_results.get(candidate["normalized_url"], {}).get("checked_at"),
            now=now_utc,
        )
    ][: max(0, max_urls_per_run)]

    if not due_candidates:
        return _empty_dataframe()

    rows: list[dict[str, object]] = []
    for candidate in due_candidates:
        outcome = validate_url(
            str(candidate["source_url"]),
            timeout_seconds=timeout_seconds,
            max_redirects=max_redirects,
        )
        rows.append(
            {
                "normalized_url": candidate["normalized_url"],
                "checked_at": now_utc,
                "final_url": outcome.final_url,
                "http_status_code": outcome.http_status_code,
                "redirect_count": outcome.redirect_count,
                "status": outcome.status,
            }
        )

    return pd.DataFrame.from_records(rows)


def _import_bigquery():
    try:
        from google.cloud import bigquery as imported_bigquery
    except ImportError as exc:  # pragma: no cover - runtime guard
        raise RuntimeError(
            "google-cloud-bigquery is required to materialize gold.url_validation_results."
        ) from exc
    return imported_bigquery


def _resolve_project_id() -> str:
    project_id = (
        os.getenv("BRUIN_PROJECT_ID")
        or os.getenv("TIDINGSIQ_GCP_PROJECT")
        or os.getenv("GOOGLE_CLOUD_PROJECT")
    )
    if not project_id:
        raise RuntimeError("BRUIN_PROJECT_ID or GOOGLE_CLOUD_PROJECT must be set.")
    return project_id


def _table_fqn(project_id: str, table_name: str) -> str:
    normalized = table_name.strip().strip("`")
    if normalized.count(".") == 1:
        return f"{project_id}.{normalized}"
    if normalized.count(".") == 2:
        return normalized
    raise ValueError("table name must be dataset.table or project.dataset.table")


def _fetch_recent_candidates(
    client,
    bigquery_module,
    *,
    silver_table_fqn: str,
    lookback_days: int,
) -> list[dict[str, str]]:
    sql = f"""
with recent_candidates as (
  select
    normalized_url,
    url as source_url,
    coalesce(published_at, ingested_at) as freshness_ts,
    row_number() over (
      partition by normalized_url
      order by coalesce(published_at, ingested_at) desc, article_id desc
    ) as freshness_rank
  from `{silver_table_fqn}`
  where is_duplicate = false
    and normalized_url is not null
    and trim(normalized_url) != ''
    and url is not null
    and trim(url) != ''
    and date(coalesce(published_at, ingested_at)) >= date_sub(current_date(), interval @lookback_days day)
)
select
  normalized_url,
  source_url
from recent_candidates
where freshness_rank = 1
order by freshness_ts desc, normalized_url
"""
    rows = client.query(
        sql,
        job_config=bigquery_module.QueryJobConfig(
            query_parameters=[
                bigquery_module.ScalarQueryParameter(
                    "lookback_days",
                    "INT64",
                    lookback_days,
                )
            ]
        ),
    ).result()
    return [
        {
            "normalized_url": str(row["normalized_url"]),
            "source_url": str(row["source_url"]),
        }
        for row in rows
    ]


def _fetch_existing_results(client, results_table_fqn: str) -> dict[str, dict[str, object]]:
    sql = f"""
select
  normalized_url,
  checked_at,
  status
from `{results_table_fqn}`
"""
    try:
        rows = client.query(sql).result()
    except Exception:
        return {}
    return {
        str(row["normalized_url"]): {
            "checked_at": row["checked_at"],
            "status": row["status"],
        }
        for row in rows
    }


def _empty_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "normalized_url",
            "checked_at",
            "final_url",
            "http_status_code",
            "redirect_count",
            "status",
        ]
    )
