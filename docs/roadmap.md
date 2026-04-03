# TidingsIQ Roadmap

## Objective

Deliver a portfolio-ready ELT project that ingests bounded GDELT news metadata, models it in BigQuery with Bruin, and serves a filtered positive-news feed through Streamlit.

## Current State

Completed:
- Terraform-managed GCP foundation
- Bronze GDELT ingestion into BigQuery
- Silver normalization and deterministic deduplication
- Gold `happy_factor` scoring with `v1_tone_only`
- Streamlit app querying Gold only
- Bronze archive bucket plus initial retention controls
- pipeline containerization for Cloud Run Jobs
- applied pipeline automation for Artifact Registry, Cloud Run Job, and paused Cloud Scheduler
- Streamlit app containerization and Cloud Run hosting path

Operational notes:
- `bronze_staging` is a supporting operational dataset for the Bronze merge load path
- the pipeline Cloud Run Job currently uses `2Gi` memory
- the scheduler remains paused until automation is explicitly enabled for recurring runs
- hosted app deployment is currently disabled in the active environment

## Next Steps

1. Decide when to unpause the scheduled pipeline runs.
2. Finalize the transformation layer and supporting checks.
3. Improve tests, security, and reviewability for final portfolio presentation.
4. Finalize architecture and deployment documentation.

## Phases Completed

1. Terraform foundation
2. Bruin scaffold
3. Bronze ingestion
4. Silver normalization and deduplication
5. Gold scoring model
6. Streamlit application
7. Retention and archive operations
8. Pipeline containerization and Cloud Run automation activation
9. Streamlit app Cloud Run deployment

## Future Work

- Cloud Run deployment for the Streamlit app
- scheduler unpause and operational run cadence review
- stronger data quality checks and alerting
- final documentation polish, including an architecture diagram
