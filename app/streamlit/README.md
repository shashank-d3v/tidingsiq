# TidingsIQ Streamlit App

This app is the local-first frontend for TidingsIQ. It queries only `gold.positive_news_feed` and renders three user-facing sections:

- `The Brief` for the editorial feed
- `Pulse` for warehouse-wide pipeline and feed health analytics
- `Methodology` for the warehouse and scoring explainer

The Brief filter and sorting controls are intended to live inline with the `Recommended` section header. The compact control bar should expose:

- lookback window in days
- detected language
- mentioned geography
- presentation sort order

Current serving constraint:

- Gold serves the canonical scored feed and now carries detected language plus article-mentioned geography as informational metadata
- these fields should not be labeled as source language, publisher country, or country of publication
- the warehouse contract should not use language or article geography as serving gates
- the app can still filter locally on these informational fields for browsing
- the Brief now surfaces only the warehouse-defined eligible feed
- the app no longer exposes a minimum `happy_factor` slider in the Brief because Gold eligibility already defines the feed floor
- the previous `More To Explore` section has been intentionally retired from the Brief after repeated UX and test-case failures, and is not part of the current product path
- feed cards default to most optimistic first unless the active sort changes that display order
- the inline compact controls apply to `The Brief` browsing experience only
- `Pulse` no longer reuses the Brief's filtered row set and instead reads warehouse-wide aggregates from Gold operational metrics plus Gold serving-table summaries

## Local Run

From the repository root:

```bash
python3 -m pip install -r app/streamlit/requirements.txt
streamlit run app/streamlit/app.py
```

## Container Runtime

Build from the repository root:

```bash
docker build -f app/streamlit/Dockerfile -t tidingsiq-streamlit:local .
```

Run locally:

```bash
docker run --rm -p 8501:8080 \
  -e TIDINGSIQ_GCP_PROJECT=tidingsiq-dev \
  -e TIDINGSIQ_GOLD_TABLE=tidingsiq-dev.gold.positive_news_feed \
  -v "$HOME/.config/gcloud:/root/.config/gcloud:ro" \
  tidingsiq-streamlit:local
```

## Stop The App

If the app is running in your terminal, stop it with:

```bash
Ctrl+C
```

If you started it in the background and need to stop it by port:

```bash
lsof -i :8501
kill <pid>
```

## Authentication

The app uses Google Application Default Credentials through the BigQuery client.

Typical local setup:

```bash
gcloud auth application-default login
export TIDINGSIQ_GCP_PROJECT=tidingsiq-dev
```

Optional override:

```bash
export TIDINGSIQ_GOLD_TABLE=tidingsiq-dev.gold.positive_news_feed
```

## Query Contract

The app queries only Gold-layer tables and does not reach into Bronze or Silver directly from the UI.

Current serving behavior:

- `The Brief` fetches the current lookback window from Gold's eligible feed, then applies language and geography filters plus presentation sorting locally in the Streamlit layer to keep browsing interactions responsive
- `Pulse` reads warehouse-wide Gold aggregates and `gold.pipeline_run_metrics` snapshots, so its charts are intentionally independent from the Brief's inline compact controls

Current implementation intentionally stays local-first for Brief browsing responsiveness. The planned future direction is documented in [Authoritative Fetching With Controlled Query Cost](../../docs/authoritative_fetching_query_cost.md): move truth-defining Brief filters, counts, pagination, and filter-option generation into authoritative BigQuery queries while keeping Gold as the only serving source and keeping query cost bounded with short-lived caching.

Current expected columns:

- `source_record_id`
- `article_id`
- `serving_date`
- `published_at`
- `source_name`
- `language`
- `language_resolution_status`
- `mentioned_country_code`
- `mentioned_country_name`
- `mentioned_country_resolution_status`
- `title`
- `url`
- `tone_score`
- `base_happy_factor`
- `happy_factor`
- `happy_factor_version`
- `is_positive_feed_eligible`
- `positive_guardrail_version`
- `exclusion_reason`
- `allow_hit_count`
- `soft_deny_hit_count`
- `hard_deny_hit_count`
- `ingested_at`

## Future Operations Horizon

The app hosting path is intentionally separate from the scheduled pipeline path:

- pipeline automation: Cloud Scheduler -> Cloud Run Job -> Bruin -> BigQuery
- app hosting: Cloud Run service -> Streamlit -> BigQuery Gold
