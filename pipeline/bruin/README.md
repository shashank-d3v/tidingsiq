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
          project_id: "<GCP_PROJECT_ID>"
          location: "<BIGQUERY_LOCATION>"
          use_application_default_credentials: true
```

## Expected Asset Progression

- `bronze.gdelt_news_raw`: implemented as a bounded GDELT GKG 2.1 ingestion step
- `silver.gdelt_news_refined`: implemented with normalization and deterministic deduplication
- `gold.positive_feed_guardrail_terms`: implemented as the title-rule reference table
- `gold.positive_news_feed`: implemented with canonical-row selection, guardrailed scoring, and feed eligibility

## Bronze Runtime Notes

The Bronze asset reads GDELT GKG 2.1 15-minute export files directly and lands article metadata into BigQuery.

Important runtime defaults:

- it uses the Bruin interval to decide which GKG files are eligible
- it fetches only the most recent `GDELT_MAX_FILES` files in that interval
- default `GDELT_MAX_FILES` is `4` to keep Phase 3 bounded and inexpensive

Optional environment variables:

- `GDELT_BASE_URL`: override the base GKG feed endpoint; deployed Cloud Run runtimes only allow the documented GDELT host
- `GDELT_MAX_FILES`: override the per-run file cap
- `GDELT_TIMEOUT_SECONDS`: HTTP timeout for downloading GDELT files
- `GDELT_MAX_MALFORMED_RATIO`: fail the run when malformed parsed rows exceed this ratio
- `GDELT_MIN_ACCEPTED_ROW_RATIO`: fail the run when accepted rows collapse sharply versus recent Bronze history
- `GDELT_BASELINE_RUNS`: number of recent Bronze ingestions used for row-count collapse detection

Containment guardrails:

- the default transport stays the documented HTTP endpoint: `http://data.gdeltproject.org/gdeltv2`
- deployed runtimes reject `GDELT_BASE_URL` overrides that do not resolve to `data.gdeltproject.org`
- downloaded files must resolve to the expected host and `*.gkg.csv.zip` filename pattern
- ZIPs must open successfully, contain a readable first member, and produce the expected 27-column GKG 2.1 row shape
- malformed-row ratio and sudden accepted-row collapse now fail the Bronze run instead of limping through parsing

Current validated mappings:

- `source_record_id`: GKG record identifier
- `source_collection_identifier`: GKG source collection identifier
- `document_identifier`: GKG document identifier
- `source_url`: document identifier when the source collection is open-web
- `source_name`: GKG source common name
- `source_domain`: resolved from the article URL with `source_name` fallback
- `title`: extracted from `Extras` via `<PAGE_TITLE>`
- `published_at`: GKG publication timestamp
- `tone_raw`: first component of `V2Tone`
- `language_raw`: parsed from `TranslationInfo` when present
- `language`: native-first, inferred-second
- `mentioned_country_code` and `mentioned_country_name`: article geography derived from `V2Locations`

Still intentionally unresolved in this layer:

- `positive_signal_raw`
- `negative_signal_raw`
- publisher-country inference

## Validation

Once Bruin is installed locally and `.bruin.yml` exists, the expected first checks are:

```bash
bruin validate pipeline/bruin/pipeline.yml
bruin run pipeline/bruin/assets/bronze/gdelt_news_raw.py
bruin run pipeline/bruin/assets/silver/gdelt_news_refined.sql
bruin run pipeline/bruin/assets/gold/positive_news_feed.sql
bruin run pipeline/bruin/assets/gold/pipeline_run_metrics.sql
bruin run pipeline/bruin/assets/gold/positive_feed_guardrail_terms.sql
```

Expected warehouse outputs after a successful end-to-end run:

- `bronze.gdelt_news_raw`
- `silver.gdelt_news_refined`
- `gold.positive_news_feed`
- `gold.positive_feed_guardrail_terms`
- `gold.pipeline_run_metrics`

Current implementation notes:

