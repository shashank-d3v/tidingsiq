# Static dashboard payload measurement — September 29, 2026

> Historical record: observations and estimates are dated, not current operating instructions. See the [documentation map](../README.md) for maintained guides.

## Conclusion

A static public feed is feasible at the measured size. The default 7-day view
contains 4,954 eligible articles: 548 KB with Brotli or 642 KB with gzip.
The 30-day view contains 15,713 articles: 1.750 MB with Brotli or 2.085 MB with
gzip. Downloading all 53,654 eligible articles would require 6.023 MB with
Brotli and should not be the default initial load.

This is a data-payload measurement, not a browser speed benchmark or a completed
frontend. No dashboard, infrastructure, schedule, or production table was changed.

## Scope and method

- Read the live `tidingsiq-dev.gold.positive_news_feed` once, selecting only
  `is_positive_feed_eligible = TRUE` and the current Brief's 11 serving fields:
  article_id, serving_date, published_at, source_name, language,
  mentioned_country_name, title, url, tone_score, happy_factor, ingested_at.
- Measured 53,654 distinct article IDs; serving dates July 1–September 29.
  BigQuery's output-stage row count also confirms 53,654, so the CLI's 100,000-row
  limit did not truncate the data.
- Matched the application's UTC date predicate exactly:
  `serving_date >= DATE_SUB(as_of_date, INTERVAL n DAY)`. As of September 29,
  the “7-day” option therefore includes September 22–29 (eight calendar dates);
  the “30-day” option includes August 30–September 29 (31 calendar dates).
  This preserves existing semantics rather than silently changing the ranges.
- Used compact UTF-8 JSON with numeric scores, gzip level 6 and Brotli quality 6.
  Compressed files were decompressed and compared byte-for-byte with their inputs.
- Units below are decimal: 1 KB = 1,000 bytes; 1 MB = 1,000,000 bytes.
- Query processed 116,276,470 bytes and billed 116,391,936 bytes (about 111 MiB).
  These are BigQuery scan statistics, not the browser download size or a rupee charge.

## Complete article payloads

| Current view | Articles | Uncompressed JSON | gzip | Brotli |
|---|---:|---:|---:|---:|
| 1 day | 1,779 | 916 KB | 217 KB | 190 KB |
| 3 days | 2,510 | 1.285 MB | 316 KB | 273 KB |
| 7 days | 4,954 | 2.522 MB | 642 KB | 548 KB |
| 30 days | 15,713 | 7.966 MB | 2.085 MB | 1.750 MB |
| All eligible dates | 53,654 | 27.327 MB | 7.209 MB | 6.023 MB |

Brotli reduces the complete 7-day and 30-day payloads by about 78% versus compact
uncompressed JSON. A 1.750 MB download still expands into 7.966 MB of JSON before
parsing; the resulting JavaScript objects and any rendering add further memory.
Only the visible page of article cards should be rendered at once.

## Compact filter/sort index

The experimental index uses dictionary-encoded language, geography, and source
names, plus article position, serving date, and Happy Factor. Positions resolve
to article records in the same immutable snapshot and preserve the existing date
and article-ID tie order. This supports the current date/language/geography
filters, both Happy Factor sort directions, and scope summaries. It excludes
headlines and URLs: it is not a full-text search index or a standalone news feed.

| View | Uncompressed index | gzip | Brotli |
|---|---:|---:|---:|
| 1 day | 60 KB | 16 KB | 14 KB |
| 3 days | 86 KB | 23 KB | 21 KB |
| 7 days | 168 KB | 44 KB | 41 KB |
| 30 days | 531 KB | 125 KB | 123 KB |

All 15,713 index positions and dictionary mappings in the 30-day slice were
checked against their original records. A production index would also need a
snapshot/version identifier and file manifest; that small overhead is not included.

## Smaller files and pagination

- The current first 20 articles compress to 2.269 KB with Brotli. This particular
  first page is smaller than typical: across 786 consecutive pages in the 30-day
  feed, the median is 2.997 KB and maximum 3.746 KB (the final page is partial).
- Splitting the 30-day feed into 100-article files produces 158 files, with a
  median of 13.118 KB and maximum of 15.134 KB each, using Brotli.
  Their combined size is 2.009 MB, larger than compressing the feed as one file.
- Per-date files for the 31 covered dates have a median compressed size of
  61.531 KB and maximum of 113.704 KB.

**Filtered results are not necessarily in one small file.** I measured all 39
language/geography pairs having at least 20 matches in the 30-day snapshot.
The first 20 matching results required a median of 13 separate 100-article files
and 173 KB of article data. The largest measured case needed 19 files and 255 KB.
With the 123 KB index, those cold-load totals are approximately 296 KB and 377 KB,
respectively, excluding the website itself and HTTP overhead. This is only the
measured first page in descending score order for those pairs, not a guarantee
for every filter, sort direction, or later page.

A dedicated first-page file can be tiny; arbitrary filtered pages cannot all be
assumed to cost only 2–4 KB. Caching helps subsequent requests, but generating
files for every filter combination would add substantial publishing complexity.

## Suggested next decision

For a first version, consider the simplest static design: load the default 7-day
feed once (548 KB Brotli), filter and paginate it locally, and request the larger
30-day dataset only if selected. Narrower date ranges can use the already loaded
records. Separate range files may repeat downloaded records when switching to
30 days; date-based files could avoid that at the cost of more requests.

If a stricter initial-data budget is needed, the measured 41 KB default index
plus a small first-page file is promising, but the chunk-fetch and caching logic
must handle scattered filter matches. The present data size does not by itself
require a new API. This recommendation is an inference from payload sizes, not a
validated mobile performance result.

Before selecting the design, a later prototype should measure total transferred
bytes, time to usable first page, parsing time, filter responsiveness, and peak
memory on a representative mobile device/network. That work is not part of this
measurement step.

## What is not included

HTML, CSS, JavaScript, fonts, icons, HTTP headers, TLS/latency, browser memory,
Pulse charts/summary payloads, and any future article images are not included.
The current article cards do not render article images. The full current Gold
schema and Bronze raw payloads were deliberately excluded. Serving must actually
negotiate gzip/Brotli with suitable cache headers to achieve these transfer sizes.
Numbers reflect this September 29 snapshot and will change with feed volume.

## Reproduction and evidence

Local, git-ignored evidence is under `logs/runs/20260929-static-sizing/`:
`feed.sql`, `query-job.json`, `feed.json`, `measure.py`, `measurement.json`, and
compact/compressed per-range payloads. The script reconstructs the core size
measurements from the saved read-only export. Supplementary 20-row page statistics
are recorded in `measurement.json`.

Query job: `bqjob_r28c1d0c50411769_000001a0eb549f51_1` in `asia-south1`.
