# Public Release Checklist

Use for a new release; unchecked items below are requirements, not claims that a
particular rollout has passed. Current procedures are in the [deployment guide](deployment_plan.md).

## Source and Publication

- Confirm the GDELT default is HTTPS and redirects remain host/path validated.
- Preserve bounded retries, input validation, source-attempt tracking and incomplete-window alerting.
- Verify the latest pipeline execution succeeded and contains the metrics audit
  timestamp; failed/active runs and execution changes must block publication.
- Check the publisher's metrics freshness, Gold ingestion time, completeness and low-volume gates.
- Confirm bucket lifecycle rules do not expire live feed files; retain all files
  referenced by the current manifest during any cleanup.
- Run a publisher canary; verify hashed JSON/gzip files before manifest promotion.
- Confirm failure retains the previous edition and older overlapping work cannot replace newer data.
- Verify matcher version, 11 source fields plus `story_id`, article/story counts,
  consistent cross-range assignments, and private audit consistency.
- Confirm filters precede grouping and display sort preserves representatives.

## Public Artifact and Access

- Build the frontend through `app/static/build_production.py`, not the repository root.
- Exclude local data, developer labels, credentials, tests, helper scripts and documentation.
- Keep the feed bucket private with a read-only frontend mount and objectViewer identity.
- Keep Gold/job-submission access on the publisher, not on the public frontend.
- Confirm only intended public routes work; `.env`, `.git`, Python helpers and directory listings return 404.
- Confirm Cloud Run `Ready=True`, the intended static revision receives traffic, and gzip/CSP/cache headers are present.

## Browser and Cost Checks

- Test refresh, date/language/geography filters, search, sorting, pagination, and empty results.
- Test Pulse and Methodology, mobile layout, and score badge contrast/labels.
- Confirm the larger file is lazy-loaded and loaded filters/pages cause no warehouse calls.
- Check the console and network for errors, polling, unexpected origins and WebSockets.
- Keep request-based billing, min=0, conservative max instances; do not undo an emergency manual stop accidentally.
- After a successful rollout, verify the publisher schedule and mirror settings in Terraform inputs.

## Accepted Limits

The direct public endpoint has no active Cloud Armor/CDN layer. Static serving
reduces work per visit but does not eliminate request, transfer, storage or job
costs. A maximum-instance setting is not a hard budget cap. GDELT can be late or
incomplete; retaining an older edition is preferable to publishing invalid data.
Scores and headline/URL/syndication/fuzzy matching do not verify articles or identify every
semantic duplicate. Monitoring configuration does not establish email delivery.
