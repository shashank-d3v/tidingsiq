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

with bronze_base as (
  select
    source_record_id,
    ingestion_id,
    ingested_at,
    published_at,
    nullif(trim(source_name), '') as source_name,
    nullif(trim(source_url), '') as source_url,
    nullif(regexp_replace(trim(title), r'\s+', ' '), '') as cleaned_title,
    nullif(lower(trim(language)), '') as cleaned_language,
    tone_raw
  from bronze.gdelt_news_raw
),

normalized as (
  select
    source_record_id,
    ingestion_id,
    ingested_at,
    published_at,
    source_name,
    cleaned_title as title,
    lower(cleaned_title) as normalized_title,
    source_url as url,
    case
      when source_url is null then null
      else nullif(
        regexp_replace(
          regexp_replace(
            regexp_replace(lower(source_url), r'^https?://', ''),
            r'[?#].*$',
            ''
          ),
          r'/$', ''
        ),
        ''
      )
    end as normalized_url,
    case
      when source_url is not null then
        nullif(regexp_replace(lower(net.host(source_url)), r'^www\.', ''), '')
      when source_name is not null then
        nullif(regexp_replace(lower(source_name), r'^www\.', ''), '')
      else null
    end as source_domain,
    cast(null as string) as source_country,
    cleaned_language as language,
    tone_raw as tone_score,
    cast(null as float64) as positive_signal_score,
    cast(null as float64) as negative_signal_score
  from bronze_base
),

keyed as (
  select
    to_hex(sha256(source_record_id)) as article_id,
    ingestion_id,
    ingested_at,
    published_at,
    source_name,
    source_domain,
    source_country,
    language,
    title,
    normalized_title,
    url,
    normalized_url,
    tone_score,
    positive_signal_score,
    negative_signal_score,
    case
      when normalized_url is not null then concat('url:', normalized_url)
      else concat(
        'title:',
        coalesce(normalized_title, ''),
        '|source:',
        coalesce(source_domain, source_name, ''),
        '|bucket:',
        format_timestamp(
          '%Y%m%d%H',
          coalesce(published_at, ingested_at)
        )
      )
    end as dedup_key,
    date(coalesce(published_at, ingested_at)) as dedup_date
  from normalized
),

scored as (
  select
    *,
    row_number() over (
      partition by dedup_key
      order by published_at desc nulls last, ingested_at desc, article_id desc
    ) as dedup_rank,
    count(*) over (
      partition by normalized_title, dedup_date
    ) as normalized_title_day_count
  from keyed
)

select
  article_id,
  ingestion_id,
  ingested_at,
  published_at,
  source_name,
  source_domain,
  source_country,
  language,
  title,
  normalized_title,
  url,
  normalized_url,
  tone_score,
  positive_signal_score,
  negative_signal_score,
  dedup_key,
  dedup_rank > 1 as is_duplicate,
  normalized_title is not null and normalized_title_day_count > 1 as is_near_duplicate_candidate
from scored
where coalesce(published_at, ingested_at) >= timestamp_sub(current_timestamp(), interval 90 day)
