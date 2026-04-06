/* @bruin
name: gold.positive_news_feed
type: bq.sql
connection: bigquery-default

depends:
  - silver.gdelt_news_refined

materialization:
  type: table
  partition_by: serving_date
  cluster_by:
    - source_name

custom_checks:
  - name: latest_gold_ingestion_is_recent
    description: Gold should reflect a recent ingestion window.
    query: |
      select if(
        count(*) = 0,
        0,
        if(
          max(ingested_at) >= timestamp_sub(current_timestamp(), interval 48 hour),
          0,
          1
        )
      )
      from gold.positive_news_feed

columns:
  - name: source_record_id
    type: string
    checks:
      - name: not_null
  - name: article_id
    type: string
    checks:
      - name: unique
      - name: not_null
  - name: serving_date
    type: date
    checks:
      - name: not_null
  - name: published_at
    type: timestamp
  - name: source_name
    type: string
  - name: title
    type: string
    checks:
      - name: not_null
  - name: url
    type: string
    checks:
      - name: not_null
  - name: tone_score
    type: float
    checks:
      - name: min
        value: -100
      - name: max
        value: 100
  - name: happy_factor
    type: float
    checks:
      - name: not_null
      - name: min
        value: 0
      - name: max
        value: 100
  - name: happy_factor_version
    type: string
    checks:
      - name: not_null
  - name: ingested_at
    type: timestamp
    checks:
      - name: not_null
@bruin */

with canonical_articles as (
  select
    source_record_id,
    article_id,
    date(coalesce(published_at, ingested_at)) as serving_date,
    published_at,
    source_name,
    title,
    url,
    tone_score,
    ingested_at
  from silver.gdelt_news_refined
  where is_duplicate = false
    and title is not null
    and url is not null
),

scored as (
  select
    source_record_id,
    article_id,
    serving_date,
    published_at,
    source_name,
    title,
    url,
    tone_score,
    round(
      100 * greatest(0.0, least(1.0, safe_divide(tone_score + 10.0, 20.0))),
      2
    ) as happy_factor,
    'v1_tone_only' as happy_factor_version,
    ingested_at
  from canonical_articles
)

select
  source_record_id,
  article_id,
  serving_date,
  published_at,
  source_name,
  title,
  url,
  tone_score,
  happy_factor,
  happy_factor_version,
  ingested_at
from scored
where serving_date >= date_sub(current_date(), interval 180 day)
