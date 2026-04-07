# TidingsIQ Streamlit App

This app is the Phase 6 frontend for TidingsIQ. It queries only `gold.positive_news_feed` and exposes a small set of user-facing controls:

- minimum `happy_factor`
- lookback window in days
- result row limit
- eligible-feed-only toggle, enabled by default

Current serving constraint:

- Gold serves the canonical scored feed without using `language` as part of the public contract
- `language` remains an internal Bronze/Silver evaluation field until the GKG source provides something defensible
- the app defaults to `is_positive_feed_eligible = true` so the default feed reflects title guardrails as well as score
- the current default minimum score is `65`, softened from the initial `70`

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

The app queries only the Gold table and does not reach into Bronze or Silver.

Current expected columns:

- `source_record_id`
- `article_id`
- `serving_date`
- `published_at`
- `source_name`
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
