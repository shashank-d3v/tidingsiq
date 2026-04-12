from __future__ import annotations

import argparse
from contextlib import nullcontext
import csv
import sys
from pathlib import Path


DEFAULT_GOLD_TABLE = "gold.positive_news_feed"
DEFAULT_SILVER_TABLE = "silver.gdelt_news_refined"
DEFAULT_LOOKBACK_DAYS = 30
DEFAULT_BUCKET_SIZE = 50
BUCKETS = (
    "eligible_current",
    "below_threshold",
    "soft_deny_without_exception",
    "hard_deny_term",
    "missing_required",
    "borderline_60_75",
    "eligible_weak_domain",
)


def build_sampling_sql(
    gold_table_fqn: str,
    silver_table_fqn: str,
    *,
    lookback_days: int,
    bucket_size: int,
) -> str:
    return f"""
with recent_rows as (
  select
    g.article_id,
    g.source_record_id,
    g.title,
    g.url,
    g.happy_factor,
    g.is_positive_feed_eligible,
    g.exclusion_reason,
    g.serving_date,
    g.source_name,
    coalesce(s.source_domain, 'unknown-source') as source_domain
  from `{gold_table_fqn}` as g
  left join `{silver_table_fqn}` as s
    on g.article_id = s.article_id
  where g.serving_date >= date_sub(current_date(), interval {int(lookback_days)} day)
),
weak_domains as (
  select
    source_domain
  from recent_rows
  group by source_domain
  having count(*) >= 5
     and avg(if(is_positive_feed_eligible, 1.0, 0.0)) < 0.35
),
bucketed as (
  select
    *,
    case
      when is_positive_feed_eligible and source_domain in (select source_domain from weak_domains)
        then 'eligible_weak_domain'
      when title is null or trim(title) = '' or url is null or trim(url) = ''
        then 'missing_required'
      when exclusion_reason = 'hard_deny_term'
        then 'hard_deny_term'
      when exclusion_reason = 'soft_deny_without_exception'
        then 'soft_deny_without_exception'
      when exclusion_reason = 'below_threshold'
        then 'below_threshold'
      when happy_factor between 60 and 75
        then 'borderline_60_75'
      when is_positive_feed_eligible
        then 'eligible_current'
      else null
    end as benchmark_bucket
  from recent_rows
),
ranked as (
  select
    *,
    row_number() over (
      partition by benchmark_bucket
      order by rand()
    ) as bucket_rank
  from bucketed
  where benchmark_bucket is not null
)
select
  benchmark_bucket,
  article_id,
  source_record_id,
  source_name,
  source_domain,
  serving_date,
  happy_factor,
  is_positive_feed_eligible,
  exclusion_reason,
  title,
  url
from ranked
where bucket_rank <= {int(bucket_size)}
order by benchmark_bucket, bucket_rank
"""


def write_rows(rows: list[dict[str, object]], *, output_path: str | None) -> None:
    fieldnames = [
        "benchmark_bucket",
        "article_id",
        "source_record_id",
        "source_name",
        "source_domain",
        "serving_date",
        "happy_factor",
        "is_positive_feed_eligible",
        "exclusion_reason",
        "title",
        "url",
    ]
    if output_path:
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        handle = destination.open("w", newline="", encoding="utf-8")
        context_manager = handle
    else:
        handle = sys.stdout
        context_manager = nullcontext(handle)

    with context_manager as output_handle:
        writer = csv.DictWriter(output_handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a stratified benchmark sample for Gold scoring review."
    )
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--gold-table", default=DEFAULT_GOLD_TABLE)
    parser.add_argument("--silver-table", default=DEFAULT_SILVER_TABLE)
    parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--bucket-size", type=int, default=DEFAULT_BUCKET_SIZE)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    try:
        from google.cloud import bigquery
    except ImportError as exc:  # pragma: no cover - runtime guard
        raise RuntimeError(
            "google-cloud-bigquery is required to generate the scoring evaluation sample."
        ) from exc

    gold_table_fqn = qualify_table(args.project_id, args.gold_table)
    silver_table_fqn = qualify_table(args.project_id, args.silver_table)
    client = bigquery.Client(project=args.project_id)
    sql = build_sampling_sql(
        gold_table_fqn,
        silver_table_fqn,
        lookback_days=args.lookback_days,
        bucket_size=args.bucket_size,
    )
    rows = [dict(row.items()) for row in client.query(sql).result()]
    write_rows(rows, output_path=args.output)
    return 0


def qualify_table(project_id: str, table_name: str) -> str:
    normalized = table_name.strip().strip("`")
    if normalized.count(".") == 1:
        return f"{project_id}.{normalized}"
    if normalized.count(".") == 2:
        return normalized
    raise ValueError("table name must be dataset.table or project.dataset.table")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
