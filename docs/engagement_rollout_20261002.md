# Engagement measurement and legacy-client handling — 2 October 2026

The frontend update was deployed on `tidingsiq-dev`, `asia-south1`.
At rollout, revision `tidingsiq-app-engagement-v2-20261002` received 100% of public traffic.
Pinned frontend image:
`asia-south1-docker.pkg.dev/tidingsiq-dev/tidingsiq-app/tidingsiq-static@sha256:d8a0fe1c0b42d603fa6633748f07e035bcab764040b035d4b7401cc7c27a60bb`.
The previous rollback revision is `tidingsiq-app-story-v2-20261002`.
Publisher images, schedules, warehouse data and runtime IAM were not changed.

## Legacy client

All `/_stcore/` requests now return HTTP 410, explicitly cacheable for one day.
The matching installed Streamlit bundle uses default fetch caching for its
health/host-config requests. Compatible browsers can answer repeated probes
from cached rejection responses; clients bypassing cache may continue requests.
In particular, the old health
endpoint no longer reports a successful Streamlit health check. `/healthz`
remains available directly to nginx locally; Cloud Run intercepts that public
path upstream, so public verification uses the actual dashboard routes.

The prior logs showed an unidentified address/agent repeatedly calling health
and host-config. Returning 410 prevents successful legacy sessions; it cannot
force a remote browser or bot to stop issuing requests. Subsequent aggregate logs
are needed to establish whether the traffic decreased.

The initial non-cacheable rejection was followed by 40 Chrome 150 requests
between 13:21:04 and 13:22:02 UTC, approximately three seconds per pair. After
the cache refinement, a five-minute request-log query around 13:31 UTC contained
six release-check requests and no Chrome 150 requests. This is a short observed
cessation, not proof that the remote client is permanently stopped or that caching
alone caused it. Compare with a longer subsequent observation window.

**3 October, 12:11 IST follow-up:** the latest one-hour log query returned 14
records, below its 10,000-record limit: 12 HTTP requests and two structured
events. It contains zero legacy endpoint requests and zero WebSocket upgrades.
One measured page load has an engagement event, with no recorded article clicks.
This may include self-use and is too small for an audience or conversion claim.
The pinned v2 revision still receives 100% traffic, automatic scaling/max two
remain set, and public route/feed/measurement checks pass. Aggregate evidence is
`logs/runs/20261002-engagement/latest-summary-20261003.json`.

## Measurement definitions

`analytics.mjs` sends bounded same-origin GET requests to
`/events/v1/<random-page-id>/<event>/<view>/<days>`. The endpoint accepts only
allowlisted dimensions and GET with no query parameters, returns HTTP 204 and
`Cache-Control: no-store`, and logs structured `tidingsiq-engagement-v1` events.

- **Page load:** once per successful initial feed load, not on range reload.
- **Engaged page load:** once after ten continuous visible seconds, or an
  interaction with navigation, range, filters, search, pagination or an article.
- **Article click:** primary click on a headline or Read story link. No article
  URL, article identifier, title, publisher name or search text is transmitted.
- **View/range changes:** fixed enum/days only. No filter values are transmitted.
- **Engagement rate:** distinct engaged page IDs / distinct loaded page IDs.
- **Article click rate:** page IDs with an article click / loaded page IDs.

The identifier stays in page memory and changes on reload. There are no cookies,
localStorage visitor IDs, cross-site scripts, new cloud databases or credentials.
Do Not Track, Global Privacy Control, webdriver and `?analytics=off` disable
collection. Measurement is enabled only on `.run.app` hosts; local previews and
future custom domains are excluded until explicitly configured. Each page emits
at most 50 events. Collection failure never retries or interrupts the dashboard.
This is not a server-side abuse rate limit.

The application event log omits addresses and user agents. Existing platform
request logs still include standard network metadata, and ordinary nginx request
logs continue. Logs inherit the project's existing retention. The Methodology
page explains measurement and standard hosting logs. Do not call this complete
anonymity or verified people tracking. Events can be blocked or forged, and the
system does not measure cross-visit retention or returning readers.

## Read-only reporting

Export requests and events with `gcloud logging read --format=json`, bounding
the requested time window and checking that the returned count is below the
chosen limit. Use project `tidingsiq-dev` and service `tidingsiq-app`.

Request filter:

```text
resource.type="cloud_run_revision"
resource.labels.service_name="tidingsiq-app"
logName="projects/tidingsiq-dev/logs/run.googleapis.com%2Frequests"
timestamp>="2026-10-03T00:00:00Z"
timestamp<"2026-10-10T00:00:00Z"
```

Event filter uses the same resource/service/time bounds and:

```text
jsonPayload.event_schema="tidingsiq-engagement-v1"
```

```bash
python3 scripts/analyse_traffic.py --requests <REQUEST_LOG_JSON> \
  --events <EVENT_LOG_JSON> --start 2026-10-03 --end 2026-10-10
```

The script emits aggregates without addresses; reserved all-zero/all-f QA IDs,
unsuccessful events, and orphan engagement/click IDs are excluded from rates.
Browser-looking request counts remain explicitly labelled as proxies. Automated
browser checks use `?analytics=off`; endpoint checks use reserved all-f IDs.
Do not enable billing exports or create paid resources simply to obtain a report.

Baseline for September 23–29 UTC is saved under ignored rollout evidence:
5,852 requests, 16 homepage requests, 14 browser-like homepage requests,
11 distinct browser-like homepage addresses, 5,587 legacy endpoint calls and
1,861 WebSocket upgrades. Engagement was not instrumented in that period.

For a week-one comparison, use October 3–9 UTC and allow billing reporting time
to settle before drawing cost conclusions. Disclose usage-date timezones, shared
free allowances, rollout/QA activity and reporting delays. Compare aggregate
requests, legacy endpoints and measured engagement with the baseline; page IDs
are not people or returning visitors.

## Verification and rollback

- 13 JavaScript tests, 20 static Python tests and two traffic-analysis tests pass.
- nginx syntax and local container routing pass at the existing 512 MiB limit.
- Staged and public checks verify dashboard, module, manifest/feed row counts,
  legacy rejection, empty/no-store events, and blocked invalid/private routes.
- Staged browser checks verify Brief/Pulse/Methodology, the privacy notice,
  30-day loading and ten rendered cards without page errors.
- Browser-generated reserved page, engagement and article-click events are
  verified in Cloud Logging and excluded from audience reporting.
- A real-browser default-fetch check verifies the second obsolete-path request
  is served from cache with zero transferred bytes; the first reaches nginx.
- Live revision retains request-based billing, 1 vCPU/512 MiB, automatic scaling,
  no warm minimum, and maximum two instances.

Evidence: `logs/runs/20261002-engagement/` (ignored). Local Terraform's frontend
image pin has been updated and a verified refresh-only plan with no cloud
resource actions has been applied. Do not apply an unrelated infrastructure plan.
Rollback traffic to `tidingsiq-app-story-v2-20261002` if needed and restore its
prior image pin; that removes event instrumentation and restores its legacy
health compatibility. Keep the static serving architecture.
