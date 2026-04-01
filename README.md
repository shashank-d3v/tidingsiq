# TidingsIQ: Positive News Intelligence Pipeline

TidingsIQ is a portfolio data engineering project that builds a low-cost, cloud-native ELT pipeline for global news intelligence. The system ingests news metadata from GDELT, lands and transforms it in BigQuery with Bruin, provisions supporting GCP resources with Terraform, and serves sentiment-filtered results through a Streamlit app.

The core product is a queryable feed of recent articles ranked by a configurable `happy_factor`, intended to surface more positive news coverage without pretending to solve sentiment perfectly.

## Scope

This repository is currently a documentation-first scaffold. It defines the target architecture, data contract, scoring approach, and implementation sequence before any infrastructure, ingestion assets, or application code are added.

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
└── scripts/
```

The directories above are intentionally present but not yet implemented.

## Documentation Index

- [Architecture](docs/architecture.md): system boundaries, responsibilities, and runtime flow
- [Data Contract](docs/data_contract.md): planned Bronze, Silver, and Gold schemas
- [Happy Factor](docs/happy_factor.md): initial scoring approach and validation rules
- [Implementation Plan](docs/implementation_plan.md): phased build sequence and exit criteria

## Design Principles

- Keep the first release batch-oriented, deterministic, and inexpensive to run.
- Make the Gold model the stable contract for the application.
- Preserve enough raw detail for debugging, but avoid storing unnecessary payload.
- Mark uncertain upstream mappings explicitly until validated against actual GDELT inputs.
- Prefer explainable SQL-friendly logic over opaque heuristics.

## Current Status

The repository has been initialized as a serious project scaffold. Documentation is the current source of truth. No application code, Terraform resources, or Bruin assets have been added yet.

## Next Build Order

1. Provision the minimum GCP and BigQuery foundation with Terraform.
2. Scaffold the Bruin project and a bounded Bronze ingestion path from GDELT.
3. Implement Silver normalization and deterministic deduplication.
4. Compute `happy_factor` in Gold and expose the feed through Streamlit.
