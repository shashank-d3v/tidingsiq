from __future__ import annotations

import argparse
import json


DEFAULT_CURRENT_TABLE = "gold.positive_news_feed"
DEFAULT_SHADOW_TABLE = "gold.positive_news_feed_v3_shadow"
DEFAULT_LABELS_TABLE = "gold.scoring_eval_labels"
DEFAULT_SILVER_TABLE = "silver.gdelt_news_refined"
SUMMARY_MARKER = "GOLD_SCORE_COMPARE_SUMMARY"


def build_overlap_summary_sql(current_table_fqn: str, shadow_table_fqn: str) -> str:
    return f"""
with current_rows as (
  select article_id, is_positive_feed_eligible
  from `{current_table_fqn}`
),
shadow_rows as (
  select article_id, is_positive_feed_eligible
  from `{shadow_table_fqn}`
)
select
  countif(current_rows.is_positive_feed_eligible) as current_eligible_count,
  countif(shadow_rows.is_positive_feed_eligible) as shadow_eligible_count,
  countif(
    current_rows.is_positive_feed_eligible
    and shadow_rows.is_positive_feed_eligible
  ) as eligible_overlap_count,
  countif(
    current_rows.is_positive_feed_eligible
    and not shadow_rows.is_positive_feed_eligible
  ) as newly_excluded_count,
  countif(
    not current_rows.is_positive_feed_eligible
    and shadow_rows.is_positive_feed_eligible
  ) as newly_included_count
from current_rows
inner join shadow_rows
  using (article_id)
"""


def build_exclusion_distribution_sql(table_fqn: str, *, limit: int = 10) -> str:
    return f"""
select
  coalesce(exclusion_reason, 'eligible') as bucket,
  count(*) as row_count
from `{table_fqn}`
group by 1
order by row_count desc, bucket
limit {int(limit)}
"""


def build_changed_rows_sql(
    current_table_fqn: str,
    shadow_table_fqn: str,
    silver_table_fqn: str,
    *,
    change_kind: str,
    limit: int = 20,
) -> str:
    if change_kind not in {"newly_included", "newly_excluded"}:
        raise ValueError("change_kind must be newly_included or newly_excluded")

    if change_kind == "newly_included":
        predicate = (
            "not current_rows.is_positive_feed_eligible and shadow_rows.is_positive_feed_eligible"
        )
    else:
        predicate = (
            "current_rows.is_positive_feed_eligible and not shadow_rows.is_positive_feed_eligible"
        )

    return f"""
with current_rows as (
  select article_id, title, happy_factor, is_positive_feed_eligible, exclusion_reason
  from `{current_table_fqn}`
),
shadow_rows as (
  select article_id, positivity_score, suitability_score, happy_factor, is_positive_feed_eligible, exclusion_reason
  from `{shadow_table_fqn}`
),
source_rows as (
  select article_id, source_domain
  from `{silver_table_fqn}`
  where is_duplicate = false
)
select
  shadow_rows.article_id,
  source_rows.source_domain,
  current_rows.title,
  current_rows.happy_factor as current_happy_factor,
  shadow_rows.happy_factor as shadow_happy_factor,
  shadow_rows.positivity_score,
  shadow_rows.suitability_score,
  current_rows.exclusion_reason as current_exclusion_reason,
  shadow_rows.exclusion_reason as shadow_exclusion_reason
from shadow_rows
inner join current_rows
  using (article_id)
left join source_rows
  using (article_id)
where {predicate}
order by shadow_rows.happy_factor desc, shadow_rows.article_id desc
limit {int(limit)}
"""


def build_domain_mix_sql(table_fqn: str, silver_table_fqn: str, *, limit: int = 10) -> str:
    return f"""
select
  coalesce(s.source_domain, 'unknown-source') as source_domain,
  count(*) as eligible_rows
from `{table_fqn}` as g
left join `{silver_table_fqn}` as s
  on g.article_id = s.article_id
where g.is_positive_feed_eligible = true
group by 1
order by eligible_rows desc, source_domain
limit {int(limit)}
"""


def build_broken_link_mix_sql(table_fqn: str, *, limit: int = 10) -> str:
    return f"""
select
  coalesce(url_quality_status, 'unknown') as url_quality_status,
  count(*) as eligible_rows
from `{table_fqn}`
where is_positive_feed_eligible = true
group by 1
order by eligible_rows desc, url_quality_status
limit {int(limit)}
"""


