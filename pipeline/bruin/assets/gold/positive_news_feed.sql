/* @bruin
name: gold.positive_news_feed
type: bq.sql
connection: bigquery-default

depends:
  - silver.gdelt_news_refined

materialization:
  type: table

columns:
  - name: article_id
    type: string
    checks:
      - name: unique
      - name: not_null
  - name: published_at
    type: timestamp
  - name: source_name
    type: string
  - name: source_country
    type: string
  - name: language
    type: string
  - name: title
    type: string
  - name: url
    type: string
  - name: tone_score
    type: float
  - name: positive_signal_score
    type: float
  - name: negative_signal_score
    type: float
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
    article_id,
    published_at,
    source_name,
    source_country,
    language,
    title,
    url,
    tone_score,
    positive_signal_score,
    negative_signal_score,
    ingested_at
  from silver.gdelt_news_refined
  where is_duplicate = false
),

scored as (
  select
    article_id,
    published_at,
    source_name,
    source_country,
    language,
    title,
    url,
    tone_score,
    positive_signal_score,
    negative_signal_score,
    round(
      100 * greatest(0.0, least(1.0, safe_divide(tone_score + 10.0, 20.0))),
      2
    ) as happy_factor,
    'v1_tone_only' as happy_factor_version,
    ingested_at
  from canonical_articles
)

select
  article_id,
  published_at,
  source_name,
  source_country,
  language,
  title,
  url,
  tone_score,
  positive_signal_score,
  negative_signal_score,
  happy_factor,
  happy_factor_version,
  ingested_at
from scored
where coalesce(published_at, ingested_at) >= timestamp_sub(current_timestamp(), interval 180 day)
