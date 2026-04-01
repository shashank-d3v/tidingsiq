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

-- Placeholder scaffold only.
-- Phase 5 will replace this empty schema projection with final scoring logic.
select
  cast(null as string) as article_id,
  cast(null as timestamp) as published_at,
  cast(null as string) as source_name,
  cast(null as string) as source_country,
  cast(null as string) as language,
  cast(null as string) as title,
  cast(null as string) as url,
  cast(null as float64) as tone_score,
  cast(null as float64) as positive_signal_score,
  cast(null as float64) as negative_signal_score,
  cast(null as float64) as happy_factor,
  cast(null as string) as happy_factor_version,
  cast(null as timestamp) as ingested_at
from (select 1 as placeholder_row)
where 1 = 0
