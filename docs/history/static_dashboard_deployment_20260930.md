# Static dashboard production deployment, 30 September 2026

> Historical record: observations and estimates are dated, not current operating instructions. See the [documentation map](../README.md) for maintained guides.

## Result

Public URL: https://tidingsiq-app-eglccrtc7q-el.a.run.app

The public service now serves the static Brief, Pulse, and Methodology. Traffic
is pinned 100% to `tidingsiq-app-static-20260930`; the legacy Streamlit revisions
receive no traffic. Pipeline and archive jobs were not redeployed in this rollout.

Before proceeding, the existing shutdown was verified: manual scaling,
zero instances, and an HTTP 503 response. Traffic was switched while manual zero
remained set, then automatic scaling was enabled only for the static revision.

## Production settings

- Project `tidingsiq-dev`, region `asia-south1`, service `tidingsiq-app`.
- Request-based billing (`cpu-throttling=true`), minimum zero, maximum two
  instances at service and revision level; 1 vCPU, 512 MiB, concurrency 80.
- Frontend image: `asia-south1-docker.pkg.dev/tidingsiq-dev/tidingsiq-app/tidingsiq-static@sha256:416984f952ca74293d3e553220cd0f126a26af36b11ad99427695d582e94ad96`.
- Publisher image: `asia-south1-docker.pkg.dev/tidingsiq-dev/tidingsiq-app/static-publisher@sha256:60288940bac832ba8cc8a213c203ba3944bf9985b6d2c8922cb335840aad0a1f`.
- Private bucket `tidingsiq-dev-static-feed`, public access prevention enforced.
  Frontend identity `tidingsiq-static-reader` has bucket objectViewer only from
  this rollout; its GCS volume is read-only. No BigQuery client runs in nginx.
- `tidingsiq-static-publisher` has objectUser on this bucket, dataViewer on Gold,
  and project jobUser.
- Publisher Scheduler `tidingsiq-static-publisher-schedule` is ENABLED at
  `06:30 Asia/Kolkata` daily, after the existing pipeline/report schedules.
- Failure log alert is configured through the existing notification channel.
  Actual email delivery was not independently tested in this rollout.

## Publication verification

Canary execution `tidingsiq-static-publisher-m7jvc` completed successfully.
Manifest generated at `2026-09-30T06:52:08Z`, using Gold ingestion timestamp
`2026-09-30T00:30:22Z`, with data date `2026-09-30`.

| Range | Articles | Raw bytes | Gzip bytes |
| --- | ---: | ---: | ---: |
| Default 7-day | 6,043 | 3,206,224 | 797,109 |
| Optional 30-day | 17,103 | 9,013,636 | 2,274,646 |

Both ranges preserve the existing inclusive UTC cutoff. The 30-day range downloads
only when selected. An already-open page keeps its edition until reloaded.

The initial publisher canary rejected fresh overnight ingestion because no article
had today's publication date. The corrected check uses ingestion freshness and
pipeline completeness, permits yesterday's publication dates, and rejects an
empty serving window. A regression test covers this case. Failed attempts did
not publish a partial manifest. The successful feed query reported zero billed
bytes on that execution; this is not an estimate of future or total pipeline cost.
Each publisher query has a 500,000,000-byte billing limit.

Publication validates pipeline freshness/completeness, verifies uploaded bytes,
and switches the manifest last with a generation precondition. The old edition
survives a failure. Files are content-hashed; manifest caching is 60 seconds,
feeds are immutable. The page warns if the loaded edition exceeds 36 hours.
The first scheduled execution is still a future event, not a verified result.

## Checks completed

- Seven feed unit tests, four snapshot/artifact tests, four publisher tests passed.
- nginx configuration and frontend image contents checked.
- Production HTTP 200, correct title without an em dash, gzip encoding, sizes,
  SHA-256 filename hashes, row counts, exact 11-field allowlist and cache headers.
- HTTP 404 for ten development paths: helpers, README, tests, `.git`, `.env`,
  data directory, unversioned data, and source map.
- Frontend build context contains only Dockerfile, nginx configuration and five
  public assets. No local fixtures, helper scripts, credentials, or local labels.
- Real-browser pagination, empty search, language filter, reset, 30-day lazy load,
  Brief/Pulse/Methodology navigation, and mobile width checks passed.
- No browser errors, automatic external requests, or WebSockets in tested flows.
- Desktop (1440 px) and mobile (390 px) screenshots inspected.
- Terraform validates. Full plan contains only CLI client/version and revision
  metadata differences, with no image/configuration rollback. A refresh-only
  apply synchronized state; the full mutation plan was not applied.

Evidence is Git-ignored under `logs/runs/20260930-static-deploy/`; screenshots are
under `output/playwright/production-desktop.png` and `production-mobile.png`.

## Billing choice and remaining limits

Request-based billing is the cheaper expected fit for short, intermittent static
requests. Instance-based billing charges for the entire instance lifetime,
including idle time, and can be economical for steady heavy traffic. See
[Google's billing guidance](https://docs.cloud.google.com/run/docs/configuring/billing-settings).
Cloud Run Jobs use instance-based billing during their execution.

The old dashboard already had request-based billing. Changing that switch alone
would not resolve long active requests. This rollout removes the Streamlit
WebSocket session and request-driven warehouse queries. Scrolling, searching,
and filtering loaded data are local browser operations. Leaving the new page
open creates no ongoing polling or WebSocket traffic.

Requests, startup/shutdown, storage, data transfer, scheduled jobs, and the
existing pipeline can still incur charges. Maximum instances is a capacity
control, not a hard rupee cap. No exact future bill is established by this rollout.
The site remains directly public on Cloud Run, without a CDN.
The feed preserves source records; syndicated articles can still repeat titles.

## Emergency stop and recovery

To immediately disable the frontend without restoring Streamlit:

```sh
gcloud run services update tidingsiq-app --project=tidingsiq-dev \
  --region=asia-south1 --scaling=0
```

To pause publication as well:

```sh
gcloud scheduler jobs pause tidingsiq-static-publisher-schedule \
  --project=tidingsiq-dev --location=asia-south1
```

Mirror the publisher pause in the ignored local Terraform variables. Service-level
scaling remains ignored by Terraform so an emergency manual stop is preserved.
Validate the static revision and feed before explicitly resuming automatic
scaling. Do not route back to Streamlit as an automatic rollback. Recover a
previous verified manifest from bucket object versions only after confirming its
referenced files still exist; old feed objects expire after 45 days.

Build future frontend releases with `app/static/build_production.py`, never the
whole repository as public content. Deploy a pinned image without traffic,
verify it, then explicitly promote it. Keep the actual image digests and schedule
state in local Terraform variables; never apply an old saved rollout plan.

## Same-day follow-up

The publisher was subsequently updated to collapse syndicated headlines. See the
[duplicate fix and forward cost estimate](static_dashboard_cost_estimate_20260930.md)
for the subsequent September 30 publisher digest, feed counts, and monthly
planning assumptions. Later story grouping superseded that exporter; see the
[October 2 release](../durable_story_deduplication.md).
The image and counts above describe the initial rollout.
