# TidingsIQ Data Contract v1

## Purpose

This document defines the initial data contract for TidingsIQ across the Bronze, Silver, and Gold layers.

The canonical serving model for the application is `gold.positive_news_feed`. All upstream ingestion and transformation logic exists to produce this table in a reliable, deduplicated, and UI-ready form.

---

## Layer Overview

### Bronze
Raw ingested GDELT records with minimal normalization and ingestion metadata.

### Silver
Cleaned and normalized records with deterministic deduplication and candidate near-duplicate marking.

### Gold
Sentiment-enriched, deduplicated, application-facing records used directly by the Streamlit app.

---

## Bronze Model

### Table
`bronze.gdelt_gkg_raw`

### Purpose
Stores raw or near-raw GDELT records landed from the ingestion asset, along with ingestion metadata required for traceability and replay handling.

### Proposed Fields

| Column | Type | Required | Description |
|---|---|---:|---|
| ingestion_id | STRING | Yes | Unique identifier for the ingestion batch or run |
| ingested_at | TIMESTAMP | Yes | Timestamp when the record was loaded |
| source_file_timestamp | TIMESTAMP | No | Timestamp associated with the upstream GDELT fetch window |
| gdelt_record_id | STRING | No | Raw upstream record identifier if available |
| document_identifier | STRING | No | Source document or article identifier from GDELT |
| source_name | STRING | No | Source publication or domain if available |
| source_url | STRING | No | Original source URL |
| title | STRING | No | Article title if available |
| language | STRING | No | Language code if available |
| published_at | TIMESTAMP | No | Article publication timestamp if derivable |
| tone_raw | FLOAT64 | No | Raw tone or sentiment related score from GDELT |
| gcam_raw | STRING | No | Raw GCAM or emotional payload if retained temporarily |
| record_payload | JSON | No | Raw normalized payload for replay and audit support |

### Notes
- Bronze should preserve enough source fidelity for debugging and replay.
- Bronze is append-oriented.
- Data minimization should happen before storage where practical.

---

## Silver Model

### Table
`silver.gdelt_news_refined`

### Purpose
Stores cleaned and normalized article-level records derived from Bronze, with deterministic deduplication and candidate flags for possible near-duplicates.

### Proposed Fields

| Column | Type | Required | Description |
|---|---|---:|---|
| article_id | STRING | Yes | Stable internal article identifier |
| ingestion_id | STRING | Yes | Ingestion batch identifier from Bronze |
| ingested_at | TIMESTAMP | Yes | Timestamp when the source record was loaded |
| published_at | TIMESTAMP | No | Normalized article publication timestamp |
| source_name | STRING | No | Normalized source name |
| source_domain | STRING | No | Extracted and normalized source domain |
| source_country | STRING | No | Source country if available |
| language | STRING | No | Normalized language code |
| title | STRING | No | Cleaned article title |
| normalized_title | STRING | No | Lowercased and normalized title for matching |
| url | STRING | No | Canonical article URL |
| normalized_url | STRING | No | Normalized URL used for deduplication |
| tone_score | FLOAT64 | No | Normalized tone score |
| positive_signal_score | FLOAT64 | No | Derived positive signal score from GDELT fields |
| duplicate_flag | BOOL | Yes | Whether the record is considered a deterministic duplicate |
| dedup_key | STRING | No | Key derived from normalized URL, title, source, and time bucket |
| possible_near_duplicate_flag | BOOL | Yes | Whether the record is a candidate for fuzzy dedup evaluation |

### Notes
- Silver is where normalization happens.
- Deterministic deduplication should be implemented in v1.
- Probabilistic or MinHash-based deduplication can be added later as an optional second-pass enhancement.

---

## Gold Model

### Table
`gold.positive_news_feed`

### Purpose
Provides the final application-facing dataset used by Streamlit for filtering and displaying positive global news.

### Proposed Fields

| Column | Type | Required | Description |
|---|---|---:|---|
| article_id | STRING | Yes | Stable article identifier |
| published_at | TIMESTAMP | No | Article publication timestamp |
| source_name | STRING | No | Human-readable source name |
| source_country | STRING | No | Source country if available |
| language | STRING | No | Article language |
| title | STRING | No | Final cleaned title |
| url | STRING | No | Canonical article URL |
| tone_score | FLOAT64 | No | Final normalized tone score |
| positive_signal_score | FLOAT64 | No | Derived positive signal signal |
| happy_factor | FLOAT64 | Yes | Final positivity-oriented ranking or filter score |
| duplicate_flag | BOOL | Yes | Indicates whether the article was marked as duplicate upstream |
| ingested_at | TIMESTAMP | Yes | Timestamp of most recent ingestion for this record |

### Notes
- This is the canonical serving model for the app.
- The Streamlit app should query only this model in v1.
- `happy_factor` definition will be documented separately in `docs/happy_factor.md`.

---

## Key Design Choices

### Primary Serving Model
`gold.positive_news_feed`

### Primary Key
`article_id`

### Partitioning
Initial recommendation:
- partition by `DATE(ingested_at)` or `DATE(published_at)` depending on query patterns
- final decision to be confirmed during implementation

### Deduplication Strategy
- v1: deterministic deduplication
- v1.1: candidate-based near-duplicate logic
- future: optional probabilistic similarity such as MinHash

### Idempotency
- ingestion should support bounded replay windows
- transformations should avoid duplicate final records during reruns
- merge-based or partition-aware overwrite strategies should be used where appropriate

---

## Open Questions

1. Which exact GDELT fields will be retained in Bronze versus parsed immediately?
2. What is the final formula for `happy_factor`?
3. Should Gold be partitioned by ingestion date or publication date?
4. How much raw payload should be retained for audit versus minimized for cost?
5. What exact rules should define `possible_near_duplicate_flag`?