# TidingsIQ Deployment Guide

## Purpose

This is the current deployment procedure, replacing the earlier future-only plan.
The [architecture](architecture.md) describes responsibilities; the
[operations runbook](operations_runbook.md) covers recovery and diagnostics.

## Current State

The [October 3 safeguards release](release_safeguards_20261003.md) records the
latest verified frontend/publisher images, success gate and retention update.

Verified **2 October 2026**: project `tidingsiq-dev`, region `asia-south1`, one active
environment. The public URL is <https://tidingsiq-app-eglccrtc7q-el.a.run.app/>.

| Runtime | Trigger, Asia/Kolkata | Identity boundary |
|---|---|---|
| Bruin pipeline job | Daily 06:00 | Pipeline warehouse editor |
| Report job | Daily 06:20 | Gold read-only plus BigQuery job submission |
| Static publisher job | Daily 06:30 | Gold reader, job submission, feed-bucket objectUser |
| Bronze archive job | 03:15 and 15:15 daily | Bronze editor and archive-bucket objectAdmin |
| nginx frontend service | HTTP requests | Feed-bucket objectViewer, read-only mount |

All four schedules were enabled. October 1 and 2 publisher executions succeeded.
The October 2 story-deduplication canary also passed; see
[matching, validation, and rollback](durable_story_deduplication.md).
The dated [engagement rollout](engagement_rollout_20261002.md) records the latest
frontend revision observed in this documentation set, following the story release.
Observed settings were request-based billing, automatic scaling, zero minimum
and two maximum instances, 1 vCPU/512 MiB. Verify live settings before a release.
Streamlit remains in the repository, not in the public traffic path.

No CDN, load balancer, Cloud Armor, VPC connector, or NAT is active. Those optional
Terraform modules should be enabled only for a demonstrated requirement.

## Inputs and Infrastructure

Use the [Terraform input reference](../infra/terraform/README.md). Static serving
requires `enable_app_hosting`, `enable_pipeline_reporting`, and
`enable_static_dashboard`, plus pinned frontend/publisher image digests.
`static_publish_schedule_paused` defaults to `true` for a guarded first rollout.
The active environment has it set to `false` after successful verification.

Keep local variables and credentials ignored. Inspect every plan for unrelated
pipeline/archive changes. Service-level scaling is intentionally ignored by
Terraform so a console emergency shutdown is not silently undone. Template
min/max settings alone do not re-enable a manually stopped service.

## Frontend Release

Build from a new allowlisted context, not the repository root:

```bash
python3 app/static/build_production.py --output <NEW_FRONTEND_CONTEXT>
docker buildx build --platform linux/amd64 \
  -t <FRONTEND_IMAGE_TAG> --push <NEW_FRONTEND_CONTEXT>
```

Resolve the pushed digest and record it as `app_container_image`. The artifact
contains only six public assets and nginx configuration. No local data, scripts,
tests, README, credentials, or preview labels are shipped. Production data comes
from the private GCS mount, not a build-time export.

For an existing correctly configured service, stage the image without traffic:

```bash
gcloud run services update <APP_SERVICE_NAME> --project=<GCP_PROJECT_ID> \
  --region=<REGION> --image=<FRONTEND_IMAGE_DIGEST> \
  --no-traffic --revision-suffix=<UNIQUE_RELEASE_SUFFIX>
```

Inspect revision configuration/readiness and the [release checklist](public_release_checklist.md).
Promote only the verified static revision:

```bash
gcloud run services update-traffic <APP_SERVICE_NAME> --project=<GCP_PROJECT_ID> \
  --region=<REGION> --to-revisions=<STATIC_REVISION_NAME>=100
```

If the service was deliberately disabled, select the static revision while it is
still stopped; explicitly re-enable automatic scaling only when ready. Follow the
runbook's emergency-stop procedure if public checks fail. Do not automatically
restore the costly Streamlit revision.

## Publisher Release

Use a separate minimal context. `Dockerfile.publisher` expects **flat filenames**:

```bash
mkdir <NEW_PUBLISHER_CONTEXT>
cp app/static/Dockerfile.publisher <NEW_PUBLISHER_CONTEXT>/Dockerfile
cp scripts/publish_static_feed.py app/static/build_snapshot.py \
  app/static/story_matcher.py <NEW_PUBLISHER_CONTEXT>/
docker buildx build --platform linux/amd64 \
  -t <PUBLISHER_IMAGE_TAG> --push <NEW_PUBLISHER_CONTEXT>
```

Record the resolved digest in `static_publisher_image`. Before releasing the
revised publisher, apply a reviewed Terraform plan that grants its identity
`roles/run.viewer` on the pipeline job and removes live-feed age expiry. Confirm
those settings before the canary; an image-only update cannot provision them.
This repository change alone does not update the deployed job or bucket.

Set the required pipeline job/region arguments, update the job, and run a canary
before enabling a newly created schedule:

```bash
gcloud run jobs update <STATIC_PUBLISHER_JOB_NAME> --project=<GCP_PROJECT_ID> \
  --region=<REGION> --image=<PUBLISHER_IMAGE_DIGEST> \
  --args="--project=<GCP_PROJECT_ID>,--bucket=<STATIC_FEED_BUCKET>,--location=<BIGQUERY_LOCATION>,--pipeline-region=<REGION>,--pipeline-job=<PIPELINE_JOB_NAME>"
gcloud run jobs execute <STATIC_PUBLISHER_JOB_NAME> --project=<GCP_PROJECT_ID> \
  --region=<REGION> --wait
```

Verify success logs, manifest date, referenced hashes, gzip sizes, approved fields,
and a real browser load. A successful job is necessary but does not replace HTTP
verification. Manifest publication occurs only after uploaded data validation;
failed publication retains the old edition. Reflect any schedule pause/resume in
local Terraform variables and reconcile state after imperative deployments.

## Pipeline, Reporting, and Archive Releases

Keep their releases independent of the frontend. Build the pipeline image using
`pipeline/bruin/Dockerfile`, pin the intended runtime digests, and manually smoke
test changed jobs. The archive has its own `bronze_archive_container_image`
override; do not overwrite it blindly during a pipeline-only release. A warehouse
reset is an exceptional destructive operation, not a normal deployment step.

See [pipeline runtime instructions](../pipeline/bruin/README.md) and the
[operations runbook](operations_runbook.md#image-and-deployment-debug).

## Live Data and Billing References

After the October 2 story release, the default range retained 6,493 articles in
4,532 groups (1,042,936 gzip bytes); the 30-day range retained 17,851 articles in
13,135 groups (2,966,139 gzip bytes). These dated observations supersede the
earlier same-day collapsed export, not fixed limits. Open pages retain their
edition until reload.

The [September cost estimate](history/static_dashboard_cost_estimate_20260930.md)
remains a dated, assumption-based budget. Request-based billing removes idle
minimum-instance charges at min=0; requests, start/stop time, transfer, storage,
and jobs can still cost money. No documentation claim establishes a current bill.

Historical rollout IDs/digests are preserved in the [rollout report](history/static_dashboard_deployment_20260930.md).
For the next release, read live settings rather than deploying a historical digest
or applying an old saved Terraform plan.
