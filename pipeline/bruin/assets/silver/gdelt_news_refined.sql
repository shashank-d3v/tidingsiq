/* @bruin
name: silver.gdelt_news_refined
type: bq.sql
connection: bigquery-default

depends:
  - bronze.gdelt_news_raw

materialization:
  type: table
  partition_by: date(ingested_at)
  cluster_by:
    - dedup_key
    - source_domain
    - language

custom_checks:
  - name: normalized_url_shape_when_present
    description: Normalized URLs should look like a hostname with an optional path.
    query: |
      select countif(
        normalized_url is not null
        and not regexp_contains(normalized_url, r'^[a-z0-9.-]+(?::[0-9]+)?(/.*)?$')
      )
      from silver.gdelt_news_refined
  - name: latest_silver_ingestion_is_recent
    description: Silver should reflect a recent ingestion window.
    query: |
      select if(
        max(ingested_at) >= timestamp_sub(current_timestamp(), interval 48 hour),
        0,
        1
      )
      from silver.gdelt_news_refined

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
  - name: language
    type: string
  - name: language_resolution_status
    type: string
    checks:
      - name: not_null
  - name: mentioned_country_code
    type: string
    checks:
      - name: not_null
  - name: mentioned_country_name
    type: string
    checks:
      - name: not_null
  - name: mentioned_country_resolution_status
    type: string
    checks:
      - name: not_null
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
    checks:
      - name: min
        value: -100
      - name: max
        value: 100
  - name: positive_signal_score
    type: float
  - name: negative_signal_score
    type: float
  - name: dedup_key
    type: string
    checks:
      - name: not_null
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
    coalesce(nullif(trim(source_domain), ''), 'unknown-source') as source_domain,
    coalesce(nullif(lower(trim(language)), ''), 'und') as language,
    coalesce(nullif(trim(language_resolution_status), ''), 'undetermined') as language_resolution_status,
    coalesce(nullif(upper(trim(mentioned_country_code)), ''), 'ZZ') as mentioned_country_code,
    coalesce(nullif(trim(mentioned_country_name), ''), 'Unknown') as mentioned_country_name,
    coalesce(nullif(trim(mentioned_country_resolution_status), ''), 'undetermined') as mentioned_country_resolution_status,
    nullif(trim(source_url), '') as source_url,
    nullif(regexp_replace(trim(title), r'\s+', ' '), '') as cleaned_title,
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
    source_domain,
    language,
    language_resolution_status,
    mentioned_country_code,
    mentioned_country_name,
    mentioned_country_resolution_status,
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
    tone_raw as tone_score,
    cast(null as float64) as positive_signal_score,
    cast(null as float64) as negative_signal_score
  from bronze_base
),

keyed as (
  select
    source_record_id,
    to_hex(sha256(source_record_id)) as article_id,
    ingestion_id,
    ingested_at,
    published_at,
    source_name,
    source_domain,
    language,
    language_resolution_status,
    mentioned_country_code,
    mentioned_country_name,
    mentioned_country_resolution_status,
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
  source_record_id,
  article_id,
  ingestion_id,
  ingested_at,
  published_at,
  source_name,
  source_domain,
  language,
  language_resolution_status,
  mentioned_country_code,
  mentioned_country_name,
  mentioned_country_resolution_status,
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
