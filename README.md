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

The repository has an applied Terraform foundation, a working Bronze ingestion slice in Bruin, a deterministic Silver normalization layer, a versioned Gold scoring model, a Streamlit app that queries Gold only, an initial retention/archive operations slice, and an applied GCP automation path for the pipeline.

The Cloud Run Job, Artifact Registry repository, and paused Cloud Scheduler trigger are now provisioned in the target GCP project. App hosting in GCP remains future work.
The infrastructure also includes an operational `bronze_staging` dataset used only by the Bronze merge load path.

## Next Build Order

1. Stabilize manual Cloud Run Job execution, then unpause the Cloud Scheduler trigger.
2. Add hosted deployment for the Streamlit app.
3. Harden checks, replay behavior, and project presentation.
