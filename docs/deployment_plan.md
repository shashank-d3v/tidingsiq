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
- pipeline container path for Cloud Run Job execution
- applied Terraform automation for Artifact Registry, Cloud Run Job, and Cloud Scheduler
- scheduler intentionally left paused even though a manual cloud run has now succeeded
- Streamlit app container and Terraform hosting scaffold for Cloud Run service
- app hosting path validated once in Cloud Run and then disabled again in the active environment

Not implemented yet:

- unpaused scheduled cloud execution for the pipeline
- active hosted cloud deployment for the Streamlit app
- container build and release flow in GCP

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

Current prep work already in the repo:

- a pipeline Dockerfile
- a container entrypoint that writes `.bruin.yml` from environment variables
- a default container command that runs `bruin run pipeline/bruin/pipeline.yml`
- Terraform resources for the Artifact Registry repository, Cloud Run Job, and Cloud Scheduler trigger
- an applied Cloud Run Job and a paused Cloud Scheduler job in the current project

Current rollout boundary:

- the scheduler is still paused by design
- a manual Cloud Run execution succeeded on `2026-04-06`, confirming the deployed pipeline can run end to end when the job image is current
- manual Cloud Run execution should still stay the first smoke check after image changes
- the pipeline now defaults to the documented HTTP GDELT feed, so SSL-verify overrides should not be the normal runtime path

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

The app hosting slice is implemented and can be reactivated quickly, but it is intentionally disabled in the current environment until the UI and security posture are finalized.

## Suggested Delivery Order

1. Retention and archive operations for Bronze, Silver, and Gold
2. Unpause the Cloud Scheduler job only after repeated manual Cloud Run executions are clean
3. Review whether the hosted Streamlit app should stay public or gain an auth layer
4. CI or release workflow for image build and deployment

## Open Questions

- how often should the pipeline run in cloud automation
- whether the app should be public, authenticated, or limited to a portfolio demo audience
- whether the pipeline and app should live in the same GCP project or be split later
- what level of monitoring and alerting is worth adding for a portfolio project