- Silver keeps deterministic duplicate flags so Gold can expose only canonical rows.
- Gold computes `base_happy_factor`, final `happy_factor`, and `is_positive_feed_eligible`.
- Gold uses `gold.positive_feed_guardrail_terms` for allow, soft deny, and hard deny title rules.
- Gold Python merge loads such as `gold.url_validation_results` use `dlt` and require the operational `gold_staging` dataset to exist in the same BigQuery location as `gold`.
- `gold.url_validation_results` now applies an SSRF safety gate before any network request and before every followed redirect.
- URL validation only attempts `http` and `https` targets whose hostname resolves exclusively to global public IP space.
- URL validation blocks metadata hosts such as `metadata.google.internal`, blocks all IP-literal hosts by default, and fails closed to `status = "unavailable"` without issuing the request.
- Blocked URL targets are logged with a clear reason so Cloud Run logs can distinguish SSRF hardening from remote-site failures.
- Silver retains unresolved positive and negative signal placeholders internally, but Gold does not expose them until the mappings are validated.
- Bronze and Silver now treat `language` as native-first and inferred-second, with explicit resolution status
- Bronze and Silver use `mentioned_country` for article geography from `V2Locations`; they do not model publisher country
- Gold now carries `language`, `language_resolution_status`, `mentioned_country_code`, `mentioned_country_name`, and `mentioned_country_resolution_status` as informational metadata only
- Silver retains the most recent 90 days in-model.
- Gold retains the most recent 180 days in-model.
- Silver partitions on `ingested_at` and clusters by `dedup_key`, `source_domain`, and `language`.
- Gold partitions on `serving_date = DATE(COALESCE(published_at, ingested_at))` and clusters by `source_name`.
- Bronze repeats run-level containment stats on landed rows so downstream operational metrics can expose the latest accepted-row count and malformed-row ratio.
- `gold.pipeline_run_metrics` is an append-history operational table for warehouse row counts, duplicate-rate visibility, score distribution monitoring, and Bronze containment visibility.
- If `gold.pipeline_run_metrics` is ever dropped during a schema reset, recreate the empty partitioned table before rerunning the asset; the append materialization does not bootstrap a missing destination table.

## Validation Notes

Representative validation should confirm:

- the Bronze downloader can fetch a bounded GDELT window
- the Bronze downloader keeps the documented HTTP default path rather than treating this as an HTTPS migration
- deployed runtimes reject arbitrary `GDELT_BASE_URL` hosts before download
- URL validation rejects non-public targets before request dispatch, including metadata hosts, loopback/private/link-local/reserved resolutions, and blocked redirect targets
- URL validation logs blocked targets with an explicit reason and preserves strict timeout and redirect caps
- corrupt ZIPs, unreadable ZIP members, bad row widths, and malformed timestamps fail closed
- sudden accepted-row collapse and elevated malformed-row ratios fail the Bronze run and surface through the existing pipeline failure alert path
- Silver produces deterministic canonical rows
- Gold exposes `is_positive_feed_eligible = true` as the default app-facing feed
- the `dlt`-backed Gold Python load path can materialize into `gold_staging` and merge into `gold`
- language and article-geography metadata remain informational rather than serving gates

## Container Runtime

The pipeline now includes the container path used by the deployed Cloud Run Job:

- [Dockerfile](/Volumes/SWE/repos/DE%202026/tidingsiq/pipeline/bruin/Dockerfile)
- [container-entrypoint.sh](/Volumes/SWE/repos/DE%202026/tidingsiq/pipeline/bruin/container-entrypoint.sh)

Build from the repository root:

```bash
docker build --platform linux/amd64 -f pipeline/bruin/Dockerfile -t tidingsiq-bruin:local .
```

Run locally with ADC mounted or otherwise available to the container runtime:

```bash
docker run --rm \
  -e BRUIN_PROJECT_ID=<GCP_PROJECT_ID> \
  -e BRUIN_BIGQUERY_LOCATION=<BIGQUERY_LOCATION> \
  -v "$HOME/.config/gcloud:/home/tidingsiq/.config/gcloud:ro" \
  tidingsiq-bruin:local \
  validate pipeline/bruin/pipeline.yml
```

Default container command:

```bash
run pipeline/bruin/pipeline.yml
```

The entrypoint writes a local `.bruin.yml` inside the container from environment variables and uses Application Default Credentials. This matches the Cloud Run Job deployment model, where the runtime identity comes from the attached service account.

The image installs Bruin from a pinned GitHub release tarball with SHA-256 verification, ships pinned `uv` binaries for Bruin-managed Python assets, installs Python dependencies from the committed lock export, and runs as a dedicated non-root user.

At runtime, the entrypoint initializes a minimal git repository inside `/workspace` when needed so Bruin can resolve the workspace root without requiring the host repository to be bind-mounted.

The same image now also supports the daily reporting Cloud Run Job, which runs:

```bash
python3 scripts/daily_pipeline_report.py
```

Cloud runtime note:

- if Cloud Run shows source-fetch issues, review the configured base feed URL before reintroducing any SSL workaround
