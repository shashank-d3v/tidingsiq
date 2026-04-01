# Bruin Scaffold

This directory contains the Bruin project scaffold for TidingsIQ. It is intentionally limited to pipeline structure, placeholder assets, and quality-check wiring.

## Included

- `pipeline.yml` with minimal pipeline metadata
- one Python Bronze placeholder asset
- one SQL Silver placeholder asset
- one SQL Gold placeholder asset
- `pyproject.toml` for Python asset dependencies

## Not Included Yet

- real GDELT ingestion logic
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

- `bronze.gdelt_news_raw`: replace the empty DataFrame placeholder with bounded GDELT ingestion logic
- `silver.gdelt_news_refined`: replace the empty schema query with normalization and deterministic deduplication
- `gold.positive_news_feed`: replace the empty schema query with final scoring and serving logic

## Validation

Once Bruin is installed locally and `.bruin.yml` exists, the expected first checks are:

```bash
bruin validate pipeline/bruin/pipeline.yml
bruin run pipeline/bruin/pipeline.yml --asset bronze.gdelt_news_raw
```

The placeholder assets are scaffolding only. They exist to lock in names, dependencies, and quality checks before the real implementation lands.
