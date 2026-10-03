# TidingsIQ Static Dashboard

The production frontend provides The Brief, Pulse, and Methodology using
HTML/CSS/JavaScript and generated JSON files. Browsing makes no BigQuery calls,
uses no polling/WebSockets, and loads no external fonts or third-party scripts.
nginx serves an allowlisted artifact and a read-only private GCS feed mount.

See the [walkthrough and screenshots](../../README.md#dashboard),
[deployment guide](../../docs/deployment_plan.md), and
[operations runbook](../../docs/operations_runbook.md#public-app-operations).

## Run Locally

Python 3.10+ is sufficient for the local server. A fresh checkout has no feed
files. Download the already public edition with this standard-library script;
it needs no GCP credentials or warehouse access:

```bash
python3 - <<'PY'
import gzip
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

base = 'https://tidingsiq-app-eglccrtc7q-el.a.run.app/data/'
output = Path('app/static/data')
output.mkdir(parents=True, exist_ok=True)
with urlopen(base + 'manifest.json', timeout=60) as response:
    manifest = json.load(response)
for entry in manifest['ranges'].values():
    name = entry['file']
    if not re.fullmatch(r'feed-(7|30)d-[a-f0-9]+\.json', name):
        raise ValueError('Unexpected feed filename')
    request = Request(base + name, headers={'Accept-Encoding': 'gzip'})
    with urlopen(request, timeout=60) as response:
        body = response.read()
        zipped = response.headers.get('Content-Encoding') == 'gzip'
    raw = gzip.decompress(body) if zipped else body
    (output / name).write_bytes(raw)
    (output / (name + '.gz')).write_bytes(body if zipped else gzip.compress(raw, mtime=0))
(output / 'manifest.json').write_text(json.dumps(manifest))
print('Local edition:', manifest['as_of'])
PY
python3 app/static/serve.py
```

Open <http://127.0.0.1:4173>. The server binds only to loopback; `--port 4174`
selects another port. Stop with Ctrl-C. `data/` is Git-ignored. Local files stay
fixed until downloaded/rebuilt again, even when production publishes a newer day.

Alternatively, build from an existing eligible-only export:

```bash
python3 app/static/build_snapshot.py \
  --source <ELIGIBLE_FEED_JSON> --as-of <YYYY-MM-DD>
```

Use the export's real UTC data date and the 11 source fields listed below. Do not use an
unfiltered Bronze/Gold export. The builder itself does not connect to GCP.

## Behavior

Same-origin, page-lifetime events measure loaded pages, engagement and article
clicks. No cookies or persistent visitor IDs are used; browser privacy signals,
automated checks and `?analytics=off` disable collection. See the
[measurement definitions and reporting](../../docs/engagement_rollout_20261002.md).
Legacy `/_stcore/` routes return 410. This rejects legacy sessions but cannot
force an unidentified remote client to stop sending requests.

- Default 7-day file; 30-day file downloads on selection and is reused in memory.
- The 1-day and 3-day views filter the loaded 7-day file. Cutoffs are inclusive
  UTC dates relative to `manifest.as_of`; 7 days includes eight calendar dates.
- Language, mentioned geography, headline/source search, score sorting, and
  ten-card pagination operate on the complete published range.
- Pulse summarizes eligible stories in the current selection, including search
  and filters. It does not expose warehouse-wide metrics or excluded rows.
- Versioned local story matching assigns `story_id` across the full 30-day export.
  Exact informative headlines match across dates/outlets; conservative URL identity
  dated syndication identities, corroborating story slugs, and bounded fuzzy headline
  matching catch additional variants. Generic and
  recurring titles remain separate without matching URL evidence.
- All eligible variants remain in the files. Browser filters run before grouping,
  then the highest-score/newest/ID representative supplies the card and statistics.
  Display sort never changes the representative. Older files without story IDs work.
- Private `_audit/` objects record membership/reasons; they are not public HTTP assets.
  Manifest counts distinguish articles from stories, and publication verifies both.
- Data date is read from the manifest. Production publishes at 06:30 IST daily;
  open pages need a reload to see a new edition. After 36 hours, a stale notice appears.
  A local timer updates the warning while visible; returning to a hidden tab
  rechecks its age. These checks make no network requests.
- Soft amber/sage/green badge bands preserve the numeric Happy Factor. The browser
  title is `TidingsIQ | A little more perspective`.

## Public Payload and Size

Fields: `article_id`, `serving_date`, `published_at`, `source_name`, `language`,
`mentioned_country_name`, `title`, `url`, `tone_score`, `happy_factor`, `ingested_at`, `story_id`.
No full article text, raw source payload, private metrics, or credentials are exported.

Measured after the story-clustering release on **2 October 2026**:

| Range | Eligible articles retained | Story groups without filters | Gzip bytes |
|---|---:|---:|---:|
| 7-day | 6,493 | 4,532 | 1,042,936 |
| 30-day | 17,851 | 13,135 | 2,966,139 |

These supersede the earlier same-day exporter measurements, which discarded
variants before publication. See the [dated release checks](../../docs/durable_story_deduplication.md#live-verification).

These vary daily. Files use content-hashed names; the manifest supplies exact
counts/sizes. Only ten cards render, but the full selected range occupies memory.
The optional 30-day file repeats records already in the default file. Current
layout/functional checks are not a representative mobile performance benchmark.

## Production Artifact

```bash
python3 app/static/build_production.py --output <NEW_FRONTEND_CONTEXT>
docker build --platform linux/amd64 -t tidingsiq-static <NEW_FRONTEND_CONTEXT>
```

The destination must not already exist. The builder copies six public assets
plus Dockerfile/nginx configuration and rejects local labels, paths, and fixture
dates in application text. Tests, docs, helpers, credentials, and local `data/`
are excluded. Unknown routes return 404. Production uses gzip, immutable feed
caching, and a short-lived manifest cache; development responses use `no-cache`.

`Dockerfile.publisher` uses a separate context with **flat** files named
`Dockerfile`, `publish_static_feed.py`, `build_snapshot.py`, and `story_matcher.py`. Its publisher
requires a successful latest pipeline execution containing the metrics audit
timestamp, checks freshness/completeness and uploaded bytes, then rechecks the
execution before switching the manifest atomically. Live feed files have no
automatic age expiry; private audits expire after 45 days. See the [publisher release steps](../../docs/deployment_plan.md#publisher-release).

## Validate

```bash
node --test app/static/tests/feed.test.mjs
python3 -m unittest discover -s app/static/tests -p 'test_*.py'
```

Publisher regression tests live in `scripts/tests/test_publish_static_feed.py`
and require the publisher's Google client dependencies. Tests cover date bounds,
filters, tie breaks, safe rendering, compression, field allowlisting, deterministic
syndication deduplication, artifact isolation, freshness, and publication failure.
Screenshot capture details are in [the screenshot index](../../docs/screenshots/README.md).
