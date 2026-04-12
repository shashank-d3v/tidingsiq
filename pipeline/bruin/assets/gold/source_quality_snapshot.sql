/* @bruin
name: gold.source_quality_snapshot
type: bq.sql
connection: bigquery-default

depends:
  - silver.gdelt_news_refined
  - gold.positive_news_feed
  - gold.url_validation_results

materialization:
  type: table

custom_checks:
  - name: source_quality_adjustment_is_bounded
    description: Source quality adjustments should stay within the documented range.
    query: |
      select count(*)
      from gold.source_quality_snapshot
      where source_quality_adjustment < -8
         or source_quality_adjustment > 8

columns:
  - name: source_domain
    type: string
    checks:
      - name: not_null
      - name: unique
  - name: sample_row_count
    type: integer
    checks:
      - name: not_null
  - name: eligible_rate
    type: float
  - name: hard_exclusion_rate
    type: float
  - name: soft_exclusion_rate
    type: float
  - name: invalid_or_unavailable_url_rate
    type: float
  - name: duplicate_or_near_duplicate_rate
    type: float
  - name: source_quality_tier
    type: string
    checks:
      - name: not_null
  - name: source_quality_adjustment
    type: float
    checks:
      - name: not_null
  - name: snapshot_window_start
    type: date
    checks:
      - name: not_null
  - name: snapshot_window_end
    type: date
    checks:
      - name: not_null
  - name: computed_at
    type: timestamp
    checks:
      - name: not_null
@bruin */

with recent_window as (
  select
    date_sub(current_date(), interval 30 day) as snapshot_window_start,
    current_date() as snapshot_window_end
),

recent_gold as (
  select
    coalesce(s.source_domain, 'unknown-source') as source_domain,
    count(*) as sample_row_count,
    avg(if(g.is_positive_feed_eligible, 1.0, 0.0)) as eligible_rate,
    avg(if(g.exclusion_reason = 'hard_deny_term', 1.0, 0.0)) as hard_exclusion_rate,
    avg(
      if(g.exclusion_reason = 'soft_deny_without_exception', 1.0, 0.0)
    ) as soft_exclusion_rate
  from gold.positive_news_feed as g
  inner join silver.gdelt_news_refined as s
    on g.article_id = s.article_id
  cross join recent_window
  where g.serving_date >= recent_window.snapshot_window_start
    and s.is_duplicate = false
  group by 1
),

recent_url_quality as (
  select
    coalesce(s.source_domain, 'unknown-source') as source_domain,
    avg(
      if(
        coalesce(u.status, 'unchecked') in ('broken', 'unavailable', 'redirect_loop'),
        1.0,
        0.0
      )
    ) as invalid_or_unavailable_url_rate
  from silver.gdelt_news_refined as s
  left join gold.url_validation_results as u
    on s.normalized_url = u.normalized_url
  cross join recent_window
  where s.is_duplicate = false
    and date(coalesce(s.published_at, s.ingested_at)) >= recent_window.snapshot_window_start
  group by 1
),

recent_duplicates as (
  select
    coalesce(source_domain, 'unknown-source') as source_domain,
    avg(if(is_duplicate or is_near_duplicate_candidate, 1.0, 0.0)) as duplicate_or_near_duplicate_rate
  from silver.gdelt_news_refined
  cross join recent_window
  where date(coalesce(published_at, ingested_at)) >= recent_window.snapshot_window_start
  group by 1
),

combined as (
  select
    gold.source_domain,
    gold.sample_row_count,
    round(gold.eligible_rate, 4) as eligible_rate,
    round(gold.hard_exclusion_rate, 4) as hard_exclusion_rate,
    round(gold.soft_exclusion_rate, 4) as soft_exclusion_rate,
    round(coalesce(urls.invalid_or_unavailable_url_rate, 0.0), 4) as invalid_or_unavailable_url_rate,
    round(coalesce(dups.duplicate_or_near_duplicate_rate, 0.0), 4) as duplicate_or_near_duplicate_rate
  from recent_gold as gold
  left join recent_url_quality as urls
    on gold.source_domain = urls.source_domain
  left join recent_duplicates as dups
    on gold.source_domain = dups.source_domain
),

tiered as (
  select
    source_domain,
    sample_row_count,
    eligible_rate,
    hard_exclusion_rate,
    soft_exclusion_rate,
    invalid_or_unavailable_url_rate,
    duplicate_or_near_duplicate_rate,
    case
      when sample_row_count < 10 then 'mixed'
      when eligible_rate >= 0.60
        and invalid_or_unavailable_url_rate < 0.02
        and duplicate_or_near_duplicate_rate < 0.15 then 'strong'
      when eligible_rate >= 0.45
        and invalid_or_unavailable_url_rate < 0.05
        and duplicate_or_near_duplicate_rate < 0.25 then 'good'
      when invalid_or_unavailable_url_rate >= 0.15
        or eligible_rate < 0.20
        or duplicate_or_near_duplicate_rate >= 0.50 then 'poor'
      when invalid_or_unavailable_url_rate >= 0.08
        or eligible_rate < 0.35
        or duplicate_or_near_duplicate_rate >= 0.35 then 'weak'
      else 'mixed'
    end as source_quality_tier
  from combined
)

select
  tiered.source_domain,
  tiered.sample_row_count,
  tiered.eligible_rate,
  tiered.hard_exclusion_rate,
  tiered.soft_exclusion_rate,
  tiered.invalid_or_unavailable_url_rate,
  tiered.duplicate_or_near_duplicate_rate,
  tiered.source_quality_tier,
  case tiered.source_quality_tier
    when 'strong' then 8.0
    when 'good' then 4.0
    when 'weak' then -4.0
    when 'poor' then -8.0
    else 0.0
  end as source_quality_adjustment,
  recent_window.snapshot_window_start,
  recent_window.snapshot_window_end,
  current_timestamp() as computed_at
from tiered
cross join recent_window
