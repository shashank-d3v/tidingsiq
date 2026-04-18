# TidingsIQ Data Contract

## Purpose

This document defines the planned warehouse contract for TidingsIQ. It is intentionally implementation-oriented: table names, field responsibilities, and quality expectations are specified now so Terraform, Bruin assets, and the Streamlit app can be built against a stable shape later.

The canonical serving table is:

- `gold.positive_news_feed`

Supporting operational table:

- `gold.pipeline_run_metrics`

Where upstream GDELT mappings are not yet validated, the internal field is still defined here but the source mapping is marked as pending.

## Contract Rules

- Bronze preserves source fidelity and ingestion traceability.
- Silver is the normalization and deterministic deduplication boundary.
- Gold is the only table the app should query in v1.
- Internal field names should remain stable even if upstream GDELT mappings change.
- Unvalidated GDELT mappings must be marked as pending, not guessed.

## Dataset and Table Plan

| Layer | Table | Purpose |
|---|---|---|
| Bronze | `bronze.gdelt_news_raw` | Landed source records plus ingestion metadata |
| Silver | `silver.gdelt_news_refined` | Cleaned, normalized, article-level records |
| Gold | `gold.positive_feed_guardrail_terms` | Versioned title-rule reference table for positive-feed eligibility |
| Gold | `gold.positive_news_feed` | Application-facing positive news feed |
| Gold | `gold.pipeline_run_metrics` | Per-run warehouse and scoring metrics for operational visibility |

## Bronze Contract

### Table

`bronze.gdelt_news_raw`

### Grain

One ingested source record per row.

### Required behavior

- replay-safe landed loads keyed by the source record identifier
- batch traceability
- enough raw fidelity for replay and parsing diagnostics
- 45-day query retention in BigQuery before archive and cleanup

### Fields

| Column | Type | Required | Mapping Status | Notes |
|---|---|---:|---|---|
| ingestion_id | STRING | Yes | Internal | Identifier for the ingestion run or batch |
| ingested_at | TIMESTAMP | Yes | Internal | Warehouse load timestamp |
| source_window_start | TIMESTAMP | No | Internal | Lower bound of the fetched source window |
| source_window_end | TIMESTAMP | No | Internal | Upper bound of the fetched source window |
| source_record_id | STRING | No | Validated from GKG | Mapped from `GKGRECORDID` |
| source_collection_identifier | STRING | No | Validated from GKG | Mapped from `SourceCollectionIdentifier` |
| document_identifier | STRING | No | Validated from GKG | Mapped from `DocumentIdentifier` |
| source_url | STRING | No | Partially validated from GKG | Set when `SourceCollectionIdentifier = 1` and the document identifier is a URL |
| source_name | STRING | No | Validated from GKG | Mapped from `V2SOURCECOMMONNAME` |
| source_domain | STRING | No | Derived | Normalized domain derived from `source_url`, with `source_name` fallback when needed |
| title | STRING | No | Partially validated from GKG | Extracted from the `Extras` field via `<PAGE_TITLE>` when present |
| language_raw | STRING | No | Partially validated from GKG | Native language code parsed from `TranslationInfo` when present |
| language | STRING | Yes | Native-first, inferred-second | Resolved language code, defaulting to `und` when unresolved |
| language_resolution_status | STRING | Yes | Derived | `native`, `inferred`, or `undetermined` |
| mentioned_country_code | STRING | Yes | Derived from GKG | Article geography derived from `V2Locations`, defaulting to `ZZ` when unresolved |
| mentioned_country_name | STRING | Yes | Derived from GKG | Country display name derived from `V2Locations`, defaulting to `Unknown` when unresolved |
| mentioned_country_resolution_status | STRING | Yes | Derived | `v2_locations` or `undetermined` |
| published_at | TIMESTAMP | No | Validated from GKG | Mapped from the GKG publication timestamp field |
| tone_raw | FLOAT64 | No | Validated from GKG | First component of `V2Tone` before normalization |
| positive_signal_raw | FLOAT64 | No | Pending GDELT validation | Optional raw positive signal if a reliable source field exists |
| negative_signal_raw | FLOAT64 | No | Pending GDELT validation | Optional raw negative signal if retained |
| bronze_run_total_row_count | INT64 | No | Internal | Repeated run-level count of parsed source rows seen in the latest Bronze ingestion |
| bronze_run_accepted_row_count | INT64 | No | Internal | Repeated run-level count of Bronze rows accepted after containment checks |
| bronze_run_malformed_row_count | INT64 | No | Internal | Repeated run-level count of malformed source rows rejected during containment checks |
| bronze_run_malformed_ratio | FLOAT64 | No | Internal | Repeated run-level malformed-row ratio for the latest Bronze ingestion |
| raw_payload | STRING | No | Internal | JSON-encoded payload retained for audit and debugging |

