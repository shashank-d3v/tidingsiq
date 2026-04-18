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

Current Brief control-bar behavior:

- language and region render as compact inline popover triggers rather than always-open multiselect fields
- each closed trigger summarizes the applied state as `Label: Value`, for example `Language: All` or `Region: Angola +4`
- when multiple values are selected, the trigger shows the first selected value plus the count of additional selections
- `Apply` and `Clear` live inside each popover footer instead of below the toolbar
- language and region popovers are expected to close after `Apply` or `Clear`

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
- the app now shows a page-level loading screen during BigQuery-backed Brief refreshes and section switches so navigation does not appear frozen while warehouse reads are in flight

## Local Run

From the repository root:

```bash
python3 -m pip install -r app/streamlit/requirements.txt
export TIDINGSIQ_GCP_PROJECT=<GCP_PROJECT_ID>
streamlit run app/streamlit/app.py
```

The current filter interaction requires Streamlit `1.55.0` or newer because the app relies on controlled `st.popover` state to close language and region popovers after `Apply` and `Clear`.

`TIDINGSIQ_GCP_PROJECT` is required. If `TIDINGSIQ_GOLD_TABLE` is unset, the app derives `<GCP_PROJECT_ID>.gold.positive_news_feed`.

If you use the repository `Makefile`, set the project explicitly for that invocation as well:

```bash
TIDINGSIQ_GCP_PROJECT=<GCP_PROJECT_ID> make streamlit
```

## Container Runtime

Build from the repository root:

```bash
docker build -f app/streamlit/Dockerfile -t tidingsiq-streamlit:local .
```

Run locally:

```bash
docker run --rm -p 8501:8080 \
  -e TIDINGSIQ_GCP_PROJECT=<GCP_PROJECT_ID> \
  -e TIDINGSIQ_GOLD_TABLE=<GOLD_TABLE_FQN> \
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
export TIDINGSIQ_GCP_PROJECT=<GCP_PROJECT_ID>
```

Optional override:

```bash
export TIDINGSIQ_GOLD_TABLE=<GOLD_TABLE_FQN>
```

Full local run with an explicit table override:

```bash
export TIDINGSIQ_GCP_PROJECT=<GCP_PROJECT_ID>
export TIDINGSIQ_GOLD_TABLE=<GOLD_TABLE_FQN>
streamlit run app/streamlit/app.py
```

## Query Contract

The app queries only Gold-layer tables and does not reach into Bronze or Silver directly from the UI.

Current serving behavior:

- `The Brief` fetches the current lookback window from Gold's eligible feed, then applies language and geography filters plus presentation sorting locally in the Streamlit layer to keep browsing interactions responsive
- the language and geography controls stay inline with the Brief header as summarized popover triggers so the toolbar remains single-line in the common desktop layout
- `Pulse` reads warehouse-wide Gold aggregates and `gold.pipeline_run_metrics` snapshots, so its charts are intentionally independent from the Brief's inline compact controls
- `Pulse` currently loads through a consolidated dashboard path: one metrics-history query for stage snapshots and trends, plus one Gold-summary query for eligibility counts, exclusion reasons, and score buckets
- article cards render clickable links only when the URL scheme is exactly `http` or `https`; `javascript:`, `data:`, `file:`, `mailto:`, `tel:`, blank, and malformed or no-scheme values are rendered as plain text instead of anchors

Loading behavior:

- a page-level loading screen appears on initial Brief load, Brief filter changes, Brief sort changes, Brief pagination changes, and section switches such as `The Brief -> Pulse`
- the loading screen is presentation-only; it does not change the underlying Gold contract or Pulse chart definitions

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

UI note:

- the app does not mutate the warehouse `url` field
- link safety is enforced at render time in the Streamlit layer
- unsupported or unsafe URL schemes are shown as non-clickable text so the browser never receives them as `href` values

## Future Operations Horizon

The app hosting path is intentionally separate from the scheduled pipeline path:

- pipeline automation: Cloud Scheduler -> Cloud Run Job -> Bruin -> BigQuery
- app hosting: Cloud Run service -> Streamlit -> BigQuery Gold
