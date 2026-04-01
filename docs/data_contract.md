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

- append-oriented loads
- batch traceability
- enough raw fidelity for replay and parsing diagnostics

### Fields

| Column | Type | Required | Mapping Status | Notes |
|---|---|---:|---|---|
| ingestion_id | STRING | Yes | Internal | Identifier for the ingestion run or batch |
| ingested_at | TIMESTAMP | Yes | Internal | Warehouse load timestamp |
| source_window_start | TIMESTAMP | No | Internal | Lower bound of the fetched source window |
| source_window_end | TIMESTAMP | No | Internal | Upper bound of the fetched source window |
| source_record_id | STRING | No | Pending GDELT validation | Upstream record identifier if exposed consistently |
| document_identifier | STRING | No | Pending GDELT validation | Document or article identifier from source data |
| source_url | STRING | No | Pending GDELT validation | Source article URL if available |
| source_name | STRING | No | Pending GDELT validation | Publisher or source name if available |
| title | STRING | No | Pending GDELT validation | Raw article title or headline if available |
| language | STRING | No | Pending GDELT validation | Language code if available |
| published_at | TIMESTAMP | No | Pending GDELT validation | Best available publication timestamp |
| tone_raw | FLOAT64 | No | Pending GDELT validation | Raw tone-related numeric signal before normalization |
| positive_signal_raw | FLOAT64 | No | Pending GDELT validation | Optional raw positive signal if a reliable source field exists |
| negative_signal_raw | FLOAT64 | No | Pending GDELT validation | Optional raw negative signal if retained |
| raw_payload | JSON | No | Internal | Parsed raw payload retained for audit and debugging |

### Bronze quality expectations

- `ingestion_id` and `ingested_at` must always be populated
- the same replay window should be safe to rerun without losing traceability
- `raw_payload` retention should be reviewed against cost once the source shape is confirmed

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
| tone_score | FLOAT64 | No | Derived | Tone normalized to a consistent internal scale |
| positive_signal_score | FLOAT64 | No | Derived | Derived positive signal, if upstream mapping is validated |
| negative_signal_score | FLOAT64 | No | Derived | Derived negative signal, if retained |
| dedup_key | STRING | No | Derived | Deterministic key used for duplicate grouping |
| is_duplicate | BOOL | Yes | Derived | True when the row is not the canonical retained record |
| is_near_duplicate_candidate | BOOL | Yes | Derived | Optional candidate flag for future fuzzy dedup work |

### Silver quality expectations

- `article_id` must be unique
- `is_duplicate` must always be populated
- canonical rows should have stable dedup behavior across reruns
- fuzzy or probabilistic deduplication is not required in v1

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
| happy_factor_version | STRING | Yes | Derived | Formula version, for example `v1_tone_only` or `v1_tone_plus_signal` |
| ingested_at | TIMESTAMP | Yes | Silver | Freshness marker for the record |

### Gold quality expectations

- `article_id` must be unique
- `happy_factor` must be between 0 and 100
- `happy_factor_version` must always be populated
- the app should not depend on nullable upstream-derived signals being present in every release

## Deduplication Policy

v1 deduplication should be deterministic and implemented in Silver. The preferred first-pass strategy is:

- normalize URL
- normalize title
- derive a stable dedup key from URL when possible
- fall back to title plus source plus time bucket when URL quality is weak

Near-duplicate detection beyond deterministic rules is optional future work and must not block the first end-to-end release.

## Partitioning and Refresh

The final partition strategy is still open. The likely choices are:

- partition by `DATE(ingested_at)` to simplify replay and freshness tracking
- partition by `DATE(published_at)` to align with UI filtering

This should be decided after the first realistic query patterns are tested in BigQuery.

## Open Validation Items

- Confirm the exact GDELT field that maps to `source_record_id`.
- Confirm whether `title`, `source_name`, and `published_at` are directly available or need derivation.
- Confirm whether positive and negative signals come from validated GDELT fields or whether v1 should ship as tone-only.
- Confirm whether `source_country` is reliable enough to expose in Gold.
