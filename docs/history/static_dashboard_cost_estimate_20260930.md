# Forward monthly cost estimate and duplicate-story fix

> Historical record: observations and estimates are dated, not current operating instructions. See the [documentation map](../README.md) for maintained guides.

Estimate prepared 30 September 2026 for the deployed TidingsIQ project. These are
planning ranges for a future full month, not an invoice or the current amount due.

## September 30 duplicate fix (superseded)

The pictured headline appeared 28 times with distinct article IDs and URLs,
primarily on iHeart station subdomains. The previous exporter only checked ID
uniqueness, so URL-level deduplication did not prevent syndicated headlines.

At this release, the publisher normalized Unicode, apostrophes, capitalization, and whitespace,
and keeps one representative per matching headline, language, and serving date.
Long headlines (at least 40 characters and six words) match across publishers;
short generic headlines additionally require the same source. Different days and
languages remain separate. No fuzzy topic matching or warehouse row deletion is
performed. Representative selection is deterministic by score, timestamp, and ID.
This reduces exact repetition, but is not semantic deduplication of rewritten news.

| Published range | Before | After | Compressed bytes after |
| --- | ---: | ---: | ---: |
| 7-day | 6,043 | 4,716 | 705,038 |
| 30-day | 17,103 | 13,614 | 2,024,326 |

Publisher image digest: `sha256:87fc95b373274b109684e232c14b67995b26b0aa45768cb8779e724e5f69a888`.
Execution `tidingsiq-static-publisher-xbrc4` succeeded. Live HTTP checks verified
one copy of the reported headline in each range, row counts and content hashes.
A real-browser check also confirmed one rendered card and one search result for
that headline; the corrected card screenshot was inspected.
Six snapshot/artifact tests and four publisher tests passed. The frontend image
and its public asset allowlist were unchanged; future daily publications use this
fix. At verification, the daily 06:30 IST schedule was enabled. Reload an open page
to load the new edition (manifest/mount caches can briefly delay visibility).

This exporter was superseded by the [October 2 story release](../durable_story_deduplication.md),
which retains all variants and groups after browser filters. The payload and
runtime assumptions below therefore do not describe that later release.

## Planning estimate

| Fresh visits per month | Static website and publisher | Entire TidingsIQ project |
| --- | ---: | ---: |
| 1,000 | INR 25–70 | INR 100–250 |
| 10,000 | INR 150–300 | INR 250–500 |
| 100,000 | INR 1,300–2,200 | INR 1,500–2,500 |

Both columns are before taxes. The project column includes the website; do not
add the columns. Ranges include an allowance for modest storage growth, Cloud
Storage operations and startup/runtime variation. For light use, INR 250/month
before taxes is a reasonable planning budget, not an enforced spend limit.

Assumptions:

- Thirty days, current schedules and bounded pipeline unchanged; no backfills,
  bulk rebuilds, sustained bot traffic, or expensive new queries.
- Mostly India/ordinary Asia destinations; 20% of visits also load the 30-day
  range. Each visit downloads fresh data; reuse of browser cache can lower costs.
- One initial 705,038-byte feed plus a 20% share of the 2,024,326-byte optional
  feed and a 30 KB allowance for shell/assets: about 1.14 MB per fresh visit.
- At a planning network rate of USD 0.12/GiB, this gives about 1.06 / 10.62 /
  106.16 GiB and INR 11 / 115 / 1,147 transfer cost for the three scenarios.
  No internet transfer free allowance is assumed for Mumbai traffic.
- INR conversions use **INR 90/USD as a budgeting assumption**, not a verified
  Google invoice exchange rate. Google bills using its applicable local SKUs.
- Normal monthly BigQuery/Cloud Run free allowances remain available to this
  billing account. Other projects share those allowances. If consumed elsewhere,
  allow roughly INR 200–400 extra at light traffic under this same workload.
- Website request-based billing, no warm minimum instances, maximum two; no
  polling, WebSockets, or BigQuery queries caused by visitor interaction. Slow
  clients and heavy traffic can still increase billable request time.

## Live measurements behind the baseline

- Latest pipeline execution: 160.3 seconds, 1 vCPU / 4 GiB; recent corrected runs
  approximately 160–170 seconds, once per scheduled day.
- Report: 24.3 seconds; archive: 28.3–44.1 seconds twice daily; initial successful
  publisher: 20.3 seconds. Jobs have a one-minute minimum billing duration, so
  estimates use at least 60 seconds for each short execution.
- Sep 30 pipeline query billed-byte metadata: 6,485,442,560 bytes across 145
  queries. At the current daily rate this is approximately 181 GiB/month;
  allow roughly 0.2–0.5 TiB/month including archive/report/publisher variation.
  This is below the 1 TiB monthly query allowance if it remains available.
- Three warehouse datasets total approximately 15.77 GiB logical table bytes.
  The region-wide storage view was unavailable to this identity; the estimate
  uses dataset `__TABLES__` metadata, not a billing-export reconciliation.
  Snapshots, retention and storage billing-model details may differ from this sum.
- Archive objects including versions: 7.35 GiB. Feed storage begins at 15 MB;
  daily generations and retention can bring it to approximately 0.6–0.7 GB at
  current sizes. Deleted-version/soft-delete overhead is covered only by the
  planning allowance, not a separately measured billable-byte calculation.
- Artifact Registry repositories: approximately 3.83 GB total (3.56 GiB).
  Four Scheduler jobs exist; three can be free at the billing-account level.

Indicative non-visitor baseline: warehouse storage INR 10–35, archive/feed storage
INR 15–35, container storage INR 28–40, Scheduler approximately INR 9 if three
free jobs are available, plus an operations/runtime allowance. Compute/query
charges should be small with the assumed free allowances. Logging is assumed to
remain within its standard included allowance; billing exports and other projects
were not audited here. This estimate is not a reconciliation of account charges.

## Official pricing sources checked

- [Cloud Run](https://cloud.google.com/run/pricing): request-based compute,
  account-wide free allowances and one-minute minimum for jobs.
- [Cloud Run regions](https://docs.cloud.google.com/run/docs/locations): Mumbai
  is in Tier 1.
- [Network](https://cloud.google.com/vpc/network-pricing): Premium internet
  transfer varies by destination.
- [BigQuery](https://cloud.google.com/bigquery): 1 TiB on-demand query and
  10 GiB storage allowances; separate storage/compute billing.
- [Cloud Storage](https://cloud.google.com/storage/pricing): storage, operations,
  and retained versions are charged separately.
- [Artifact Registry](https://cloud.google.com/artifact-registry/pricing):
  storage above its shared free allowance.
- [Scheduler](https://cloud.google.com/scheduler/pricing): USD 0.10/job/month,
  first three jobs free per billing account.

Raw measurements and deployment evidence are Git-ignored in
`logs/runs/20260930-dedup-cost/`.
