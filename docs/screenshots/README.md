# Dashboard Screenshots

Captured **2 October 2026** from the real public deployment:
<https://tidingsiq-app-eglccrtc7q-el.a.run.app/>.

The edition was `2026-10-02`, generated at `2026-10-02T01:00:20Z` from Gold data
last ingested at `2026-10-02T00:30:37Z`. The default selection contained 4,834
stories. Screenshots use the 7-day window, all languages/geographies, no search,
and most-optimistic sorting. These are dated examples, not fixed product counts.

| File | View | Capture |
|---|---|---|
| [dashboard-brief-overview-clean.png](dashboard-brief-overview-clean.png) | Brief header, statistics and start of feed | 1440 × 1000 desktop viewport |
| [dashboard-brief-feed-detail.png](dashboard-brief-feed-detail.png) | Filters, search, scores and story cards | 1440 × 1000 desktop viewport, scrolled to feed |
| [dashboard-pulse.png](dashboard-pulse.png) | Selection-based daily/geography/score charts | 1440-wide desktop, full page |
| [dashboard-methodology.png](dashboard-methodology.png) | Scoring, colour bands and date explanations | 1440-wide desktop, full page |
| [dashboard-mobile.png](dashboard-mobile.png) | Responsive Brief, controls and first cards | 390 × 1400 compact tall viewport |

The four existing screenshot filenames were retained and their legacy images
replaced, preserving the README walkthrough layout. The mobile image is new.
Browser-native captures contain no edits to the displayed data or composited UI.
Working originals are under Git-ignored `output/playwright/docs-*.png`.

For a refresh, load the live page, wait for cards/data date, reset filters, and
capture each tab. Check mobile horizontal overflow and inspect every image before
copying it here. Record the new date and manifest values; do not reuse an old
screenshot while calling it current. Layout checks do not substitute for a
representative mobile performance benchmark.
