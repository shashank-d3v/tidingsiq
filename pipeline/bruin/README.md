# Bruin Scaffold

This directory contains the Bruin project scaffold for TidingsIQ. It is intentionally limited to pipeline structure, placeholder assets, and quality-check wiring.

## Included

- `pipeline.yml` with minimal pipeline metadata
- one Python Bronze ingestion asset
- one SQL Silver placeholder asset
- one SQL Gold placeholder asset
- `pyproject.toml` for Python asset dependencies

## Not Included Yet

- production-ready BigQuery SQL transformations
- local or CI execution wiring
- committed `.bruin.yml` credentials configuration

## Local Bruin Configuration

Bruin expects a `.bruin.yml` file at the root of the git repository. That file should stay local because it contains connection details and may contain credentials.

Bruin automatically adds `.bruin.yml` to `.gitignore` the first time it creates the file. This repository also ignores it proactively.

Recommended local connection name used by this scaffold:

- `bigquery-default`

Minimal local example using Application Default Credentials:

```yaml
default_environment: default
environments:
  default:
    connections:
      google_cloud_platform:
        - name: "bigquery-default"
          project_id: "your-gcp-project-id"
          location: "asia-south1"
          use_application_default_credentials: true
```

## Expected Asset Progression

- `bronze.gdelt_news_raw`: implemented as a bounded GDELT GKG 2.1 ingestion step
- `silver.gdelt_news_refined`: replace the empty schema query with normalization and deterministic deduplication
- `gold.positive_news_feed`: replace the empty schema query with final scoring and serving logic

## Bronze Runtime Notes

The Bronze asset reads GDELT GKG 2.1 15-minute export files directly and lands article metadata into BigQuery.

Important runtime defaults:

- it uses the Bruin interval to decide which GKG files are eligible
- it fetches only the most recent `GDELT_MAX_FILES` files in that interval
- default `GDELT_MAX_FILES` is `4` to keep Phase 3 bounded and inexpensive

Optional environment variables:

- `GDELT_MAX_FILES`: override the per-run file cap
- `GDELT_TIMEOUT_SECONDS`: HTTP timeout for downloading GDELT files
- `GDELT_DISABLE_SSL_VERIFY=true`: disable SSL verification if your local certificate chain blocks the download

Current validated mappings:

- `source_record_id`: GKG record identifier
- `document_identifier`: GKG document identifier
- `source_url`: document identifier when the source collection is open-web
- `source_name`: GKG source common name
- `title`: extracted from `Extras` via `<PAGE_TITLE>`
- `published_at`: GKG publication timestamp
- `tone_raw`: first component of `V2Tone`

Still intentionally unresolved in Phase 3:

- `positive_signal_raw`
- `negative_signal_raw`
- a guaranteed language value for every record

## Validation

Once Bruin is installed locally and `.bruin.yml` exists, the expected first checks are:

```bash
bruin validate pipeline/bruin/pipeline.yml
bruin run pipeline/bruin/assets/bronze/gdelt_news_raw.py
```

The Bronze asset now ingests real metadata. Silver and Gold remain schema placeholders until later phases.
