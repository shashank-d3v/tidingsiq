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
- Gold serving contract exposes detected language and article-mentioned geography as informational metadata only
- Gold run-metrics history for operational visibility
- Streamlit app querying Gold only
- Bronze archive bucket plus initial retention controls
- pipeline containerization for Cloud Run Jobs
- applied pipeline automation for Artifact Registry, Cloud Run Job, and active Cloud Scheduler
- daily reporting Cloud Run Job plus Monitoring-based email notifications
- Streamlit app containerization, Cloud Run hosting path, and live public dashboard URL

Operational notes:
- `bronze_staging` is a supporting operational dataset for the Bronze merge load path
- `gold_staging` is a supporting operational dataset for Gold merge loads driven by `dlt`
- the pipeline Cloud Run Job currently uses `2Gi` memory
- the pipeline scheduler now runs every 6 hours in `Asia/Kolkata`
- a manual Cloud Run execution succeeded on `2026-04-06` after redeploying the updated pipeline image
- a post-reset manual Cloud Run execution succeeded on `2026-04-07` before the scheduler was activated
- a manual Cloud Run execution succeeded on `2026-04-16` after provisioning `gold_staging`, correcting the nullable integer load shape for `gold.url_validation_results`, and recreating `gold.positive_news_feed_v3_shadow` with the expected partitioning
- the live public dashboard is available at `https://tidingsiq-app-eglccrtc7q-el.a.run.app/`
- the latest source finding is that `TranslationInfo` is empty in the sampled landed GKG rows, so Gold language metadata still depends heavily on deterministic inference and should remain informational rather than a serving gate
- the current Gold default feed is `is_positive_feed_eligible = true` with `happy_factor >= 65`
- the current score version is `v2_1_guardrailed_tone` and the current title-rule version is `v1_1_title_rules`
- Monitoring email delivery may still require the recipient to confirm the verification email from GCP
- the current `Pulse` page now reads warehouse-wide Gold aggregates and is no longer tied to the Brief's inline compact controls
- the current Streamlit app now shows explicit loading screens during BigQuery-backed Brief refreshes and section switches to keep warehouse latency visible to the user

## Next Steps

1. Finalize evaluator-facing documentation, screenshots, and submission polish.
2. Improve tests and release-review confidence around the public dashboard and Cloud Run paths.
3. Decide whether to deepen scoring beyond title guardrails using validated GKG fields.
4. Decide whether the daily summary job should later move from Monitoring-triggered emails to a richer mail-delivery path.
5. Keep the deferred authoritative-fetching design note available for a later Streamlit serving refactor without changing the current Gold-only app contract.

## Phases Completed

1. Terraform foundation
2. Bruin project foundation
3. Bronze ingestion
4. Silver normalization and deduplication
5. Gold scoring model
6. Streamlit application
7. Retention and archive operations
8. Pipeline containerization and Cloud Run automation activation
9. Streamlit app Cloud Run deployment
10. Bronze/Silver enrichment and Gold guardrailed scoring

## Future Work

- stronger data quality checks and alerting
- broader positive-feed QA and rule tuning
- final documentation polish, including an architecture diagram
- precomputed Gold snapshot table for Pulse aggregates to reduce live BigQuery reads on dashboard load
- progressive Pulse rendering so the page shell appears immediately while slower charts populate incrementally
- deferred app-serving refactor: move truth-defining Brief filters, counts, pagination, and filter-option generation into authoritative BigQuery queries with bounded caching and query cost; see [Authoritative Fetching With Controlled Query Cost](authoritative_fetching_query_cost.md)
