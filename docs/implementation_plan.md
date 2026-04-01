# TidingsIQ Implementation Plan

## Objective

Deliver a portfolio-ready ELT project that ingests bounded GDELT news metadata, models it in BigQuery with Bruin, and serves a filtered positive-news feed through Streamlit.

The plan favors small phases with clear exit criteria so the project can be built and demonstrated incrementally.

## Current Status

Documentation scaffold complete. Terraform foundation is applied, Phase 2 scaffold is committed, and Phase 3 Bronze ingestion is implemented.

Completed in the current phase:
- project framing and scope
- architecture definition
- warehouse data contract
- initial `happy_factor` strategy
- phased implementation plan
- Terraform provider, dataset, service account, and IAM scaffold
- Bruin pipeline, dependency, and placeholder asset scaffold
- bounded Bronze ingestion from GDELT GKG into BigQuery

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

### Goal

Convert landed records into clean article-level rows suitable for downstream consumption.

### Deliverables

- normalized timestamps, titles, and URLs
- derived source domain
- deterministic deduplication logic
- `silver.gdelt_news_refined`

### Exit criteria

- `article_id` is unique
- duplicate handling is reproducible across reruns
- row-level assumptions are documented where source ambiguity remains

## Phase 5: Gold Scoring Model

### Goal

Create the canonical serving model used by the app.

### Deliverables

- `gold.positive_news_feed`
- `happy_factor`
- `happy_factor_version`
- core Gold quality checks

### Exit criteria

- Gold schema matches the documented contract
- `happy_factor` stays within `0` to `100`
- the model can support a threshold-only app without querying lower layers

## Phase 6: Streamlit Application

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

## Phase 7: Hardening and Presentation

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

## Key Risks

- GDELT field mappings may differ from assumptions in the current docs.
- Source data quality may require more normalization than expected.
- Deduplication quality may depend heavily on URL completeness.
- `happy_factor` may need to launch as tone-only if richer sentiment inputs are not validated quickly.

## Working Rules

- Do not add complexity before the previous phase is stable.
- Keep BigQuery as the center of gravity for storage and compute.
- Prefer deterministic SQL-friendly logic over speculative heuristics.
- Update the docs when implementation decisions invalidate an earlier assumption.
