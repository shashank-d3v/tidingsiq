# TidingsIQ Terraform Foundation

This directory contains the first infrastructure slice for TidingsIQ. It provisions the minimum GCP resources needed to support the data pipeline and app:

- BigQuery datasets: `bronze`, `silver`, `gold`
- pipeline service account for Bruin workloads
- app service account for Streamlit reads
- minimum BigQuery IAM bindings for both identities

## Prerequisites

- Terraform `>= 1.6`
- access to a target GCP project
- Google application default credentials or another supported Terraform authentication method
- required APIs already enabled in the target project, at minimum BigQuery and IAM

This scaffold does not enable project APIs automatically. That is intentional to keep the first version small and permission-conscious.

If Bronze archival to GCS is added later, Cloud Storage must also be enabled in the target project.

## Files

- `versions.tf`: Terraform and provider constraints
- `variables.tf`: input variables
- `main.tf`: provider, datasets, service accounts, and IAM
- `outputs.tf`: useful resource outputs
- `terraform.tfvars.example`: starter local variable file
- `future_multi_environment.md`: reference notes for a possible future multi-environment setup

## Usage

Create a local variable file from the example. `terraform.tfvars` is intended for machine-local configuration and is gitignored.

```bash
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform fmt -recursive
terraform validate
terraform plan
```

Apply only after reviewing the plan against the intended project:

```bash
terraform apply
```

## Input Variables

| Name | Required | Default | Purpose |
|---|---|---|---|
| `project_id` | Yes | none | Target GCP project ID |
| `environment` | No | `dev` | Environment label and service account suffix |
| `region` | No | `us-central1` | Provider region |
| `bigquery_location` | No | `US` | BigQuery dataset location |
| `labels` | No | `{}` | Extra labels for supported resources |

## Provisioned Access Model

Pipeline service account:
- project role: `roles/bigquery.jobUser`
- dataset role on `bronze`, `silver`, `gold`: `roles/bigquery.dataEditor`

App service account:
- project role: `roles/bigquery.jobUser`
- dataset role on `gold`: `roles/bigquery.dataViewer`

This is the minimum working split for the planned architecture:
- the pipeline can create and update warehouse objects
- the app can run query jobs but only read the serving dataset

Additional permissions likely needed for the planned retention and archive phase:

Pipeline service account:
- bucket-level role on the Bronze archive bucket: `roles/storage.objectAdmin` on a dedicated bucket is the practical first version
- existing BigQuery roles are likely sufficient for export jobs because the pipeline already has `roles/bigquery.jobUser` and dataset access

Terraform operator or CI identity:
- permission to create and manage the archive bucket and lifecycle rules
- permission to manage bucket IAM bindings

Why `roles/storage.objectAdmin` first:
- it supports writing archive files and handling replay-safe reruns without forcing append-only object naming
- it can be tightened later if the archive path is guaranteed to be write-once

## Notes

- This repository currently targets a single active environment.
- Dataset IDs are intentionally plain: `bronze`, `silver`, and `gold`.
- `delete_contents_on_destroy` is disabled to avoid accidental dataset deletion behavior.
- If stricter IAM boundaries are required later, move from dataset-wide editor access to more specific table or routine permissions after the first end-to-end slice is working.
- If you revisit a multi-environment setup later, see `future_multi_environment.md`.
- Planned retention targets are Bronze 45 days with GCS archive, Silver 90 days, and Gold 180 days.
- Planned archive lifecycle is to retain Bronze archive objects in GCS for 365 days and then delete them automatically.