def build_label_precision_sql(
    table_fqn: str,
    labels_table_fqn: str,
) -> str:
    return f"""
with labeled as (
  select
    article_id,
    default_feed_label
  from `{labels_table_fqn}`
  where default_feed_label in ('include', 'exclude')
),
eligible_labeled as (
  select
    table_rows.article_id,
    labeled.default_feed_label
  from `{table_fqn}` as table_rows
  inner join labeled
    using (article_id)
  where table_rows.is_positive_feed_eligible = true
)
select
  count(*) as labeled_eligible_rows,
  countif(default_feed_label = 'include') as labeled_include_hits,
  round(
    safe_divide(countif(default_feed_label = 'include'), count(*)),
    4
  ) as include_precision
from eligible_labeled
"""


def build_summary_line(summary: dict[str, object]) -> str:
    parts = [SUMMARY_MARKER]
    for key in (
        "current_eligible_count",
        "shadow_eligible_count",
        "eligible_overlap_count",
        "newly_included_count",
        "newly_excluded_count",
        "current_include_precision",
        "shadow_include_precision",
    ):
        value = summary.get(key)
        parts.append(f"{key}={value if value is not None else 'none'}")
    return " ".join(parts)


def qualify_table(project_id: str, table_name: str) -> str:
    normalized = table_name.strip().strip("`")
    if normalized.count(".") == 1:
        return f"{project_id}.{normalized}"
    if normalized.count(".") == 2:
        return normalized
    raise ValueError("table name must be dataset.table or project.dataset.table")


def _query_rows(client, sql: str) -> list[dict[str, object]]:
    return [dict(row.items()) for row in client.query(sql).result()]


def _query_one(client, sql: str) -> dict[str, object]:
    rows = _query_rows(client, sql)
    return rows[0] if rows else {}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare the current Gold scoring table with the v3 shadow table."
    )
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--current-table", default=DEFAULT_CURRENT_TABLE)
    parser.add_argument("--shadow-table", default=DEFAULT_SHADOW_TABLE)
    parser.add_argument("--labels-table", default=DEFAULT_LABELS_TABLE)
    parser.add_argument("--silver-table", default=DEFAULT_SILVER_TABLE)
    args = parser.parse_args()

    try:
        from google.cloud import bigquery
    except ImportError as exc:  # pragma: no cover - runtime guard
        raise RuntimeError(
            "google-cloud-bigquery is required to compare Gold score versions."
        ) from exc

    current_table_fqn = qualify_table(args.project_id, args.current_table)
    shadow_table_fqn = qualify_table(args.project_id, args.shadow_table)
    labels_table_fqn = qualify_table(args.project_id, args.labels_table)
    silver_table_fqn = qualify_table(args.project_id, args.silver_table)

    client = bigquery.Client(project=args.project_id)
    summary = _query_one(client, build_overlap_summary_sql(current_table_fqn, shadow_table_fqn))
    summary["current_exclusion_distribution"] = _query_rows(
        client,
        build_exclusion_distribution_sql(current_table_fqn),
    )
    summary["shadow_exclusion_distribution"] = _query_rows(
        client,
        build_exclusion_distribution_sql(shadow_table_fqn),
    )
    summary["newly_included_rows"] = _query_rows(
        client,
        build_changed_rows_sql(
            current_table_fqn,
            shadow_table_fqn,
            silver_table_fqn,
            change_kind="newly_included",
        ),
    )
    summary["newly_excluded_rows"] = _query_rows(
        client,
        build_changed_rows_sql(
            current_table_fqn,
            shadow_table_fqn,
            silver_table_fqn,
            change_kind="newly_excluded",
        ),
    )
    summary["current_domain_mix"] = _query_rows(
        client,
        build_domain_mix_sql(current_table_fqn, silver_table_fqn),
    )
    summary["shadow_domain_mix"] = _query_rows(
        client,
        build_domain_mix_sql(shadow_table_fqn, silver_table_fqn),
    )
    summary["shadow_broken_link_mix"] = _query_rows(
        client,
        build_broken_link_mix_sql(shadow_table_fqn),
    )

    try:
        current_precision = _query_one(
            client,
            build_label_precision_sql(current_table_fqn, labels_table_fqn),
        )
        shadow_precision = _query_one(
            client,
            build_label_precision_sql(shadow_table_fqn, labels_table_fqn),
        )
    except Exception:
        current_precision = {}
        shadow_precision = {}

    summary["current_include_precision"] = current_precision.get("include_precision")
    summary["shadow_include_precision"] = shadow_precision.get("include_precision")
    summary["current_labeled_eligible_rows"] = current_precision.get("labeled_eligible_rows")
    summary["shadow_labeled_eligible_rows"] = shadow_precision.get("labeled_eligible_rows")

    print(json.dumps(summary, sort_keys=True, default=str))
    print(build_summary_line(summary))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
