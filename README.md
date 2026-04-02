# TidingsIQ: Positive News Intelligence Pipeline

TidingsIQ is a portfolio data engineering project that builds a low-cost, cloud-native ELT pipeline for global news intelligence. The system ingests news metadata from GDELT, lands and transforms it in BigQuery with Bruin, provisions supporting GCP resources with Terraform, and serves sentiment-filtered results through a Streamlit app.

The core product is a queryable feed of recent articles ranked by a configurable `happy_factor`, intended to surface more positive news coverage without pretending to solve sentiment perfectly.

## Scope

This repository now includes the applied infrastructure foundation, a working Bronze Bruin ingestion asset, the Silver normalization layer, the Gold scoring layer, the initial Streamlit app, and the core design docs.

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

`infra/terraform/`, `pipeline/bruin/`, and `app/streamlit/` now contain working implementation slices. `scripts/` remains available for later operational helpers.
`infra/terraform/`, `pipeline/bruin/`, `app/streamlit/`, and `scripts/` now contain working implementation slices.

## Documentation Index

- [Architecture](docs/architecture.md): system boundaries, responsibilities, and runtime flow
- [Data Contract](docs/data_contract.md): planned Bronze, Silver, and Gold schemas
- [Happy Factor](docs/happy_factor.md): initial scoring approach and validation rules
- [Implementation Plan](docs/implementation_plan.md): phased build sequence and exit criteria
- [Deployment Plan](docs/deployment_plan.md): future GCP hosting path for the pipeline and app
- [Terraform Foundation](infra/terraform/README.md): initial GCP and BigQuery infrastructure scaffold
- [Bruin Pipeline](pipeline/bruin/README.md): local setup notes, asset behavior, and validation workflow
- [Streamlit App](app/streamlit/README.md): local UI run instructions and Gold query contract
- [Operations Scripts](scripts/README.md): manual archive and retention helpers

## Design Principles

- Keep the first release batch-oriented, deterministic, and inexpensive to run.
- Make the Gold model the stable contract for the application.
- Preserve enough raw detail for debugging, but avoid storing unnecessary payload.
- Mark uncertain upstream mappings explicitly until validated against actual GDELT inputs.
- Prefer explainable SQL-friendly logic over opaque heuristics.

## Current Status

The repository has an applied Terraform foundation, a working Bronze ingestion slice in Bruin, a deterministic Silver normalization layer, a versioned Gold scoring model, a Streamlit app that queries Gold only, and an initial retention/archive operations slice.
The repository also includes a pipeline container path for future Cloud Run Job execution.
The next GCP automation slice is now scaffolded in Terraform behind an explicit feature flag.

Planned retention and archival policy is documented, but not yet implemented in infrastructure or pipeline operations.

## Next Build Order

1. Push the pipeline image and enable the Terraform automation slice for Artifact Registry, Cloud Run Jobs, and Cloud Scheduler.
2. Harden checks, replay behavior, and project presentation.
3. Polish the top-level GitHub-facing documentation and repo presentation for evaluation.
