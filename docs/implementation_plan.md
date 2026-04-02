# TidingsIQ Implementation Plan

## Objective

Deliver a portfolio-ready ELT project that ingests bounded GDELT news metadata, models it in BigQuery with Bruin, and serves a filtered positive-news feed through Streamlit.

The plan favors small phases with clear exit criteria so the project can be built and demonstrated incrementally.

## Current Status

Documentation scaffold complete. Terraform foundation is applied, Bronze ingestion is implemented, Silver normalization is implemented, Gold scoring is implemented, the Streamlit app is implemented, and the initial retention/archive slice is implemented.

Completed in the current phase:
- project framing and scope
- architecture definition
- warehouse data contract
- initial `happy_factor` strategy
- phased implementation plan
- Terraform provider, dataset, service account, and IAM scaffold
- Bruin pipeline, dependency, and placeholder asset scaffold
- bounded Bronze ingestion from GDELT GKG into BigQuery
- deterministic Silver normalization and deduplication
- Gold `happy_factor` scoring with `v1_tone_only`
- Streamlit frontend querying `gold.positive_news_feed`
- Terraform-managed Bronze archive bucket and manual Bronze archive runbook
- Silver 90-day and Gold 180-day retention filters
- pipeline container path for future Cloud Run Job execution

## Phase 1: Terraform Foundation

### Status

Implemented in repository and applied to the target GCP project.

### Goal

Provision the minimum GCP footprint required to support development.

### Deliverables

- Terraform provider configuration
- BigQuery datasets for `bronze`, `silver`, and `gold`
- service accounts and minimum IAM bindings
- variables and outputs for project configuration

### Exit criteria

- `terraform plan` is clean against the target project
- required datasets exist with the expected names
- pipeline and app identities are separated cleanly

### Result

Phase 1 is complete.

## Phase 2: Bruin Project Scaffold

### Status

Implemented in repository as a placeholder scaffold. Real ingestion and transformation logic are still pending.

### Goal

Establish the pipeline project structure without overbuilding it.

### Deliverables

- Bruin project configuration
- one ingestion asset placeholder
- one Silver SQL asset placeholder
- one Gold SQL asset placeholder
- initial data quality checks wired into the asset layout

### Exit criteria

- project structure supports local development
- dataset and table naming matches the documented contract
- checks can be added without redesigning the layout

### Result

Phase 2 is complete.

## Phase 3: Bronze Ingestion

### Status

Implemented in repository using bounded GDELT GKG ingestion with replay-safe row keys.

### Goal

Land a bounded GDELT window into BigQuery Bronze with traceability.

### Deliverables

- working ingestion asset for a controlled source window
- Bronze schema aligned to `docs/data_contract.md`
- replay-safe ingestion metadata

### Exit criteria

- a rerun of the same window does not break traceability
- landed fields match the documented Bronze contract
- uncertain GDELT mappings are still marked explicitly in code and docs

### Result

Phase 3 is complete.

## Phase 4: Silver Normalization and Deduplication

### Status

Implemented in repository with deterministic URL-first deduplication and a title-source-time fallback.

### Goal

Convert landed records into clean article-level rows suitable for downstream consumption.

### Deliverables

- normalized timestamps, titles, and URLs
- derived source domain
- deterministic deduplication logic
- `silver.gdelt_news_refined`
- 90-day Silver retention policy captured in implementation and docs

### Exit criteria

- `article_id` is unique
- duplicate handling is reproducible across reruns
- row-level assumptions are documented where source ambiguity remains

### Result

Phase 4 is complete.

## Phase 5: Gold Scoring Model

### Status

Implemented in repository using a versioned tone-only scoring model.

### Goal

Create the canonical serving model used by the app.

### Deliverables

- `gold.positive_news_feed`
- `happy_factor`
- `happy_factor_version`
- core Gold quality checks
- 180-day Gold retention policy captured in implementation and docs

### Exit criteria

- Gold schema matches the documented contract
- `happy_factor` stays within `0` to `100`
- the model can support a threshold-only app without querying lower layers

### Result

Phase 5 is complete.

## Phase 6: Streamlit Application

### Status

Implemented in repository as a Gold-only frontend.

### Goal

Provide a simple frontend that makes the warehouse output usable.

### Deliverables

- Streamlit app scaffold
- `happy_factor` threshold control
- query path against BigQuery Gold
- lightweight result presentation

### Exit criteria

- the app queries only Gold
- filtering works as expected
- repeated interaction does not require schema changes to the pipeline

### Result

Phase 6 is complete.

## Phase 7: Retention and Archive Operations

### Status

Initial retention and archive slice is implemented in repository with a Terraform-managed Bronze archive bucket, manual Bronze export/delete tooling, and in-model Silver/Gold retention windows.

### Goal

Put explicit lifecycle controls around the warehouse so the project stays inexpensive and operationally credible.

### Deliverables

- Bronze partitioning and 45-day retention policy
- Bronze export path to GCS before BigQuery cleanup
- Bronze archive lifecycle set to delete archived objects after 365 days
- Silver 90-day retention policy
- Gold 180-day retention policy
- IAM and operational notes for archive execution

### Exit criteria

- Bronze data older than 45 days has a documented and testable archive path
- Silver and Gold retention behavior is defined and implementable
- required GCS permissions and lifecycle assumptions are documented before infra changes are applied

### Result

The first retention and archive slice is complete. Fully scheduled archive execution and any partition-specific refinements remain future work.

## Operational Horizon: GCP Automation

### Goal

Move pipeline execution from local runs to scheduled GCP batch execution without changing the warehouse contract.

### Likely Shape

- package the Bruin runner and pipeline code into a container image
- publish the image to Artifact Registry
- execute the pipeline as a Cloud Run Job
- trigger scheduled runs with Cloud Scheduler
- keep service-account access and runtime config managed by Terraform

Current repository state:

- the pipeline container image definition is in place
- the remaining work is publishing it and wiring it into Cloud Run Jobs and Cloud Scheduler

Related future app hosting notes are captured in `docs/deployment_plan.md`.

## Phase 8: Hardening and Presentation

### Goal

Make the project easier to review, demo, and maintain.

### Deliverables

- stronger data quality checks
- better local run instructions
- architecture and implementation docs updated to match reality
- screenshots or demo notes if helpful

### Exit criteria

- documentation matches implementation
- failure modes and replay behavior are documented
- the project is coherent enough to discuss end-to-end in a portfolio review

## Phase 9: Audience Readiness and GitHub Presentation

### Goal

Make the repository easier to evaluate quickly by hiring managers, interviewers, and technical reviewers.

### Deliverables

- a stronger top-level `README.md` with clearer outcomes and demo path
- cleaner repo navigation for first-time reviewers
- polished screenshots, architecture image, or demo notes if they materially improve evaluation
- final wording pass for public-facing technical documentation

### Exit criteria

- a reviewer can understand the project shape from the repository root in a few minutes
- the main GitHub landing page feels intentional rather than purely internal
- portfolio-facing documentation stays consistent with the actual implementation

## Key Risks

- GDELT field mappings may differ from assumptions in the current docs.
- Source data quality may require more normalization than expected.
- Deduplication quality may depend heavily on URL completeness.
- `happy_factor` may need to launch as tone-only if richer sentiment inputs are not validated quickly.
- retention and archive mechanics add storage IAM and operational complexity beyond the initial BigQuery-only slice

## Working Rules

- Do not add complexity before the previous phase is stable.
- Keep BigQuery as the center of gravity for storage and compute.
- Prefer deterministic SQL-friendly logic over speculative heuristics.
- Update the docs when implementation decisions invalidate an earlier assumption.
