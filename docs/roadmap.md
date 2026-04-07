# TidingsIQ Roadmap

## Objective

Deliver a portfolio-ready ELT project that ingests bounded GDELT news metadata, models it in BigQuery with Bruin, and serves a filtered positive-news feed through Streamlit.

## Current State

Completed:
- Terraform-managed GCP foundation
- Bronze GDELT ingestion into BigQuery
- Silver normalization and deterministic deduplication
- Gold guardrailed `happy_factor` scoring with feed eligibility metadata
- Gold guardrail reference table for title allow/deny rules
- finalized GDELT source findings and Bronze field-mapping evidence
- Gold serving contract no longer depends on `language`
- Gold run-metrics history for operational visibility
- Streamlit app querying Gold only
- Bronze archive bucket plus initial retention controls
- pipeline containerization for Cloud Run Jobs
- applied pipeline automation for Artifact Registry, Cloud Run Job, and paused Cloud Scheduler
- Streamlit app containerization and Cloud Run hosting path

Operational notes:
- `bronze_staging` is a supporting operational dataset for the Bronze merge load path
- the pipeline Cloud Run Job currently uses `2Gi` memory
- the scheduler remains paused until automation is explicitly enabled for recurring runs
- a manual Cloud Run execution succeeded on `2026-04-06` after redeploying the updated pipeline image
- hosted app deployment is currently disabled in the active environment
- the latest source finding is that `TranslationInfo` is empty in the sampled landed GKG rows, so `language` remains internal and unresolved rather than part of the serving contract
- the current Gold default feed is `is_positive_feed_eligible = true` with `happy_factor >= 65`

## Next Steps

1. Decide when to unpause the scheduled pipeline runs.
2. Improve tests, security, and reviewability for final portfolio presentation.
3. Integrate the final Streamlit UI design.
4. Finalize architecture and deployment documentation.
5. Decide whether to deepen scoring beyond title guardrails using validated GKG fields.

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
10. Bronze/Silver enrichment and Gold guardrailed scoring

## Future Work

- Cloud Run deployment for the Streamlit app
- scheduler unpause and operational run cadence review
- stronger data quality checks and alerting
- broader positive-feed QA and rule tuning
- final documentation polish, including an architecture diagram
