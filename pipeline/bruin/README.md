# Bruin Scaffold

This directory contains the Bruin pipeline for TidingsIQ, including the working Bronze, Silver, and Gold layers.

## Included

- `pipeline.yml` with minimal pipeline metadata
- one Python Bronze ingestion asset
- one SQL Silver normalization and deduplication asset
- one SQL Gold scoring asset
- `pyproject.toml` for Python asset dependencies

## Not Included Yet

- committed `.bruin.yml` credentials configuration
- CI execution wiring
- fully automated archive scheduling

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
- `silver.gdelt_news_refined`: implemented with normalization and deterministic deduplication
- `gold.positive_news_feed`: implemented with canonical-row selection and `v1_tone_only` scoring

## Bronze Runtime Notes

The Bronze asset reads GDELT GKG 2.1 15-minute export files directly and lands article metadata into BigQuery.

Important runtime defaults:

- it uses the Bruin interval to decide which GKG files are eligible
- it fetches only the most recent `GDELT_MAX_FILES` files in that interval
- default `GDELT_MAX_FILES` is `4` to keep Phase 3 bounded and inexpensive

Optional environment variables:

- `GDELT_BASE_URL`: override the base GKG feed endpoint
- `GDELT_MAX_FILES`: override the per-run file cap
- `GDELT_TIMEOUT_SECONDS`: HTTP timeout for downloading GDELT files

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
- a source-backed mentioned-country derivation

## Validation

Once Bruin is installed locally and `.bruin.yml` exists, the expected first checks are:

```bash
bruin validate pipeline/bruin/pipeline.yml
bruin run pipeline/bruin/assets/bronze/gdelt_news_raw.py
bruin run pipeline/bruin/assets/silver/gdelt_news_refined.sql
bruin run pipeline/bruin/assets/gold/positive_news_feed.sql
bruin run pipeline/bruin/assets/gold/pipeline_run_metrics.sql
```

Expected warehouse outputs after a successful end-to-end run:

- `bronze.gdelt_news_raw`
- `silver.gdelt_news_refined`
- `gold.positive_news_feed`
- `gold.pipeline_run_metrics`

Current implementation notes:

- Silver keeps deterministic duplicate flags so Gold can expose only canonical rows.
- Gold computes `happy_factor_version = 'v1_tone_only'`.
- Silver retains unresolved positive and negative signal placeholders internally, but Gold does not expose them until the mappings are validated.
- the current Bronze language mapping remains sparse, so `language` stays internal to Bronze and Silver only
- Silver retains the most recent 90 days in-model.
- Gold retains the most recent 180 days in-model.
- Silver partitions on `ingested_at` and clusters by `dedup_key`, `source_domain`, and `language`.
- Gold partitions on `serving_date = DATE(COALESCE(published_at, ingested_at))` and clusters by `source_name`.
- `gold.pipeline_run_metrics` is an append-history operational table for warehouse row counts, duplicate-rate visibility, and score distribution monitoring.

## Current Validation Finding

Most recent verified end-to-end cloud validation on `2026-04-06`:

- direct Bronze downloader validation succeeded against `http://data.gdeltproject.org/gdeltv2/...`
- a manual Cloud Run execution completed successfully after redeploying the updated pipeline image
- Bronze row count: `4426`
- Silver row count: `4426`
- Silver canonical row count: `4337`
- Bronze rows with populated `TranslationInfo`: `0`
- Bronze rows with populated `language`: `0`
- Silver rows with populated `source_domain`: `4426`
- current Gold row count after removing the language gate: `4323`

Current conclusion:

- the current Bronze parser is not obviously dropping language data
- the landed GKG rows themselves do not provide usable `TranslationInfo` in the tested sample
- `source_domain` is already a working derived field in Silver
- `language` should not be treated as a serving-layer dependency in the current contract
- removing `language` from Gold restores a populated serving table without inventing new upstream mappings
- the deployed Cloud Run path is now validated end to end; the current quality gap is upstream metadata sparsity, not pipeline execution

## Container Runtime

The pipeline now includes the container path used by the deployed Cloud Run Job:

- [Dockerfile](/Volumes/SWE/repos/DE%202026/tidingsiq/pipeline/bruin/Dockerfile)
- [container-entrypoint.sh](/Volumes/SWE/repos/DE%202026/tidingsiq/pipeline/bruin/container-entrypoint.sh)

Build from the repository root:

```bash
docker build -f pipeline/bruin/Dockerfile -t tidingsiq-bruin:local .
```

Run locally with ADC mounted or otherwise available to the container runtime:

```bash
docker run --rm \
  -e BRUIN_PROJECT_ID=tidingsiq-dev \
  -e BRUIN_BIGQUERY_LOCATION=asia-south1 \
  -v "$HOME/.config/gcloud:/root/.config/gcloud:ro" \
  tidingsiq-bruin:local \
  validate pipeline/bruin/pipeline.yml
```

Default container command:

```bash
run pipeline/bruin/pipeline.yml
```

The entrypoint writes a local `.bruin.yml` inside the container from environment variables and uses Application Default Credentials. This matches the current Cloud Run Job deployment model, where the runtime identity comes from the attached service account.

The image now initializes its own minimal git repository at build time so Bruin can resolve the workspace root without requiring the host repository to be bind-mounted at runtime.

Current cloud runtime note:

- if Cloud Run still shows source-fetch issues, review the configured base feed URL before reintroducing any SSL workaround
