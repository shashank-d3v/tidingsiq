# Publication and frontend safeguards — 3 October 2026

Deployed and verified in `tidingsiq-dev`, `asia-south1` on 3 October 2026.
The [public dashboard](https://tidingsiq-app-eglccrtc7q-el.a.run.app/) serves
revision `tidingsiq-app-safeguards-20261003` with 100% traffic at verification.

## Changes

- The publisher requires the latest pipeline execution to have succeeded, checks
  that its interval contains the metrics audit timestamp, and rechecks the
  execution before manifest replacement. Missing access or an unsuccessful,
  active, changed or unmatched execution blocks publication.
- Its identity has `roles/run.viewer` on the pipeline job only. Runtime arguments
  explicitly distinguish the Cloud Run pipeline region from BigQuery location.
- Bucket lifecycle age expiry applies only to private audits after 45 days.
  Archived versions expire after seven newer versions; live hashed feed files
  have no age expiry. Storage grows until safe, manifest-aware cleanup is added.
- The browser updates the loaded edition's stale warning after 36 hours and
  when visibility changes. This uses local timers without network polling.
  The warning asks readers to reload to check for a newer edition.

## Verification

Both isolated Cloud Build image builds succeeded. The frontend was staged without
public traffic; route/feed checks and browser checks passed before promotion.
Production checks then verified routing, feed loading, private-path rejection,
legacy endpoint rejection and measurement endpoint behavior. Browser checks
confirmed 30-day loading, ten-card rendering, Methodology, and no console errors.
The timer transition and hidden-tab behavior are covered by automated tests;
verification did not leave a production browser open for 36 hours.

Publisher canary `tidingsiq-static-publisher-4rhlr` succeeded from 08:22:47 to
08:27:30 UTC (13:52:47–13:57:30 IST). Publication logged success and zero billed
bytes for the cached feed query; this is not a total deployment-cost measurement.
The public manifest generated at `2026-10-03T08:22:58.796291+00:00` was verified:

| Range | Articles | Story groups | Gzip bytes |
|---|---:|---:|---:|
| 7 days | 6,378 | 4,498 | 1,032,994 |
| 30 days | 17,692 | 13,066 | 2,948,034 |

Both raw hashes, decoded sizes, gzip sizes and article/story counts matched the
manifest. The daily 06:30 IST publisher schedule remains enabled. Local image
pins and Terraform state were reconciled. The final plan contains client/revision
metadata differences only; no image, argument or runtime-setting drift. No broad
mutation plan was applied. The prerequisite targeted apply also cleared client
metadata on the pipeline job, without changing its image or runtime settings.

17 JavaScript tests and 12 publisher regression tests passed before release.
Detailed service/job configurations and verification output are Git-ignored under
`logs/runs/20261003-safeguards/`.

## Images and rollback

Frontend:
`asia-south1-docker.pkg.dev/tidingsiq-dev/tidingsiq-app/tidingsiq-static@sha256:394e5dcbe3f02d6aa8d4b72ec83e0390310c55dfe5142a5ad6b16d22021d6338`.
Publisher:
`asia-south1-docker.pkg.dev/tidingsiq-dev/tidingsiq-app/static-publisher@sha256:54be438f2c313c71ca66f2c69b70048b75938bc2a90f449fe44840e2e8a84e40`.

For frontend recovery, the previous revision is
`tidingsiq-app-engagement-v2-20261002`. The previous publisher digest is
`sha256:f632b09d692edb470d33a31f3c39115f3ed8b76940c1b8ab192cb6c722a11df9`.
An image rollback need not restore feed age expiry or remove read-only pipeline
access. Check saved job arguments before rollback, mirror image pins locally,
and reconcile state. Follow the [runbook](operations_runbook.md) for edition
recovery and the [deployment guide](deployment_plan.md) for future releases.

## Same-day favicon cache refresh

The favicon image remained present and returned HTTP 200. To refresh browser
favicon caches, the HTML reference now includes a content-hash query parameter
and explicit PNG type and 64×64 dimensions. The staged reference and image bytes
were verified before promoting `tidingsiq-app-favicon-20261003` to 100% traffic.
This frontend supersedes the initial safeguards revision; publisher and retention
settings are unchanged. Its pinned image is:
`asia-south1-docker.pkg.dev/tidingsiq-dev/tidingsiq-app/tidingsiq-static@sha256:46dad8bb23118b0f13839e381e57b77080fdef4e4acec5759c1eb898f5e7c462`.
Reload or reopen an existing tab to load the new icon reference.
