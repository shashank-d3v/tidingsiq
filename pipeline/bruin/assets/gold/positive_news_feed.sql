/* @bruin
name: gold.positive_news_feed
type: bq.sql
connection: bigquery-default

depends:
  - silver.gdelt_news_refined
  - gold.positive_feed_guardrail_terms

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
  - name: eligible_feed_has_no_hard_deny_rows
    description: Eligible feed rows must not carry hard deny hits.
    query: |
      select count(*)
      from gold.positive_news_feed
      where is_positive_feed_eligible = true
        and hard_deny_hit_count > 0
  - name: eligible_feed_has_no_unresolved_soft_deny_rows
    description: Eligible feed rows must not carry unresolved soft deny hits.
    query: |
      select count(*)
      from gold.positive_news_feed
      where is_positive_feed_eligible = true
        and soft_deny_hit_count > 0
        and allow_hit_count = 0

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
  - name: language
    type: string
    checks:
      - name: not_null
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
  - name: url
    type: string
  - name: tone_score
    type: float
    checks:
      - name: min
        value: -100
      - name: max
        value: 100
  - name: base_happy_factor
    type: float
    checks:
      - name: not_null
      - name: min
        value: 0
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
  - name: is_positive_feed_eligible
    type: boolean
    checks:
      - name: not_null
  - name: positive_guardrail_version
    type: string
    checks:
      - name: not_null
  - name: exclusion_reason
    type: string
  - name: allow_hit_count
    type: integer
    checks:
      - name: not_null
  - name: soft_deny_hit_count
    type: integer
    checks:
      - name: not_null
  - name: hard_deny_hit_count
    type: integer
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
    language,
    language_resolution_status,
    mentioned_country_code,
    mentioned_country_name,
    mentioned_country_resolution_status,
    title,
    url,
    tone_score,
    ingested_at
  from silver.gdelt_news_refined
  where is_duplicate = false
),

guardrail_terms as (
  select
    term,
    rule_class,
    match_scope
  from gold.positive_feed_guardrail_terms
  where is_active = true
),

normalized_articles as (
  select
    source_record_id,
    article_id,
    serving_date,
    published_at,
    source_name,
    language,
    language_resolution_status,
    mentioned_country_code,
    mentioned_country_name,
    mentioned_country_resolution_status,
    title,
    url,
    coalesce(tone_score, 0.0) as tone_score,
    regexp_replace(lower(coalesce(title, '')), r'[^a-z0-9]+', ' ') as normalized_title,
    regexp_extract_all(lower(coalesce(title, '')), r'[a-z0-9]+') as title_tokens,
    ingested_at
  from canonical_articles
),

rule_hits as (
  select
    article.source_record_id,
    countif(term.rule_class = 'allow' and term.match_scope = 'token') as allow_token_hit_count,
    countif(term.rule_class = 'allow' and term.match_scope = 'phrase') as allow_phrase_hit_count,
    countif(term.rule_class = 'allow') as allow_hit_count,
    countif(term.rule_class = 'deny_soft') as soft_deny_hit_count,
    countif(term.rule_class = 'deny_hard') as hard_deny_hit_count
  from normalized_articles as article
  left join guardrail_terms as term
    on (
      term.match_scope = 'token'
      and term.term in unnest(article.title_tokens)
    )
    or (
      term.match_scope = 'phrase'
      and instr(article.normalized_title, lower(term.term)) > 0
    )
  group by article.source_record_id
),

scored as (
  select
    article.source_record_id,
    article.article_id,
    article.serving_date,
    article.published_at,
    article.source_name,
    article.language,
    article.language_resolution_status,
    article.mentioned_country_code,
    article.mentioned_country_name,
    article.mentioned_country_resolution_status,
    article.title,
    article.url,
    article.tone_score,
    round(
      100 * greatest(0.0, least(1.0, safe_divide(article.tone_score + 10.0, 20.0))),
      2
    ) as base_happy_factor,
    coalesce(hits.allow_token_hit_count, 0) as allow_token_hit_count,
    coalesce(hits.allow_phrase_hit_count, 0) as allow_phrase_hit_count,
    coalesce(hits.allow_hit_count, 0) as allow_hit_count,
    coalesce(hits.soft_deny_hit_count, 0) as soft_deny_hit_count,
    coalesce(hits.hard_deny_hit_count, 0) as hard_deny_hit_count,
    article.ingested_at
  from normalized_articles as article
  left join rule_hits as hits
    on article.source_record_id = hits.source_record_id
),

finalized as (
  select
    source_record_id,
    article_id,
    serving_date,
    published_at,
    source_name,
    language,
    language_resolution_status,
    mentioned_country_code,
    mentioned_country_name,
    mentioned_country_resolution_status,
    title,
    url,
    tone_score,
    base_happy_factor,
    round(
      greatest(
        0.0,
        least(
          100.0,
          base_happy_factor
          + least(10.0, 2.0 * allow_token_hit_count + 5.0 * allow_phrase_hit_count)
          - if(soft_deny_hit_count > 0 and allow_hit_count = 0, 12.0, 0.0)
        )
      ),
      2
    ) as happy_factor,
    'v2_1_guardrailed_tone' as happy_factor_version,
    case
      when title is null or trim(title) = '' then false
      when url is null or trim(url) = '' then false
      when hard_deny_hit_count > 0 then false
      when soft_deny_hit_count > 0 and allow_hit_count = 0 then false
      when round(
        greatest(
          0.0,
          least(
            100.0,
            base_happy_factor
            + least(10.0, 2.0 * allow_token_hit_count + 5.0 * allow_phrase_hit_count)
            - if(soft_deny_hit_count > 0 and allow_hit_count = 0, 12.0, 0.0)
          )
        ),
        2
      ) < 65 then false
      else true
    end as is_positive_feed_eligible,
    'v1_1_title_rules' as positive_guardrail_version,
    case
      when title is null or trim(title) = '' then 'missing_title'
      when url is null or trim(url) = '' then 'missing_url'
      when hard_deny_hit_count > 0 then 'hard_deny_term'
      when soft_deny_hit_count > 0 and allow_hit_count = 0 then 'soft_deny_without_exception'
      when round(
        greatest(
          0.0,
          least(
            100.0,
            base_happy_factor
            + least(10.0, 2.0 * allow_token_hit_count + 5.0 * allow_phrase_hit_count)
            - if(soft_deny_hit_count > 0 and allow_hit_count = 0, 12.0, 0.0)
          )
        ),
        2
      ) < 65 then 'below_threshold'
      else null
    end as exclusion_reason,
    allow_hit_count,
    soft_deny_hit_count,
    hard_deny_hit_count,
    ingested_at
  from scored
)

select
  source_record_id,
  article_id,
  serving_date,
  published_at,
  source_name,
  language,
  language_resolution_status,
  mentioned_country_code,
  mentioned_country_name,
  mentioned_country_resolution_status,
  title,
  url,
  tone_score,
  base_happy_factor,
  happy_factor,
  happy_factor_version,
  is_positive_feed_eligible,
  positive_guardrail_version,
  exclusion_reason,
  allow_hit_count,
  soft_deny_hit_count,
  hard_deny_hit_count,
  ingested_at
from finalized
where serving_date >= date_sub(current_date(), interval 180 day)
