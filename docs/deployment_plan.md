# TidingsIQ Deployment Plan

## Purpose

This document captures the intended cloud deployment shape for TidingsIQ after the local-first pipeline and app slices are stable.

It covers two separate concerns:

- scheduled pipeline execution
- hosted application serving

They should remain separate in both infrastructure and IAM.

## Current State

Implemented now:

- Terraform-managed GCP foundation
- Bruin pipeline running locally against BigQuery
- Streamlit app running locally against `gold.positive_news_feed`

Not implemented yet:

- scheduled cloud execution for the pipeline
- hosted cloud deployment for the Streamlit app
- container build and release flow

## Deployment Targets

### 1. Pipeline Runtime

Recommended target:

- Cloud Run Jobs

Recommended trigger:

- Cloud Scheduler

Recommended flow:

`Cloud Scheduler -> Cloud Run Job -> bruin run pipeline/bruin/pipeline.yml -> BigQuery`

Why this fits:

- low operational overhead
- inexpensive for batch execution
- no always-on compute
- clean fit for the current Bruin plus BigQuery architecture

Expected components:

- Artifact Registry repository for the pipeline container image
- Cloud Run Job for Bruin execution
- Cloud Scheduler job for cadence
- dedicated pipeline service account
- Secret Manager or environment-based runtime configuration

Pipeline service account responsibilities:

- run BigQuery jobs
- read and write the `bronze`, `silver`, and `gold` datasets
- read any required runtime secrets
- write logs to Cloud Logging

### 2. Application Runtime

Recommended target:

- Cloud Run service

Recommended flow:

`Browser -> Cloud Run service -> Streamlit app -> BigQuery gold.positive_news_feed`

Why this fits:

- simple deployment model
- scales down when idle
- matches Streamlit's web-service execution model
- keeps the app separate from pipeline orchestration

Expected components:

- Artifact Registry repository for the app container image
- Cloud Run service for Streamlit
- dedicated app service account
- optional load balancer, custom domain, or auth layer if needed later

App service account responsibilities:

- read from `gold.positive_news_feed`
- run BigQuery query jobs
- write logs to Cloud Logging

The app should not need write access to Bronze or Silver.

## Recommended Separation

The pipeline and app should not share the same runtime identity.

Keep these separate:

- container images
- Cloud Run resources
- service accounts
- environment variables
- deployment cadence

This keeps the architecture easier to reason about and easier to explain in a portfolio review.

## Suggested Terraform Scope For Future Work

When cloud deployment work starts, Terraform should likely add:

- Artifact Registry repositories
- Cloud Run Job for Bruin
- Cloud Scheduler job for the pipeline cadence
- Cloud Run service for Streamlit
- service-account IAM for both runtimes
- Secret Manager bindings if secrets are introduced

Do not add these resources until the local execution paths are stable enough to package.

## Suggested Delivery Order

1. Retention and archive operations for Bronze, Silver, and Gold
2. Pipeline containerization and Cloud Run Job execution
3. App containerization and Cloud Run service deployment
4. CI or release workflow for image build and deployment

## Open Questions

- how often should the pipeline run in cloud automation
- whether the app should be public, authenticated, or limited to a portfolio demo audience
- whether the pipeline and app should live in the same GCP project or be split later
- what level of monitoring and alerting is worth adding for a portfolio project
