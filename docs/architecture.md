# TidingsIQ Architecture

## Purpose

TidingsIQ is designed as a small but credible ELT system for global news intelligence. The project demonstrates how to build a warehouse-centric pipeline that ingests external news metadata, standardizes it in BigQuery, and serves a filtered analytical experience through a simple frontend.

The architecture is intentionally batch-oriented and minimal. The goal is a clear, reviewable design that can be implemented incrementally without introducing unnecessary services.

## System Boundary

In scope:
- GDELT as the upstream news metadata source
- GCP infrastructure provisioned with Terraform
- BigQuery datasets for Bronze, Silver, and Gold models
- Bruin-managed ingestion, transformation, orchestration, and data quality checks
- Streamlit as the consumer-facing application

Out of scope for v1:
- event streaming
- custom ML sentiment models
- complex source reputation scoring
- multi-tenant application concerns

## Component Responsibilities

### 1. Terraform

Terraform owns reproducible cloud setup. The first version should provision only what the pipeline requires to run:
- BigQuery datasets
- an operational Bronze staging dataset for merge loads
- a GCS bucket for Bronze archive once retention is implemented
- service accounts
- IAM bindings
- any minimal supporting configuration needed for local-to-cloud execution

Terraform should not contain speculative resources in the first pass.

### 2. GDELT Source

GDELT is the upstream source of article-level or document-level news metadata used by the pipeline.

Current implementation choice:
- Phase 3 uses GDELT GKG 2.1 15-minute export files as the Bronze ingestion source.

Still pending validation:
- whether positive and negative emotional signals should be mapped directly from GKG fields or derived later
- how much of downstream language coverage comes from native `TranslationInfo` versus deterministic inference

The internal contract remains stable even where some upstream mappings are still intentionally nullable.

### 3. Bruin Ingestion Layer

Bruin Python assets will:
- fetch a bounded GDELT GKG input window
- parse only the fields needed for downstream modeling
- resolve language using native `TranslationInfo` first and title-based inference second
- resolve article geography from `V2Locations` into `mentioned_country`
- attach ingestion metadata
- load an idempotent Bronze table keyed by the GKG record identifier

The ingestion step should be idempotent at the batch level. Replay should be controlled through ingestion window parameters, not by manual table cleanup.

### 4. BigQuery Transformation Layer

Bruin SQL assets will materialize three logical layers:

- `bronze`: landed source records plus ingestion metadata
- `silver`: cleaned, normalized, and deduplicated article records
- `gold`: application-facing records with `happy_factor`

Supporting infrastructure also includes `bronze_staging`, which is an operational dataset used by the Bronze load path and is not part of the consumer-facing warehouse contract.

BigQuery is both the storage layer and the compute layer. No separate processing engine is required for v1.

Retention targets for the current design:
- Bronze stays queryable in BigQuery for 45 days
- Silver stays queryable in BigQuery for 90 days
- Gold stays queryable in BigQuery for 180 days
- Bronze records older than 45 days should be archived to GCS before BigQuery cleanup
- Bronze archive objects should be retained in GCS for 365 days and then deleted by lifecycle policy

Current implementation state:
- the Bronze archive bucket and its 365-day lifecycle are provisioned in Terraform
- Silver filters itself to the most recent 90 days
- Gold filters itself to the most recent 180 days
- Bronze archive and cleanup runs remain manual through an operations script today

### 5. Data Quality Layer

Checks should run as close to the transformations as possible. Initial checks should focus on:
- required fields not null in Silver and Gold
- uniqueness of primary identifiers
- valid score ranges for `happy_factor`
- duplicate rate visibility after Silver deduplication

### 6. Streamlit Serving Layer

The Streamlit app queries only the Gold model in v1. It is not responsible for business logic beyond query parameterization and presentation.

Current UI controls:
- `happy_factor` minimum threshold
- lookback window in days
- result limit

The app should remain thin. Any future scheduled execution of the Bruin pipeline belongs in GCP batch infrastructure rather than the Streamlit runtime.

## End-to-End Flow

1. Terraform provisions the minimum GCP and BigQuery footprint.
2. Bruin ingestion fetches a bounded GDELT window and lands data in `bronze.gdelt_news_raw`.
3. Bruin SQL transforms Bronze data into `silver.gdelt_news_refined`.
4. Bruin SQL builds `gold.positive_news_feed`, including `happy_factor`.
5. Streamlit queries Gold and returns filtered results to the user.
6. The pipeline can run locally or through the deployed Cloud Run Job, with Cloud Scheduler kept paused until the cloud execution path is stable.

## Data Model Strategy

### Bronze

Bronze is append-oriented and traceable. It should preserve the source record shape closely enough to debug parsing and replay issues.

### Silver

Silver is the normalization boundary. URL cleanup, title cleanup, timestamp normalization, and deterministic deduplication belong here.

Current metadata posture:
- `source_domain` is a derived publisher/source-domain field
- `mentioned_country` means article-mentioned geography, not publisher origin
- publisher country remains out of scope

### Gold

Gold is the stable consumer contract. It should contain only fields needed by the app and enough metadata to explain the scoring logic.

Current implementation choice:
- Gold keeps only canonical Silver rows where `is_duplicate = false`
- `happy_factor_version = 'v1_tone_only'`
- `happy_factor` is derived from `tone_score` only until richer GDELT signal mappings are validated

## Operational Principles

- Prefer scheduled batch processing over frequent small loads.
- Keep the ingestion window bounded to control cost and replay behavior.
- Make transformations deterministic so reruns do not create duplicate Gold records.
- Treat uncertain GDELT mappings as explicit implementation decisions, not hidden assumptions.
- Keep the active BigQuery footprint intentionally small through explicit retention windows.
- Archive Bronze before deletion so replay and audit remain possible without keeping all history in BigQuery.

## Known Decisions

- BigQuery is the only warehouse and compute platform.
- Bruin is the orchestrator and transformation framework.
- The app will depend on one canonical serving table: `gold.positive_news_feed`.
- The first release uses a configurable threshold, not a complex ranking product.
- Phase 5 uses a tone-only Gold scoring model rather than unvalidated emotional-signal fields.
- Retention targets are Bronze 45 days, Silver 90 days, and Gold 180 days.
- Bronze archive should land in GCS rather than remain indefinitely in BigQuery.
- Archived Bronze objects should expire after 365 days in GCS.
- Bronze export and cleanup currently run as a manual operation rather than a scheduled job.

## Open Items

- Confirm which upstream fields map to positive and negative emotional indicators beyond `V2Tone`.
- Decide whether Bronze archival is implemented as a Bruin-driven export step, a scheduled BigQuery export job, or an external batch script.