### Bronze quality expectations

- `ingestion_id` and `ingested_at` must always be populated
- the same replay window should be safe to rerun without losing traceability
- the default transport remains the documented HTTP GDELT endpoint, while deployed runtime overrides are restricted to the expected GDELT host
- source files should fail closed when the resolved host, filename pattern, ZIP structure, row width, or timestamp parsing is suspicious
- `language`, `language_resolution_status`, `mentioned_country_code`, `mentioned_country_name`, and `mentioned_country_resolution_status` should never be blank after Bronze resolution
- `bronze_run_total_row_count`, `bronze_run_accepted_row_count`, `bronze_run_malformed_row_count`, and `bronze_run_malformed_ratio` should preserve run-level containment visibility on successful ingestions
- `raw_payload` currently stores selected raw GKG fields rather than the entire original row to keep Bronze practical and debuggable without retaining unnecessary volume
- Bronze rows older than 45 days should be exportable to GCS without losing row-level traceability
- archived Bronze objects should be retained for 365 days before deletion
- current implementation uses the canonical `scripts/archive_bronze.py` worker plus a Terraform-managed archive bucket and optional scheduled Cloud Run execution

## Silver Contract

### Table

`silver.gdelt_news_refined`

### Grain

One normalized article candidate per row before Gold filtering.

### Required behavior

- normalize URLs, titles, and timestamps
- derive deterministic deduplication keys
- separate duplicates from canonical retained rows

### Fields

| Column | Type | Required | Source | Notes |
|---|---|---:|---|---|
| source_record_id | STRING | Yes | Bronze | Lineage back to the landed Bronze record |
| article_id | STRING | Yes | Derived | Stable internal identifier for the article record |
| ingestion_id | STRING | Yes | Bronze | Last contributing ingestion batch |
| ingested_at | TIMESTAMP | Yes | Bronze | Last contributing ingestion timestamp |
| published_at | TIMESTAMP | No | Bronze normalized | Normalized publication timestamp |
| source_name | STRING | No | Bronze normalized | Cleaned source name |
| source_domain | STRING | No | Derived | Normalized domain from URL |
| language | STRING | Yes | Bronze resolved | Normalized language code |
| language_resolution_status | STRING | Yes | Bronze resolved | `native`, `inferred`, or `undetermined` |
| mentioned_country_code | STRING | Yes | Bronze resolved | Article geography country code derived from `V2Locations` |
| mentioned_country_name | STRING | Yes | Bronze resolved | Article geography country name derived from `V2Locations` |
| mentioned_country_resolution_status | STRING | Yes | Bronze resolved | `v2_locations` or `undetermined` |
| title | STRING | No | Bronze normalized | Cleaned display title |
| normalized_title | STRING | No | Derived | Lowercased and normalized title for matching |
| url | STRING | No | Bronze normalized | Canonical article URL |
| normalized_url | STRING | No | Derived | URL normalized for deduplication |
| tone_score | FLOAT64 | No | Bronze carried forward | Raw GDELT tone component retained for deterministic downstream scoring |
| positive_signal_score | FLOAT64 | No | Derived | Nullable placeholder until an upstream mapping is validated |
| negative_signal_score | FLOAT64 | No | Derived | Nullable placeholder until an upstream mapping is validated |
| dedup_key | STRING | No | Derived | Deterministic key used for duplicate grouping |
| is_duplicate | BOOL | Yes | Derived | True when the row is not the canonical retained record |
| is_near_duplicate_candidate | BOOL | Yes | Derived | Optional candidate flag for future fuzzy dedup work |

### Silver quality expectations

