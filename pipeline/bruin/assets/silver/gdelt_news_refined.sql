/* @bruin
name: silver.gdelt_news_refined
type: bq.sql
connection: bigquery-default

depends:
  - bronze.gdelt_news_raw

materialization:
  type: table

columns:
  - name: article_id
    type: string
    checks:
      - name: unique
      - name: not_null
  - name: ingestion_id
    type: string
    checks:
      - name: not_null
  - name: ingested_at
    type: timestamp
    checks:
      - name: not_null
  - name: published_at
    type: timestamp
  - name: source_name
    type: string
  - name: source_domain
    type: string
  - name: source_country
    type: string
  - name: language
    type: string
  - name: title
    type: string
  - name: normalized_title
    type: string
  - name: url
    type: string
  - name: normalized_url
    type: string
  - name: tone_score
    type: float
  - name: positive_signal_score
    type: float
  - name: negative_signal_score
    type: float
  - name: dedup_key
    type: string
  - name: is_duplicate
    type: boolean
    checks:
      - name: not_null
  - name: is_near_duplicate_candidate
    type: boolean
    checks:
      - name: not_null
@bruin */

-- Placeholder scaffold only.
-- Phase 4 will replace this empty schema projection with normalization and dedup logic.
select
  cast(null as string) as article_id,
  cast(null as string) as ingestion_id,
  cast(null as timestamp) as ingested_at,
  cast(null as timestamp) as published_at,
  cast(null as string) as source_name,
  cast(null as string) as source_domain,
  cast(null as string) as source_country,
  cast(null as string) as language,
  cast(null as string) as title,
  cast(null as string) as normalized_title,
  cast(null as string) as url,
  cast(null as string) as normalized_url,
  cast(null as float64) as tone_score,
  cast(null as float64) as positive_signal_score,
  cast(null as float64) as negative_signal_score,
  cast(null as string) as dedup_key,
  cast(null as bool) as is_duplicate,
  cast(null as bool) as is_near_duplicate_candidate
from (select 1 as placeholder_row)
where 1 = 0
