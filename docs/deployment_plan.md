# TidingsIQ Deployment Plan

## Purpose

This document captures the intended cloud deployment shape for TidingsIQ after the local-first pipeline and app slices are stable.

It covers two separate concerns:

- scheduled pipeline execution
- hosted application serving

They should remain separate in both infrastructure and IAM.

## Current State

Implemented in the repository:

- Terraform-managed GCP foundation
- Bruin pipeline running locally against BigQuery
- Streamlit app running locally against `gold.positive_news_feed`
- pipeline container path for Cloud Run Job execution
- Terraform automation for Artifact Registry, Cloud Run Job, and Cloud Scheduler
- Terraform-managed restricted-egress path for the main pipeline and Bronze archive Cloud Run jobs
- reporting Cloud Run Job path and Monitoring-based email notifications
- Bronze archive Cloud Run Job, scheduler, and Monitoring resources in repository, designed to reuse the pipeline image while running under a dedicated archive service account
- Streamlit app container and Terraform hosting path for a Cloud Run service
- public dashboard currently live on the direct Cloud Run URL: `https://tidingsiq-app-eglccrtc7q-el.a.run.app/`

Not implemented as a public, always-on deployment contract:

- container build and release flow in GCP
- a hardened public edge in front of the already-live direct Cloud Run app

## Deployment Targets

### 1. Pipeline Runtime

Recommended target:

- Cloud Run Jobs

Recommended trigger:

- Cloud Scheduler

Recommended flow:

`Cloud Scheduler -> Cloud Run Job -> bruin run pipeline/bruin/pipeline.yml -> BigQuery`

Example cadence target:

- every 6 hours
- timezone: `<SCHEDULE_TIME_ZONE>`
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
- dedicated VPC, subnet, Serverless VPC Access connector, Cloud Router, and Cloud NAT path for restricted outbound traffic
- dedicated pipeline service account
- Secret Manager or environment-based runtime configuration

Pipeline service account responsibilities:

- run BigQuery jobs
- read and write the `bronze`, `silver`, and `gold` datasets plus the supporting `bronze_staging` and `gold_staging` datasets used by merge load paths
- read any required runtime secrets
- write logs to Cloud Logging

Current prep work already in the repo:

- a pipeline Dockerfile
- a container entrypoint that writes `.bruin.yml` from environment variables
- a default container command that runs `bruin run pipeline/bruin/pipeline.yml`
- Terraform resources for the Artifact Registry repository, Cloud Run Job, and Cloud Scheduler trigger
- Terraform resources for a dedicated egress VPC, connector, NAT path, deny rules, and blocked-egress monitoring
- a reusable Cloud Run Job and Cloud Scheduler configuration path

Rollout guidance:

- manual Cloud Run execution should still stay the first smoke check after image changes
- when restricted egress is enabled, keep the pipeline and Bronze archive schedulers paused until public article validation still succeeds through the connector-backed path
- review blocked firewall logs after the first manual run and first scheduled run; unusual publisher redirects may need rule tuning before steady-state activation
- the reporting and Bronze archive schedulers are separate automation paths and should not be paused for a pipeline-only rollout unless their own runtime is being changed
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
- keep reporting on default Cloud Run outbound networking because it does not need article-fetching egress

### 2. Application Runtime

Recommended target:

- direct public Cloud Run service

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
- direct `run.app` HTTPS endpoint

App service account responsibilities:

- read from `gold.positive_news_feed`
- run BigQuery query jobs
- write logs to Cloud Logging

The app should not need write access to Bronze or Silver.

Current serving safety posture:

- keep the app public and unauthenticated
- keep `app_max_instance_count` conservative so abusive traffic cannot scale far
- preserve the current bounded query model:
  - fixed lookback options only
  - fixed brief page size
  - no free-form query/search inputs
  - no unbounded row or page parameters

Rollout guidance:

- verify the direct `run.app` URL serves the app after deploy
- re-test page refreshes, pagination, and filter changes on the direct Cloud Run URL
- keep the instance cap conservative until real traffic justifies additional hardening
- if public traffic later warrants stricter protection or custom-domain branding, the optional AppEdge slice can be enabled in front of the same Cloud Run service

## Recommended Separation

The pipeline and app should not share the same runtime identity.

Keep these separate:

- container images
- Cloud Run resources
- service accounts
- environment variables
- deployment cadence
- egress posture for workloads that fetch external URLs versus workloads that only query first-party services

This keeps the architecture easier to reason about and easier to explain in a portfolio review.

## Suggested Terraform Scope For Future Work

When cloud deployment work starts, Terraform should likely add:

- Artifact Registry repositories
- Cloud Run Job for Bruin
- Cloud Scheduler job for the pipeline cadence
- controlled VPC egress for Cloud Run jobs that fetch external URLs
- Cloud Run service for Streamlit
- optional external HTTPS load balancer and Cloud Armor for future app hardening
- service-account IAM for both runtimes
- Secret Manager bindings if secrets are introduced

The app hosting slice is sufficient for the active public deployment. The app-edge slice remains available as an optional future hardening layer.

## Suggested Delivery Order

1. Retention and archive operations for Bronze, Silver, and Gold
1. Verify the Monitoring email recipient has confirmed any verification email
2. Keep the public app healthy on direct Cloud Run
3. Add CI or release workflow for image build and deployment

## Open Questions

- how often should the pipeline run in cloud automation
- whether the pipeline and app should live in the same GCP project or be split later
- what level of monitoring and alerting is worth adding for a portfolio project