- `source_record_id` must always be populated
- `article_id` must be unique
- `dedup_key` must always be populated
- `is_duplicate` must always be populated
- `language_resolution_status`, `mentioned_country_code`, `mentioned_country_name`, and `mentioned_country_resolution_status` must always be populated
- `tone_score`, when present, should stay within a broad sanity range of `-100` to `100`
- canonical rows should have stable dedup behavior across reruns
- fuzzy or probabilistic deduplication is not required in v1
- Silver should retain 90 days of queryable history in BigQuery
- current implementation uses normalized URL first, then title plus source plus hour bucket as the deterministic dedup fallback
- current implementation keeps the canonical row by ordering on newest `published_at`, then newest `ingested_at`, then descending `article_id`
- current implementation enforces the 90-day retention window in the Silver model itself
- current implementation partitions Silver by `ingested_at` and clusters by `dedup_key`, `source_domain`, and `language`

## Gold Contract

### Table

`gold.positive_news_feed`

### Grain

One scored retained article record per canonical article candidate.

### Required behavior

- expose only consumer-facing fields
- compute and persist `happy_factor`
- separate ranking score from feed eligibility
- keep score logic explainable and versioned

### Fields

| Column | Type | Required | Source | Notes |
|---|---|---:|---|---|
| source_record_id | STRING | Yes | Silver | Exposed for lineage and debugging |
| article_id | STRING | Yes | Silver | Stable application identifier |
| serving_date | DATE | Yes | Derived | Partition and lookback field derived from `DATE(COALESCE(published_at, ingested_at))` |
| published_at | TIMESTAMP | No | Silver | Display and filter field |
| source_name | STRING | No | Silver | Display field |
| language | STRING | Yes | Silver resolved | Detected article language carried forward as informational metadata, not a serving gate |
| language_resolution_status | STRING | Yes | Silver resolved | `native`, `inferred`, or `undetermined` for the detected article language |
| mentioned_country_code | STRING | Yes | Silver resolved | Article-mentioned geography country code carried forward as informational metadata |
| mentioned_country_name | STRING | Yes | Silver resolved | Article-mentioned geography country name carried forward as informational metadata |
| mentioned_country_resolution_status | STRING | Yes | Silver resolved | `v2_locations` or `undetermined` for the article-mentioned geography |
| title | STRING | No | Silver | Display field |
| url | STRING | No | Silver | Link-out target |
| tone_score | FLOAT64 | No | Silver | Exposed for transparency and debugging |
| base_happy_factor | FLOAT64 | Yes | Derived | Pure tone-normalized base score before title guardrails |
| happy_factor | FLOAT64 | Yes | Derived | Guardrailed positivity-oriented score on a 0 to 100 scale |
| happy_factor_version | STRING | Yes | Derived | Current implementation is `v2_1_guardrailed_tone` |
| is_positive_feed_eligible | BOOL | Yes | Derived | Default feed gate combining score threshold and title guardrails |
| positive_guardrail_version | STRING | Yes | Derived | Current title-rule set version, `v1_1_title_rules` |
| exclusion_reason | STRING | No | Derived | Null when eligible, otherwise the reason the row is excluded from the default feed |
| allow_hit_count | INT64 | Yes | Derived | Number of positive allowlist hits in the title |
| soft_deny_hit_count | INT64 | Yes | Derived | Number of soft denylist hits in the title |
| hard_deny_hit_count | INT64 | Yes | Derived | Number of hard denylist hits in the title |
| ingested_at | TIMESTAMP | Yes | Silver | Freshness marker for the record |

### Gold quality expectations

- `source_record_id` must always be populated
- `article_id` must be unique
- `serving_date` must always be populated
- `language`, `language_resolution_status`, `mentioned_country_code`, `mentioned_country_name`, and `mentioned_country_resolution_status` must always be populated
- `base_happy_factor` and `happy_factor` must always be between `0` and `100`
- `is_positive_feed_eligible` must always be populated
- `positive_guardrail_version` must always be populated
- `tone_score`, when present, should stay within a broad sanity range of `-100` to `100`
- eligible rows should not carry hard deny hits
- eligible rows should not carry unresolved soft deny hits
- the app should not depend on unresolved upstream-derived signal columns being present in every release
- language and article geography are informational metadata in Gold; they should not be treated as publisher-origin fields or feed-eligibility gates
- Gold should retain 180 days of queryable history in BigQuery
- current implementation keeps only canonical Silver rows where `is_duplicate = false`
- current implementation retains scored canonical rows even when they are not feed-eligible so the guardrail decision remains explainable
- current implementation enforces the 180-day retention window in the Gold model itself
- current implementation partitions Gold by `serving_date` and clusters by `source_name`

