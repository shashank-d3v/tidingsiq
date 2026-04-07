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
- reporting Cloud Run Job path and Monitoring-based email notifications
- pipeline scheduler activated after a warehouse reset and successful post-reset smoke test
- Streamlit app container and Terraform hosting scaffold for Cloud Run service
- app hosting path validated once in Cloud Run and then disabled again in the active environment

Not implemented yet:

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

Current cadence target:

- every 6 hours
- timezone: `Asia/Kolkata`
- target run times: `00:00`, `06:00`, `12:00`, `18:00` IST

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
- an applied Cloud Run Job and an active Cloud Scheduler job in the current project

Current rollout boundary:

- the scheduler is now active on the configured cadence
- a manual Cloud Run execution succeeded on `2026-04-06`, confirming the deployed pipeline can run end to end when the job image is current
- a manual Cloud Run execution also succeeded after the warehouse reset on `2026-04-07`, confirming the active scheduled image can rebuild the warehouse from empty state
- manual Cloud Run execution should still stay the first smoke check after image changes
- the pipeline now defaults to the documented HTTP GDELT feed, so SSL-verify overrides should not be the normal runtime path
- a warehouse reset should happen before regular scheduled execution is activated for the clean-start rollout

### 1A. Reporting Runtime

Recommended target:

- separate Cloud Run Job

Recommended flow:

`Cloud Scheduler -> Cloud Run Job -> query BigQuery metrics -> emit DAILY_PIPELINE_SUMMARY log -> Monitoring email`

Current implementation choice:

- use native Monitoring email notifications for both:
  - immediate pipeline failure alerts
  - daily summary delivery
- avoid a third-party email API dependency in this project phase

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
1. Verify the Monitoring email recipient has confirmed any verification email
2. Review whether the hosted Streamlit app should stay public or gain an auth layer
3. CI or release workflow for image build and deployment

## Open Questions

- how often should the pipeline run in cloud automation
- whether the app should be public, authenticated, or limited to a portfolio demo audience
- whether the pipeline and app should live in the same GCP project or be split later
- what level of monitoring and alerting is worth adding for a portfolio project
