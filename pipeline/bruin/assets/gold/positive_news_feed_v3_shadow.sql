/* @bruin
name: gold.positive_news_feed_v3_shadow
type: bq.sql
connection: bigquery-default

depends:
  - silver.gdelt_news_refined
  - gold.positive_feed_guardrail_terms
  - gold.url_validation_results
  - gold.source_quality_snapshot

materialization:
  type: table
  partition_by: serving_date
  cluster_by:
    - source_name
    - source_domain

custom_checks:
  - name: positivity_score_is_bounded
    description: Positivity scores should stay on the documented 0 to 100 scale.
    query: |
      select count(*)
      from gold.positive_news_feed_v3_shadow
      where positivity_score < 0 or positivity_score > 100
  - name: suitability_score_is_bounded
    description: Suitability scores should stay on the documented 0 to 100 scale.
    query: |
      select count(*)
      from gold.positive_news_feed_v3_shadow
      where suitability_score < 0 or suitability_score > 100
  - name: eligible_feed_has_no_hard_deny_rows
    description: Eligible shadow-feed rows must not carry hard deny hits.
    query: |
      select count(*)
      from gold.positive_news_feed_v3_shadow
      where is_positive_feed_eligible = true
        and hard_deny_hit_count > 0
  - name: eligible_feed_has_no_invalid_url_rows
    description: Eligible shadow-feed rows must have valid link status.
    query: |
      select count(*)
      from gold.positive_news_feed_v3_shadow
      where is_positive_feed_eligible = true
        and exclusion_reason in ('missing_url', 'malformed_url', 'url_broken', 'url_redirect_loop', 'url_unavailable')

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
  - name: source_domain
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
  - name: normalized_url
    type: string
  - name: tone_score
    type: float
  - name: base_happy_factor
    type: float
    checks:
      - name: not_null
      - name: min
        value: 0
      - name: max
        value: 100
  - name: positivity_score
    type: float
    checks:
      - name: not_null
      - name: min
        value: 0
      - name: max
        value: 100
  - name: suitability_score
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
  - name: suitability_gate_reason
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
  - name: url_quality_status
    type: string
    checks:
      - name: not_null
  - name: url_quality_checked_at
    type: timestamp
  - name: url_http_status
    type: integer
  - name: url_quality_penalty
    type: float
    checks:
      - name: not_null
  - name: headline_shape_penalty
    type: float
    checks:
      - name: not_null
  - name: source_quality_adjustment
    type: float
    checks:
      - name: not_null
  - name: score_explanation
    type: json
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
    source_domain,
    language,
    language_resolution_status,
    mentioned_country_code,
    mentioned_country_name,
    mentioned_country_resolution_status,
    title,
    url,
    normalized_url,
    tone_score,
    positive_signal_score,
    negative_signal_score,
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
    coalesce(source_domain, 'unknown-source') as source_domain,
    language,
    language_resolution_status,
    mentioned_country_code,
    mentioned_country_name,
    mentioned_country_resolution_status,
    title,
    url,
    normalized_url,
    coalesce(tone_score, 0.0) as tone_score,
    positive_signal_score,
    negative_signal_score,
    regexp_replace(lower(coalesce(title, '')), r'[^a-z0-9]+', ' ') as normalized_title,
    regexp_extract_all(lower(coalesce(title, '')), r'[a-z0-9]+') as title_tokens,
    array_length(regexp_extract_all(coalesce(title, ''), r'[A-Za-z0-9]+')) as title_token_count,
    array_length(regexp_extract_all(coalesce(title, ''), r'\b[A-Z]{2,}\b')) as uppercase_token_count,
    (
      select string_agg(token, ' ' order by offset)
      from unnest(regexp_extract_all(lower(coalesce(title, '')), r'[a-z0-9]+')) as token with offset
      where offset < 5
    ) as title_template_prefix,
    ingested_at
  from canonical_articles
),

recent_template_counts as (
  select
    source_domain,
    title_template_prefix,
    count(*) as template_repeat_count
  from normalized_articles
  where serving_date >= date_sub(current_date(), interval 7 day)
    and title_template_prefix is not null
    and title_template_prefix != ''
  group by 1, 2
),

rule_hits as (
  select
    article.source_record_id,
    countif(term.rule_class = 'allow' and term.match_scope = 'token') as allow_token_hit_count,
    countif(term.rule_class = 'allow' and term.match_scope = 'phrase') as allow_phrase_hit_count,
    countif(term.rule_class = 'allow') as allow_hit_count,
    countif(term.rule_class = 'deny_soft') as soft_deny_hit_count,
    countif(term.rule_class = 'deny_hard') as hard_deny_hit_count,
    array_agg(
      distinct if(term.rule_class = 'allow', term.term, null) ignore nulls
    ) as allow_terms,
    array_agg(
      distinct if(term.rule_class = 'deny_soft', term.term, null) ignore nulls
    ) as soft_deny_terms,
    array_agg(
      distinct if(term.rule_class = 'deny_hard', term.term, null) ignore nulls
    ) as hard_deny_terms
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

headline_features as (
  select
    article.*,
    coalesce(hits.allow_token_hit_count, 0) as allow_token_hit_count,
    coalesce(hits.allow_phrase_hit_count, 0) as allow_phrase_hit_count,
    coalesce(hits.allow_hit_count, 0) as allow_hit_count,
    coalesce(hits.soft_deny_hit_count, 0) as soft_deny_hit_count,
    coalesce(hits.hard_deny_hit_count, 0) as hard_deny_hit_count,
    coalesce(hits.allow_terms, cast([] as array<string>)) as allow_terms,
    coalesce(hits.soft_deny_terms, cast([] as array<string>)) as soft_deny_terms,
    coalesce(hits.hard_deny_terms, cast([] as array<string>)) as hard_deny_terms,
    coalesce(templates.template_repeat_count, 0) as template_repeat_count,
    regexp_contains(coalesce(article.title, ''), r'([!?]{2,}|\.{3,})') as has_punctuation_bait,
    regexp_contains(
      article.normalized_title,
      r'\b(photo gallery|gallery|slideshow|photos|watch|live updates?|live blog)\b'
    ) as has_gallery_bait,
    round(
      safe_divide(article.uppercase_token_count, nullif(article.title_token_count, 0)),
      4
    ) as uppercase_ratio
  from normalized_articles as article
  left join rule_hits as hits
    on article.source_record_id = hits.source_record_id
  left join recent_template_counts as templates
    on article.source_domain = templates.source_domain
    and article.title_template_prefix = templates.title_template_prefix
),

url_enriched as (
  select
    headline_features.*,
    case
      when headline_features.title is null or trim(headline_features.title) = '' then false
      else true
    end as has_title,
    case
      when headline_features.url is null or trim(headline_features.url) = '' then false
      else true
    end as has_url,
    case
      when headline_features.normalized_url is null or trim(headline_features.normalized_url) = '' then false
      when regexp_contains(
        headline_features.normalized_url,
        r'^[a-z0-9.-]+(?::[0-9]+)?(/.*)?$'
      ) then true
      else false
    end as has_valid_url,
    coalesce(url_results.status, 'unchecked') as url_quality_status,
    url_results.checked_at as url_quality_checked_at,
    url_results.http_status_code as url_http_status
  from headline_features
  left join gold.url_validation_results as url_results
    on headline_features.normalized_url = url_results.normalized_url
),

source_enriched as (
  select
    url_enriched.*,
    coalesce(source_quality.source_quality_tier, 'mixed') as source_quality_tier,
    coalesce(source_quality.source_quality_adjustment, 0.0) as source_quality_adjustment
  from url_enriched
  left join gold.source_quality_snapshot as source_quality
    on url_enriched.source_domain = source_quality.source_domain
),

positivity_scored as (
  select
    *,
    round(
      100 * greatest(0.0, least(1.0, safe_divide(tone_score + 10.0, 20.0))),
      2
    ) as base_happy_factor,
    cast(0.0 as float64) as upstream_signal_adjustment
  from source_enriched
),

suitability_inputs as (
  select
    *,
    least(10.0, 2.0 * allow_token_hit_count + 5.0 * allow_phrase_hit_count) as constructive_bonus,
    least(
      20.0,
      if(has_punctuation_bait, 6.0, 0.0)
      + if(title_token_count >= 5 and uppercase_ratio >= 0.4, 6.0, 0.0)
      + if(has_gallery_bait, 8.0, 0.0)
      + if(template_repeat_count >= 5, 6.0, 0.0)
    ) as headline_shape_penalty,
    case coalesce(url_quality_status, 'unchecked')
      when 'broken' then 40.0
      when 'redirect_loop' then 30.0
      when 'unavailable' then 20.0
      when 'timeout' then 15.0
      when 'forbidden' then 10.0
      when 'unchecked' then 5.0
      else 0.0
    end as url_quality_penalty
  from positivity_scored
),

dual_scored as (
  select
    *,
    round(
      greatest(
        0.0,
        least(
          100.0,
          base_happy_factor + constructive_bonus + upstream_signal_adjustment
        )
      ),
      2
    ) as positivity_score,
    round(
      greatest(
        0.0,
        least(
          100.0,
          100.0
          - headline_shape_penalty
          - url_quality_penalty
          - if(has_title, 0.0, 100.0)
          - if(has_valid_url, 0.0, 100.0)
          - if(hard_deny_hit_count > 0, 100.0, 0.0)
          - if(soft_deny_hit_count > 0 and allow_hit_count = 0, 25.0, 0.0)
          + greatest(-8.0, least(8.0, source_quality_adjustment))
        )
      ),
      2
    ) as suitability_score
  from suitability_inputs
),

finalized as (
  select
    source_record_id,
    article_id,
    serving_date,
    published_at,
    source_name,
    source_domain,
    language,
    language_resolution_status,
    mentioned_country_code,
    mentioned_country_name,
    mentioned_country_resolution_status,
    title,
    url,
    normalized_url,
    tone_score,
    base_happy_factor,
    positivity_score,
    suitability_score,
    round(
      greatest(
        0.0,
        least(100.0, 0.7 * positivity_score + 0.3 * suitability_score)
      ),
      2
    ) as happy_factor,
    'v3_dual_score_shadow' as happy_factor_version,
    'v1_1_title_rules' as positive_guardrail_version,
    case
      when not has_title then 'missing_title'
      when not has_url then 'missing_url'
      when not has_valid_url then 'malformed_url'
      when hard_deny_hit_count > 0 then 'hard_deny_term'
      when soft_deny_hit_count > 0 and allow_hit_count = 0 then 'soft_deny_without_exception'
      when url_quality_status = 'broken' then 'url_broken'
      when url_quality_status = 'redirect_loop' then 'url_redirect_loop'
      when url_quality_status = 'unavailable' then 'url_unavailable'
      when positivity_score < 65 then 'below_positivity_threshold'
      when suitability_score < 60 then 'low_suitability'
      else null
    end as exclusion_reason,
    case
      when not has_title then 'missing_title'
      when not has_url then 'missing_url'
      when not has_valid_url then 'malformed_url'
      when hard_deny_hit_count > 0 then 'hard_deny_term'
      when soft_deny_hit_count > 0 and allow_hit_count = 0 then 'soft_deny_without_exception'
      when url_quality_status = 'broken' then 'url_broken'
      when url_quality_status = 'redirect_loop' then 'url_redirect_loop'
      when url_quality_status = 'unavailable' then 'url_unavailable'
      when suitability_score < 60 then 'low_suitability'
      else null
    end as suitability_gate_reason,
    case
      when not has_title then false
      when not has_valid_url then false
      when hard_deny_hit_count > 0 then false
      when soft_deny_hit_count > 0 and allow_hit_count = 0 then false
      when url_quality_status in ('broken', 'redirect_loop', 'unavailable') then false
      when positivity_score < 65 then false
      when suitability_score < 60 then false
      else true
    end as is_positive_feed_eligible,
    allow_hit_count,
    soft_deny_hit_count,
    hard_deny_hit_count,
    url_quality_status,
    url_quality_checked_at,
    url_http_status,
    url_quality_penalty,
    headline_shape_penalty,
    greatest(-8.0, least(8.0, source_quality_adjustment)) as source_quality_adjustment,
    to_json(
      struct(
        base_happy_factor as base_happy_factor,
        constructive_bonus as constructive_bonus,
        upstream_signal_adjustment as upstream_signal_adjustment,
        positivity_score as positivity_score,
        suitability_score as suitability_score,
        headline_shape_penalty as headline_shape_penalty,
        url_quality_status as url_quality_status,
        url_quality_penalty as url_quality_penalty,
        source_quality_tier as source_quality_tier,
        greatest(-8.0, least(8.0, source_quality_adjustment)) as source_quality_adjustment,
        has_punctuation_bait as has_punctuation_bait,
        has_gallery_bait as has_gallery_bait,
        uppercase_ratio as uppercase_ratio,
        template_repeat_count as template_repeat_count,
        allow_terms as allow_terms,
        soft_deny_terms as soft_deny_terms,
        hard_deny_terms as hard_deny_terms,
        url_http_status as url_http_status,
        case
          when not has_title then 'missing_title'
          when not has_url then 'missing_url'
          when not has_valid_url then 'malformed_url'
          when hard_deny_hit_count > 0 then 'hard_deny_term'
          when soft_deny_hit_count > 0 and allow_hit_count = 0 then 'soft_deny_without_exception'
          when url_quality_status = 'broken' then 'url_broken'
          when url_quality_status = 'redirect_loop' then 'url_redirect_loop'
          when url_quality_status = 'unavailable' then 'url_unavailable'
          when positivity_score < 65 then 'below_positivity_threshold'
          when suitability_score < 60 then 'low_suitability'
          else null
        end as exclusion_reason
      )
    ) as score_explanation,
    ingested_at
  from dual_scored
)

select
  source_record_id,
  article_id,
  serving_date,
  published_at,
  source_name,
  source_domain,
  language,
  language_resolution_status,
  mentioned_country_code,
  mentioned_country_name,
  mentioned_country_resolution_status,
  title,
  url,
  normalized_url,
  tone_score,
  base_happy_factor,
  positivity_score,
  suitability_score,
  happy_factor,
  happy_factor_version,
  is_positive_feed_eligible,
  positive_guardrail_version,
  exclusion_reason,
  suitability_gate_reason,
  allow_hit_count,
  soft_deny_hit_count,
  hard_deny_hit_count,
  url_quality_status,
  url_quality_checked_at,
  url_http_status,
  url_quality_penalty,
  headline_shape_penalty,
  source_quality_adjustment,
  score_explanation,
  ingested_at
from finalized
where serving_date >= date_sub(current_date(), interval 180 day)
