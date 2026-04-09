# TidingsIQ Streamlit App

This app is the local-first frontend for TidingsIQ. It queries only `gold.positive_news_feed` and renders three user-facing sections:

- `The Brief` for the editorial feed
- `Pulse` for live feed analytics
- `Methodology` for the warehouse and scoring explainer

The filter rail currently exposes a small set of user-facing controls:

- minimum `happy_factor`
- lookback window in days
- date within the currently loaded lookback window
- detected language
- mentioned geography

Current serving constraint:

- Gold serves the canonical scored feed and now carries detected language plus article-mentioned geography as informational metadata
- these fields should not be labeled as source language, publisher country, or country of publication
- the warehouse contract should not use language or article geography as serving gates
- the app can still filter locally on these informational fields for browsing
- the app surfaces `Recommended` stories from eligible rows and `More To Explore` from `below_threshold` rows only
- `More To Explore` also applies an app-side safety screen so obviously disturbing titles do not surface even if they slipped through the current warehouse guardrails
- the current default minimum score is `65`, softened from the initial `70`
- feed cards are ordered from least optimistic to most optimistic within each section

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

The app queries only the Gold table and does not reach into Bronze or Silver. It fetches the current lookback window from Gold, then applies `happy_factor`, date, language, and geography filters locally in the Streamlit layer to keep UI interactions responsive.

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
