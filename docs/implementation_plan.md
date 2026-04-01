# TidingsIQ Implementation Plan v1

## Objective

Implement TidingsIQ as a low-cost, cloud-native ELT portfolio project that ingests global news from GDELT, transforms it in BigQuery through Bruin, and serves positivity-filtered results through Streamlit.

The project should be developed in small, reviewable phases so that architecture, data contract, and implementation remain aligned.

---

## Phase 1. Foundation and Documentation

### Goal
Establish the project identity, architecture, and data contract before writing implementation code.

### Deliverables
- README completed at a starter level
- architecture documentation
- data contract documentation
- Happy Factor definition
- phased implementation plan

### Status
Completed

---

## Phase 2. Infrastructure Skeleton

### Goal
Provision the minimum required GCP resources through Terraform.

### Scope
- configure GCP provider
- create BigQuery datasets:
  - bronze
  - silver
  - gold
- create service accounts for:
  - pipeline execution
  - app access
- define variables and outputs
- document required environment inputs

### Deliverables
- `infra/terraform/main.tf`
- `infra/terraform/variables.tf`
- `infra/terraform/outputs.tf`
- `infra/terraform/README.md`

### Notes
Keep the first version minimal. Avoid overbuilding IAM and optional resources early.

---

## Phase 3. Bruin Project Scaffold

### Goal
Create the initial Bruin project structure for ingestion and transformation.

### Scope
- create one Python ingestion asset
- create one Silver SQL asset
- create one Gold SQL asset
- add placeholder checks for `not_null` and `unique`

### Deliverables
- Bruin project configuration
- ingestion asset stub for GDELT
- SQL asset stubs for Silver and Gold
- quality check placeholders

### Notes
At this stage, focus on structure and contracts, not full implementation depth.

---

## Phase 4. Bronze Ingestion

### Goal
Implement the first working ingestion path from GDELT into BigQuery Bronze.

### Scope
- fetch a bounded GDELT time window
- parse and normalize selected fields
- add ingestion metadata
- minimize unnecessary payload
- materialize into `bronze.gdelt_gkg_raw`

### Deliverables
- working Python asset
- Bronze schema aligned to data contract
- sample loaded records in BigQuery

### Validation
- successful local execution
- successful warehouse load
- schema matches documented contract

---

## Phase 5. Silver Transformation

### Goal
Normalize Bronze records into a cleaned, article-level Silver model.

### Scope
- clean core fields
- normalize titles and URLs
- derive source domain
- normalize tone score
- implement deterministic deduplication
- mark candidate near-duplicates

### Deliverables
- `silver.gdelt_news_refined`
- deterministic dedup logic
- candidate near-duplicate flag

### Validation
- row counts make sense relative to Bronze
- duplicates are reduced
- key fields are normalized as expected

---

## Phase 6. Gold Serving Model

### Goal
Build the canonical application-facing model.

### Scope
- compute `happy_factor`
- expose only app-relevant fields
- finalize the serving schema
- ensure idempotent refresh behavior

### Deliverables
- `gold.positive_news_feed`
- documented scoring logic reflected in SQL
- initial quality checks

### Validation
- records are filterable by Happy Factor
- schema matches data contract
- app can depend on this table only

---

## Phase 7. Streamlit Application

### Goal
Create a simple but portfolio-ready frontend over the Gold model.

### Scope
- title and project description
- Happy Factor slider
- date filters
- query function against BigQuery
- result list or article cards
- caching to reduce repeated scans

### Deliverables
- minimal Streamlit app
- parameterized query path
- secrets-based configuration placeholder

### Validation
- app loads successfully
- filtering works
- repeated interactions behave efficiently

---

## Phase 8. Quality, Replay, and Polish

### Goal
Make the project more robust and portfolio-ready.

### Scope
- tighten quality checks
- document replay and idempotency behavior
- improve README
- add sample screenshots
- refine query patterns
- add developer notes and local run instructions

### Deliverables
- better documentation
- improved checks
- cleaner project presentation

---

## Phase 9. Optional Near-Duplicate Enhancement

### Goal
Add a second-pass similarity-based deduplication enhancement if justified by observed duplicate volume.

### Scope
- identify likely duplicate candidate groups
- test similarity-based comparison logic
- optionally introduce MinHash-style or comparable probabilistic methods
- keep this logic modular and non-blocking for the main pipeline

### Deliverables
- experimental or optional fuzzy dedup module
- comparison notes against deterministic dedup

### Notes
This phase is explicitly optional for the first end-to-end release.

---

## Execution Principles

### Build one bounded slice at a time
Each phase should be independently reviewable.

### Prefer correctness over premature complexity
Start with deterministic implementations where possible.

### Keep assumptions explicit
If an upstream field mapping or formula is uncertain, mark it clearly.

### Make the Gold model the anchor
The application should depend on one canonical serving model.