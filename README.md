# TidingsIQ: Positive News Intelligence Pipeline

TidingsIQ is a portfolio data engineering project that builds a low-cost, cloud-native ELT pipeline for global news intelligence. The system ingests news metadata from GDELT, lands and transforms it in BigQuery with Bruin, provisions supporting GCP resources with Terraform, and serves sentiment-filtered results through a Streamlit app.

The core product is a queryable feed of recent articles ranked by a configurable `happy_factor`, intended to surface more positive news coverage without pretending to solve sentiment perfectly.

## Scope

This repository now includes the first infrastructure scaffold, a working Bronze Bruin ingestion asset, and the core design docs. It defines the target architecture, data contract, scoring approach, and implementation sequence before the Silver, Gold, and application layers are implemented.

Included in scope:
- GCP infrastructure managed with Terraform
- BigQuery as the warehouse and compute engine
- Bruin for ingestion, SQL transformations, orchestration, and checks
- Streamlit as a lightweight analytical frontend

Not in scope for the current scaffold:
- production-grade MLOps or custom NLP models
- full editorial quality scoring
- real-time streaming ingestion

## Planned System

Data flow:

`GDELT -> Bruin ingestion -> BigQuery bronze -> BigQuery silver -> BigQuery gold -> Streamlit`

Serving model:

- `gold.positive_news_feed`

Primary user control:

- `happy_factor` threshold filter in the Streamlit UI

## Repository Layout

```text
.
├── app/
│   └── streamlit/
├── docs/
│   ├── architecture.md
│   ├── data_contract.md
│   ├── happy_factor.md
│   └── implementation_plan.md
├── infra/
│   └── terraform/
├── pipeline/
│   └── bruin/
│       ├── pipeline.yml
│       └── assets/
└── scripts/
```

`infra/terraform/` and `pipeline/bruin/` now contain the first implementation slices. `app/streamlit/` and `scripts/` remain placeholders for later phases.

## Documentation Index

- [Architecture](docs/architecture.md): system boundaries, responsibilities, and runtime flow
- [Data Contract](docs/data_contract.md): planned Bronze, Silver, and Gold schemas
- [Happy Factor](docs/happy_factor.md): initial scoring approach and validation rules
- [Implementation Plan](docs/implementation_plan.md): phased build sequence and exit criteria
- [Terraform Foundation](infra/terraform/README.md): initial GCP and BigQuery infrastructure scaffold
- [Bruin Scaffold](pipeline/bruin/README.md): local setup notes and placeholder asset layout

## Design Principles

- Keep the first release batch-oriented, deterministic, and inexpensive to run.
- Make the Gold model the stable contract for the application.
- Preserve enough raw detail for debugging, but avoid storing unnecessary payload.
- Mark uncertain upstream mappings explicitly until validated against actual GDELT inputs.
- Prefer explainable SQL-friendly logic over opaque heuristics.

## Current Status

The repository has an applied Terraform foundation, a working Bronze ingestion slice in Bruin, and the supporting design docs. Silver and Gold remain placeholders, and the Streamlit app has not been added yet.

Planned retention and archival policy is documented, but not yet implemented in infrastructure or pipeline operations.

## Next Build Order

1. Implement Silver normalization and deterministic deduplication.
2. Compute `happy_factor` in Gold and expose the feed through Streamlit.
3. Add retention and archive mechanics for Bronze, Silver, and Gold.
4. Harden checks, replay behavior, and project presentation.
5. Polish the top-level GitHub-facing documentation and repo presentation for evaluation.
