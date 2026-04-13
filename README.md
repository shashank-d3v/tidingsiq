# TidingsIQ: Positive News Intelligence Pipeline

TidingsIQ is a portfolio data engineering project that builds a low-cost, cloud-native ELT pipeline for global news intelligence. The system ingests news metadata from GDELT, lands and transforms it in BigQuery with Bruin, provisions supporting GCP resources with Terraform, and serves sentiment-filtered results through a Streamlit app.

The core product is a queryable feed of recent articles ranked by a configurable `happy_factor` and gated by explicit title guardrails, intended to surface more positive news coverage without pretending to solve sentiment perfectly.

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

Primary user controls:

- Brief lookback, date, language, and geography filters in the Streamlit UI
- a warehouse-wide `Pulse` page backed by Gold operational aggregates

## Repository Layout

```text
.
├── app/
│   └── streamlit/
├── docs/
│   ├── architecture.md
│   ├── data_contract.md
│   ├── gdelt_findings.md
│   ├── happy_factor.md
│   └── roadmap.md
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
- [GDELT Findings](docs/gdelt_findings.md): verified upstream GKG column layout, current mappings, and source-quality findings
- [Happy Factor](docs/happy_factor.md): initial scoring approach and validation rules
- [Roadmap](docs/roadmap.md): public build status and next-step summary
- [Authoritative Fetching With Controlled Query Cost](docs/authoritative_fetching_query_cost.md): deferred Streamlit serving design for authoritative warehouse-side filtering, counts, and pagination
- [Deployment Plan](docs/deployment_plan.md): future GCP hosting path for the pipeline and app
- [Terraform Foundation](infra/terraform/README.md): initial GCP and BigQuery infrastructure scaffold
- [Bruin Pipeline](pipeline/bruin/README.md): local setup notes, asset behavior, and validation workflow
- [Streamlit App](app/streamlit/README.md): local UI run instructions and Gold query contract
- [Operations Scripts](scripts/README.md): manual archive and retention helpers
- [Operations Runbook](docs/operations_runbook.md): reset, smoke test, scheduler, image, and warehouse debug commands

## Design Principles

- Keep the first release batch-oriented, deterministic, and inexpensive to run.
- Make the Gold model the stable contract for the application.
- Preserve enough raw detail for debugging, but avoid storing unnecessary payload.
- Mark uncertain upstream mappings explicitly until validated against actual GDELT inputs.
- Prefer explainable SQL-friendly logic over opaque heuristics.

## Current Status

The repository has an applied Terraform foundation, a working Bronze ingestion slice in Bruin, a deterministic Silver normalization layer, a versioned Gold scoring model, a Streamlit app that queries Gold only, an initial retention/archive operations slice, and an applied GCP automation path for the pipeline.

The Cloud Run job path, reporting path, and app hosting path are all implemented in the repo. In the current environment, the 6-hour pipeline scheduler is active, the hosted Streamlit service remains intentionally disabled until reactivated, and the Monitoring email channel may still need inbox verification before notifications start arriving.
The infrastructure also includes an operational `bronze_staging` dataset used only by the Bronze merge load path.
The current Gold serving contract now separates score from eligibility: `happy_factor` ranks records, while `is_positive_feed_eligible` keeps obvious non-uplifting titles out of the default feed. The current default serving threshold is `65`.

## Next Build Order

1. Harden security, replay behavior, and public-release posture.
2. Integrate the final Streamlit UI design on top of the stabilized Gold contract.
3. Finalize architecture and deployment documentation.
