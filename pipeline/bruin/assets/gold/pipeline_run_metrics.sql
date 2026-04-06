/* @bruin
name: gold.pipeline_run_metrics
type: bq.sql
connection: bigquery-default

depends:
  - bronze.gdelt_news_raw
  - silver.gdelt_news_refined
  - gold.positive_news_feed

materialization:
  type: table
  strategy: append
  partition_by: date(audit_run_at)

custom_checks:
  - name: gold_row_count_has_no_severe_recent_drop
    description: The latest Gold row count should not drop sharply versus recent history.
    query: |
      with ordered as (
        select
          gold_row_count,
          row_number() over (order by audit_run_at desc) as run_rank
        from gold.pipeline_run_metrics
      ),
      latest as (
        select gold_row_count
        from ordered
        where run_rank = 1
      ),
      history as (
        select avg(gold_row_count) as avg_gold_row_count
        from ordered
        where run_rank between 2 and 8
      )
      select if(
        (select avg_gold_row_count from history) is null,
        0,
        if(
          (select gold_row_count from latest) >= 0.7 * (select avg_gold_row_count from history),
          0,
          1
        )
      )
  - name: silver_duplicate_ratio_is_stable
    description: Duplicate-rate swings should stay within a reasonable recent band.
    query: |
      with ordered as (
        select
          safe_divide(silver_duplicate_row_count, silver_row_count) as duplicate_ratio,
          row_number() over (order by audit_run_at desc) as run_rank
        from gold.pipeline_run_metrics
      ),
      latest as (
        select duplicate_ratio
        from ordered
        where run_rank = 1
      ),
      history as (
        select avg(duplicate_ratio) as avg_duplicate_ratio
        from ordered
        where run_rank between 2 and 8
      )
      select if(
        (select avg_duplicate_ratio from history) is null,
        0,
        if(
          abs((select duplicate_ratio from latest) - (select avg_duplicate_ratio from history)) <= 0.1,
          0,
          1
        )
      )
  - name: latest_gold_timestamp_in_metrics_is_recent
    description: The latest metrics snapshot should reflect fresh Gold data.
    query: |
      with ordered as (
        select
          gold_row_count,
          latest_gold_ingested_at,
          row_number() over (order by audit_run_at desc) as run_rank
        from gold.pipeline_run_metrics
      )
      select if(
        max(if(run_rank = 1, gold_row_count, null)) = 0,
        0,
        if(
          max(if(run_rank = 1, latest_gold_ingested_at, null)) >= timestamp_sub(current_timestamp(), interval 48 hour),
          0,
          1
        )
      )
      from ordered

columns:
  - name: audit_run_at
    type: timestamp
    checks:
      - name: not_null
  - name: bronze_row_count
    type: integer
    checks:
      - name: not_null
  - name: silver_row_count
    type: integer
    checks:
      - name: not_null
  - name: silver_canonical_row_count
    type: integer
    checks:
      - name: not_null
  - name: silver_duplicate_row_count
    type: integer
    checks:
      - name: not_null
  - name: gold_row_count
    type: integer
    checks:
      - name: not_null
  - name: gold_min_happy_factor
    type: float
  - name: gold_avg_happy_factor
    type: float
  - name: gold_max_happy_factor
    type: float
  - name: latest_gold_ingested_at
    type: timestamp
  - name: latest_gold_published_at
    type: timestamp
@bruin */

with bronze_metrics as (
  select
    count(*) as bronze_row_count
  from bronze.gdelt_news_raw
),

silver_metrics as (
  select
    count(*) as silver_row_count,
    countif(is_duplicate = false) as silver_canonical_row_count,
    countif(is_duplicate = true) as silver_duplicate_row_count
  from silver.gdelt_news_refined
),

gold_metrics as (
  select
    count(*) as gold_row_count,
    min(happy_factor) as gold_min_happy_factor,
    round(avg(happy_factor), 2) as gold_avg_happy_factor,
    max(happy_factor) as gold_max_happy_factor,
    max(ingested_at) as latest_gold_ingested_at,
    max(published_at) as latest_gold_published_at
  from gold.positive_news_feed
)

select
  current_timestamp() as audit_run_at,
  bronze_metrics.bronze_row_count,
  silver_metrics.silver_row_count,
  silver_metrics.silver_canonical_row_count,
  silver_metrics.silver_duplicate_row_count,
  gold_metrics.gold_row_count,
  gold_metrics.gold_min_happy_factor,
  gold_metrics.gold_avg_happy_factor,
  gold_metrics.gold_max_happy_factor,
  gold_metrics.latest_gold_ingested_at,
  gold_metrics.latest_gold_published_at
from bronze_metrics
cross join silver_metrics
cross join gold_metrics
