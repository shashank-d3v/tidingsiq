# TidingsIQ Runtime IAM Roles

## Scope

This guide describes the roles provisioned by Terraform for the current static
serving design. It distinguishes active runtime identities from the legacy app
identity still present in the hosting module. It is not a claim that every
project-level inherited grant has been independently audited.

Use the real project, dataset, bucket and service-account names from Terraform
outputs/live resources. Do not grant broad roles simply to make a deployment pass.

## Runtime Access Model

| Identity | Scope | Provisioned role | Purpose |
|---|---|---|---|
| Pipeline | Project | `roles/bigquery.jobUser` | Submit warehouse jobs |
| Pipeline | `bronze`, `bronze_staging`, `silver`, `gold`, `gold_staging` | `roles/bigquery.dataEditor` | Ingest, merge, transform and write metrics |
| Reporting | Project | `roles/bigquery.jobUser` | Submit report queries |
| Reporting | `gold` | `roles/bigquery.dataViewer` | Read summaries and run metrics |
| Static publisher | Project | `roles/bigquery.jobUser` | Submit bounded export queries |
| Static publisher | `gold` | `roles/bigquery.dataViewer` | Read eligible feed and freshness metrics |
| Static publisher | Pipeline Cloud Run job | `roles/run.viewer` | Read execution outcomes; no invocation or mutation |
| Static publisher | Private static feed bucket | `roles/storage.objectUser` | Write/read back feed objects; conditional manifest replacement |
| Static reader | Private static feed bucket | `roles/storage.objectViewer` | Read files for the nginx mount |
| Archive | Project | `roles/bigquery.jobUser` | Export/verify/prune queries |
| Archive | `bronze` | `roles/bigquery.dataEditor` | Temporary snapshots, verification and guarded pruning |
| Archive | Bronze archive bucket | `roles/storage.objectAdmin` | Immutable batches, manifests, checkpoint and generation lock |
| Pipeline scheduler | Pipeline job | `roles/run.invoker` | Trigger pipeline only |
| Reporting scheduler | Report job and static publisher job | `roles/run.invoker` | Trigger these two jobs |
| Archive scheduler | Archive job | `roles/run.invoker` | Trigger archive only |
| Cloud Run service agent | Relevant Artifact Registry repository | `roles/artifactregistry.reader` | Pull runtime images |
| Public `allUsers` | Frontend Cloud Run service | `roles/run.invoker` | Read the public website |

## Static Frontend Boundary

With `enable_static_dashboard=true`, the Cloud Run service runs as
`tidingsiq-static-reader`. Its GCS volume is read-only. The public bucket remains
private with uniform bucket-level access and public access prevention; public
website invocation does not make GCS or BigQuery public.

The frontend does not need BigQuery jobUser or dataset roles. Only the separate
publisher can query Gold and write the static feed. Search and filters run in the
browser, so a visitor action cannot submit a warehouse query through nginx.

## Retained Legacy Identity

`main.tf` still provisions the legacy app service account and Gold read/jobUser
bindings when `enable_app_hosting=true`, even in static mode. The active frontend
uses the static-reader identity instead. These retained grants are not required
for static serving; removing them is a separate reviewed infrastructure change,
not an effect of this documentation cleanup.

## Archive Boundary

The scheduled worker is `archive_bronze_incremental.py`. It verifies full rows in
immutable Parquet batches before advancing a checkpoint. The bucket role also
supports creating/removing a generation-conditional lock and updating checkpoint
metadata. The legacy worker's overwrite-by-cutoff behavior is not the scheduled
archive contract. Pipeline/reporting/frontend identities do not need archive-bucket
access from the current role design.

## Validation After IAM Changes

- Inspect Cloud Run's actual service account, not just whether an identity exists.
- Confirm pipeline transforms and report summaries still complete.
- Run a controlled publisher canary and verify files through the public endpoint.
- Confirm the static reader's scoped binding is read-only and the mount cannot write.
- Confirm archive verification succeeds before enabling pruning or resuming its schedule.
- Check schedulers have invocation rights only on their intended jobs.
- Review inherited IAM separately before claiming a strict effective-permission boundary.

Do not test denied writes by mutating live data. Use policy inspection or an
isolated non-production check where needed. Deployment operators require separate
resource-management permissions; runtime grants are not deployment permissions.
