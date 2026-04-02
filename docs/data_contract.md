# TidingsIQ Data Contract

## Purpose

This document defines the planned warehouse contract for TidingsIQ. It is intentionally implementation-oriented: table names, field responsibilities, and quality expectations are specified now so Terraform, Bruin assets, and the Streamlit app can be built against a stable shape later.

The canonical serving table is:

- `gold.positive_news_feed`

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
| Gold | `gold.positive_news_feed` | Application-facing positive news feed |

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
| document_identifier | STRING | No | Validated from GKG | Mapped from `V2DOCUMENTIDENTIFIER` |
| source_url | STRING | No | Partially validated from GKG | Set when `V2SOURCECOLLECTIONIDENTIFIER = 1` and the document identifier is a URL |
| source_name | STRING | No | Validated from GKG | Mapped from `V2SOURCECOMMONNAME` |
| title | STRING | No | Partially validated from GKG | Extracted from the `Extras` field via `<PAGE_TITLE>` when present |
| language | STRING | No | Partially validated from GKG | Extracted from `TranslationInfo` when a source-language code is present |
| published_at | TIMESTAMP | No | Validated from GKG | Mapped from the GKG publication timestamp field |
| tone_raw | FLOAT64 | No | Validated from GKG | First component of `V2Tone` before normalization |
| positive_signal_raw | FLOAT64 | No | Pending GDELT validation | Optional raw positive signal if a reliable source field exists |
| negative_signal_raw | FLOAT64 | No | Pending GDELT validation | Optional raw negative signal if retained |
| raw_payload | STRING | No | Internal | JSON-encoded payload retained for audit and debugging |

### Bronze quality expectations

- `ingestion_id` and `ingested_at` must always be populated
- the same replay window should be safe to rerun without losing traceability
- `raw_payload` currently stores selected raw GKG fields rather than the entire original row to keep Bronze practical and debuggable without retaining unnecessary volume
- Bronze rows older than 45 days should be exportable to GCS without losing row-level traceability
- archived Bronze objects should be retained for 365 days before deletion

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
| article_id | STRING | Yes | Derived | Stable internal identifier for the article record |
| ingestion_id | STRING | Yes | Bronze | Last contributing ingestion batch |
| ingested_at | TIMESTAMP | Yes | Bronze | Last contributing ingestion timestamp |
| published_at | TIMESTAMP | No | Bronze normalized | Normalized publication timestamp |
| source_name | STRING | No | Bronze normalized | Cleaned source name |
| source_domain | STRING | No | Derived | Normalized domain from URL |
| source_country | STRING | No | Pending GDELT validation | Country is optional until a reliable source mapping is confirmed |
| language | STRING | No | Bronze normalized | Normalized language code |
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

- `article_id` must be unique
- `is_duplicate` must always be populated
- canonical rows should have stable dedup behavior across reruns
- fuzzy or probabilistic deduplication is not required in v1
- Silver should retain 90 days of queryable history in BigQuery
- current implementation uses normalized URL first, then title plus source plus hour bucket as the deterministic dedup fallback

## Gold Contract

### Table

`gold.positive_news_feed`

### Grain

One app-ready article record per retained article.

### Required behavior

- expose only consumer-facing fields
- compute and persist `happy_factor`
- keep score logic explainable and versioned

### Fields

| Column | Type | Required | Source | Notes |
|---|---|---:|---|---|
| article_id | STRING | Yes | Silver | Stable application identifier |
| published_at | TIMESTAMP | No | Silver | Display and filter field |
| source_name | STRING | No | Silver | Display field |
| source_country | STRING | No | Silver | Optional filter field |
| language | STRING | No | Silver | Optional filter field |
| title | STRING | No | Silver | Display field |
| url | STRING | No | Silver | Link-out target |
| tone_score | FLOAT64 | No | Silver | Exposed for transparency and debugging |
| positive_signal_score | FLOAT64 | No | Silver | Nullable if v1 launches before this mapping is confirmed |
| negative_signal_score | FLOAT64 | No | Silver | Nullable if not used in v1 |
| happy_factor | FLOAT64 | Yes | Derived | Positivity-oriented score on a 0 to 100 scale |
| happy_factor_version | STRING | Yes | Derived | Current implementation is `v1_tone_only` |
| ingested_at | TIMESTAMP | Yes | Silver | Freshness marker for the record |

### Gold quality expectations

- `article_id` must be unique
- `happy_factor` must be between 0 and 100
- `happy_factor_version` must always be populated
- the app should not depend on nullable upstream-derived signals being present in every release
- Gold should retain 180 days of queryable history in BigQuery
- current implementation keeps only canonical Silver rows where `is_duplicate = false`

## Deduplication Policy

v1 deduplication should be deterministic and implemented in Silver. The preferred first-pass strategy is:

- normalize URL
- normalize title
- derive a stable dedup key from URL when possible
- fall back to title plus source plus time bucket when URL quality is weak

Near-duplicate detection beyond deterministic rules is optional future work and must not block the first end-to-end release.

## Partitioning, Retention, and Archive

The final partition strategy is still open. The likely choices are:

- partition by `DATE(ingested_at)` to simplify replay and freshness tracking
- partition by `DATE(published_at)` to align with UI filtering

This should be decided after the first realistic query patterns are tested in BigQuery.

Current retention targets:

- Bronze: retain 45 days in BigQuery, then archive older partitions to GCS for 365 days before deletion
- Silver: retain 90 days in BigQuery
- Gold: retain 180 days in BigQuery

These are documented design targets and are not yet implemented as active lifecycle controls.

Archive expectations for Bronze:

- archive objects should be partitionable by export date or source date
- archived files should preserve enough columns to support replay or audit
- cleanup of BigQuery Bronze data must happen only after archive success is confirmed
- the archive bucket should enforce object deletion after 365 days through lifecycle policy

## Open Validation Items

- Confirm whether positive and negative signals come from validated GDELT fields or whether a later Gold version should extend beyond `v1_tone_only`.
- Confirm whether `source_country` is reliable enough to expose in Gold.
