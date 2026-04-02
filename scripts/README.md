# TidingsIQ Operations Scripts

This directory contains manual operational helpers that sit outside the Bruin pipeline itself.

## `archive_bronze.py`

Exports Bronze rows older than the retention window to GCS and can optionally delete those rows after a successful export.

The script is intentionally explicit:

- it counts eligible rows first
- it defaults to dry-run behavior when `--dry-run` is provided
- it deletes rows only when `--delete-after-export` is set

Example dry run:

```bash
python3 scripts/archive_bronze.py \
  --project-id tidingsiq-dev \
  --archive-uri-prefix gs://your-bronze-archive-bucket/manual \
  --dry-run
```

Example export without deletion:

```bash
python3 scripts/archive_bronze.py \
  --project-id tidingsiq-dev \
  --archive-uri-prefix gs://your-bronze-archive-bucket/manual
```

Example export and cleanup:

```bash
python3 scripts/archive_bronze.py \
  --project-id tidingsiq-dev \
  --archive-uri-prefix gs://your-bronze-archive-bucket/manual \
  --delete-after-export
```

Requirements:

- Google Application Default Credentials or equivalent auth
- `google-cloud-bigquery` available in the active Python environment
- pipeline service account or operator identity with access to the Bronze archive bucket

This script is the current manual Bronze retention path. Scheduling it in GCP belongs to a later automation phase.

