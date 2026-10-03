# Durable story deduplication

Deployed **2 October 2026** in `tidingsiq-dev`, `asia-south1`. At release, the frontend began showing one representative per story after applying the reader's filters. The
publisher canary `tidingsiq-static-publisher-7pcqq` succeeded in **4m5s**. The
06:30 IST daily schedule was enabled at verification. Reload an already-open page
to load a new release and edition.

## Live verification

| Window | Eligible articles retained | Story groups displayed without filters | gzip bytes |
| --- | ---: | ---: | ---: |
| 7 days | 6,493 | 4,532 | 1,042,936 |
| 30 days | 17,851 | 13,135 | 2,966,139 |

These are observed October 2 counts, not fixed limits. The prior publisher's
14,065-row 30-day file had already discarded some variants. The new files retain
all eligible articles, so the raw row counts and download sizes increase while
the number of displayed cards decreases. The six Edmunds articles share one
story ID. HTTP verification confirms both payload hashes, counts, and 404s for
private audits, source scripts, and credential/repository paths.

Frontend at this rollout: `tidingsiq-app-story-v2-20261002`, 100% traffic, image
`asia-south1-docker.pkg.dev/tidingsiq-dev/tidingsiq-app/tidingsiq-static@sha256:9fec4a95d5a49e4b6850617cd95a0c05baa58c60f164b933c5572b235921ce31`.
Publisher image:
`asia-south1-docker.pkg.dev/tidingsiq-dev/tidingsiq-app/static-publisher@sha256:f632b09d692edb470d33a31f3c39115f3ed8b76940c1b8ab192cb6c722a11df9`.
This frontend was subsequently replaced by the [engagement release](engagement_rollout_20261002.md);
the image above identifies this historical rollout, not a current deployment target.
Live browser checks passed for 1/3/7/30-day windows, language/geography filters,
stable representatives under sorting, source-variant search, Pulse, Methodology,
reset, and pagination. The Edmunds screenshot was visually inspected.

## Matching and serving

`app/static/story_matcher.py` owns versioned local matching (`local-v2`). It
normalizes Unicode, HTML entities, case, punctuation, whitespace, and publisher
suffixes evidenced by the source/hostname or a verified alias. For example,
[Y102 identifies itself as KRNY](https://krny.com/contact-us/). Station frequency
formatting and trailing marketing text are removed only with publisher evidence.
URL identity preserves path case, scheme, and identity-bearing query parameters;
known tracking parameters and fragments are removed.

Within a language, informative exact headlines and identical URLs match across
the 30-day edition. The same dated iHeart producer path on different stations
also identifies a syndicated item. Generic titles of two words or fewer,
recurring features, and TV-schedule labels stay separate without URL/producer
identity. Long identical URL slugs that corroborate the headline can match
within 72 hours, with matching numbers and negation.

Fuzzy matches require token Jaccard >=0.72, character-trigram Dice >=0.85, at
least four headline and informative tokens, matching numbers/negation, and a
maximum 72-hour cluster span. Heuristic named-entity checks reject templates
naming different people, places, or companies. Character trigrams use lossless
packed Unicode values to bound memory. Every member must match the fixed anchor;
there are no transitive cluster merges. IDs are deterministic for identical
inputs, not permanent across changing editions.

The builder clusters the complete edition, derives both ranges from the same
assignments, and rejects non-determinism by recomputing with reversed input.
All variants remain in public files with `story_id`. The browser applies date,
language, country, and search filters before choosing the highest-score/newest/ID
representative. Sort order does not change the representative; Pulse counts the
selected representatives. Old editions without story IDs remain compatible.

## Publication safeguards

Publication verifies hashes, compression, sizes, article/story counts, range
membership, cross-range assignments, audit consistency, and matcher version
before writes. Audit membership and match reasons are retained privately under
`_audit/`, outside the nginx HTTP allowlist. At this rollout, feed and audit
objects had a 45-day retention policy. The repository now removes age expiry from
live feeds to preserve the retained edition; private audits still expire after
45 days. Files are uploaded and read back before a generation-guarded manifest
replacement. The revised publisher also verifies the latest pipeline execution
succeeded and contains the metrics audit timestamp, then rechecks it before
manifest replacement. These subsequent safeguards were deployed in the
[October 3 release](release_safeguards_20261003.md); this October 2 record
describes the earlier rollout.

Success logs include input articles, story count, suppression ratio, exact,
fuzzy and syndication matches, largest cluster, and version. A suppression-rate
shift greater than 15 percentage points warns without blocking publication. The
new `TidingsIQ story suppression changed` policy uses the existing notification
channel; the existing publisher-failure policy remains enabled. Configuration
was verified, but email delivery was not induced for this rollout.

## Tests and limitations

36 tests cover confirmed exact copies, Unicode/URL identity, source aliases,
dated syndication, recurring labels, changed numbers, negation, languages,
entity changes, time bounds, fixed anchors, stable range assignments, browser
filtering/sorting, publication failures, and concurrent manifest replacement.

There are three reviewed metadata-pair fixtures, totaling 175 pairs. The original
55-pair development set scores 100% precision/recall; the 72-pair regression set
scores 100% precision and 97.0% recall. The final 48-pair set scores 100% precision
and 95.3% recall after targeted brand/schedule fixes. It initially scored 97.5%
precision and 90.7% recall, so its final result is a regression measurement rather
than untouched blind validation. Labels are headline-level judgments, not
article-body ground truth, and do not establish universal matching accuracy.

```sh
python3 -m unittest discover -s app/static/tests -p 'test_*.py'
node --test app/static/tests/feed.test.mjs
.venv/bin/python -m unittest discover -s scripts/tests -p 'test_publish_static_feed.py'
python3 app/static/evaluate_story_matching.py --fixture app/static/tests/fixtures/story_pairs_validation.json
```

A strict 512 MiB container benchmark processed the full current export in about
100 seconds at 355 MiB peak RSS, including Google client imports and artifact
validation. The real canary completed within five minutes. The bounded read-only
export billed 39,845,888 bytes; the canary feed query used cache and billed zero.

Headline-only rules can miss larger rewrites, missing timestamps, non-space-
delimited language segmentation, or variants outside the fuzzy window. Cross-
language semantic matching and article-body analysis remain outside this release.
All warehouse source records remain intact for later analysis or reprocessing.

Release measurements are dated observations. For subsequent publications, verify
job success, manifest freshness, referenced hashes and browser behavior using the
[operations runbook](operations_runbook.md#static-publisher-and-stale-feed).

## Rollback

The previous frontend digest is
`sha256:416984f952ca74293d3e553220cd0f126a26af36b11ad99427695d582e94ad96`;
the previous publisher digest is
`sha256:87fc95b373274b109684e232c14b67995b26b0aa45768cb8779e724e5f69a888`.
Complete image names/configuration are saved in `service-before.json` and
`publisher-before.json` in the evidence directory. The previous public manifest
is `manifest-before.json`.

Restore the previous publisher image before restoring its edition. Confirm every
referenced old raw/gzip object exists and matches its hash, then write the saved
manifest with the current object's `ifGenerationMatch` precondition. Stop on a
precondition failure and inspect the winning edition; do not overwrite it blindly.
Keep the new frontend during edition recovery because it supports both schemas.
If the frontend itself fails, route to `tidingsiq-app-static-20260930` only after
confirming the old manifest is restored, since the old frontend does not group
new all-variant files. Reflect rolled-back images in local Terraform inputs and
reconcile state. Never delete or rebuild warehouse tables for this serving fix.