## Gold Guardrail Terms Contract

### Table

`gold.positive_feed_guardrail_terms`

### Grain

One active or inactive title-rule term per row.

### Fields

| Column | Type | Required | Source | Notes |
|---|---|---:|---|---|
| term | STRING | Yes | Internal | Token or phrase used by the guardrail logic |
| rule_class | STRING | Yes | Internal | `deny_hard`, `deny_soft`, or `allow` |
| match_scope | STRING | Yes | Internal | `token` or `phrase` |
| is_active | BOOL | Yes | Internal | Rule activation flag |
| notes | STRING | No | Internal | Human-readable context for maintenance |

## Gold Operational Metrics Contract

### Table

`gold.pipeline_run_metrics`

### Grain

One appended operational run snapshot row.

### Purpose

- preserve a simple warehouse health snapshot history
- expose Bronze, Silver, and Gold row counts over time
- expose score distribution drift at the Gold layer
- expose the latest Bronze containment stats for accepted-row count and malformed-row ratio
- support later freshness and regression alerting without querying the app table directly

### Fields

| Column | Type | Required | Source | Notes |
|---|---|---:|---|---|
| audit_run_at | TIMESTAMP | Yes | Internal | Timestamp when the metrics snapshot was written |
| bronze_row_count | INT64 | Yes | Derived | Current total row count in Bronze |
| silver_row_count | INT64 | Yes | Derived | Current total row count in Silver |
| silver_canonical_row_count | INT64 | Yes | Derived | Current canonical Silver row count |
| silver_duplicate_row_count | INT64 | Yes | Derived | Current duplicate Silver row count |
| latest_bronze_ingestion_accepted_row_count | INT64 | Yes | Derived | Accepted-row count for the latest successful Bronze ingestion |
| latest_bronze_ingestion_malformed_ratio | FLOAT64 | Yes | Derived | Malformed-row ratio recorded for the latest successful Bronze ingestion |
| gold_row_count | INT64 | Yes | Derived | Current serving-table row count |
| gold_min_happy_factor | FLOAT64 | No | Derived | Current minimum `happy_factor` |
| gold_avg_happy_factor | FLOAT64 | No | Derived | Current average `happy_factor` |
| gold_max_happy_factor | FLOAT64 | No | Derived | Current maximum `happy_factor` |
| latest_gold_ingested_at | TIMESTAMP | No | Derived | Latest Gold ingestion timestamp |
| latest_gold_published_at | TIMESTAMP | No | Derived | Latest Gold publication timestamp |

## Deduplication Policy

v1 deduplication should be deterministic and implemented in Silver. The current canonical tie-break policy is:

1. group rows by `dedup_key`
2. keep the row with the newest `published_at`
3. then break ties by newest `ingested_at`
4. then break any remaining ties by descending `article_id`

Current dedup-key strategy:

- normalize URL
- normalize title
- derive a stable dedup key from URL when possible
- fall back to title plus source plus time bucket when URL quality is weak

Near-duplicate detection beyond deterministic rules is optional future work and must not block the first end-to-end release.

## Partitioning, Retention, and Archive

Current chosen partition strategy:

- Silver partitions by `DATE(ingested_at)` to simplify replay and freshness tracking
- Gold partitions by `serving_date = DATE(COALESCE(published_at, ingested_at))` to align with UI lookback behavior while remaining resilient to missing publication timestamps

Current retention targets:

- Bronze: retain 45 days in BigQuery, then archive older partitions to GCS for 365 days before deletion
- Silver: retain 90 days in BigQuery
- Gold: retain 180 days in BigQuery

Current implementation status:

- Bronze archive bucket and object lifecycle are provisioned in Terraform
- Bronze export and delete are executed manually through an operations script
- Silver and Gold retention are enforced in-model today

Archive expectations for Bronze:

- archive objects should be partitionable by export date or source date
- archived files should preserve enough columns to support replay or audit
- cleanup of BigQuery Bronze data must happen only after archive success is confirmed
- the archive bucket should enforce object deletion after 365 days through lifecycle policy

## Open Validation Items

- Confirm whether positive and negative signals come from validated GDELT fields or whether a later Gold version should extend beyond `v1_tone_only`.
- Re-evaluate whether a separate publisher-country concept is worth adding later; the current contract only models article-mentioned geography.
