# GDELT Findings

## Current Bronze Source

TidingsIQ currently ingests raw GDELT GKG 2.1 15-minute export files from the `gdeltv2` feed.

The verified row layout is:

1. `GKGRECORDID`
2. `DATE`
3. `SourceCollectionIdentifier`
4. `SourceCommonName`
5. `DocumentIdentifier`
6. `Counts`
7. `V2Counts`
8. `Themes`
9. `V2Themes`
10. `Locations`
11. `V2Locations`
12. `Persons`
13. `V2Persons`
14. `Organizations`
15. `V2Organizations`
16. `V2Tone`
17. `Dates`
18. `GCAM`
19. `SharingImage`
20. `RelatedImages`
21. `SocialImageEmbeds`
22. `SocialVideoEmbeds`
23. `Quotations`
24. `AllNames`
25. `Amounts`
26. `TranslationInfo`
27. `Extras`

## What Bronze Maps Today

Current Bronze extraction maps:

- `source_record_id` from `GKGRECORDID`
- `published_at` from `DATE`
- `source_collection_identifier` from `SourceCollectionIdentifier`
- `source_name` from `SourceCommonName`
- `document_identifier` from `DocumentIdentifier`
- `source_url` from `DocumentIdentifier` when `SourceCollectionIdentifier = 1`
- `source_domain` from the resolved article URL, with `source_name` fallback
- `title` from `Extras` via `<PAGE_TITLE>`
- `tone_raw` from `V2Tone`
- `language_raw` from `TranslationInfo` when a source-language code is present
- `language` from native `TranslationInfo` when present, otherwise deterministic title-based inference
- `mentioned_country_code` and `mentioned_country_name` from `V2Locations` when article geography is present

The Bronze `raw_payload` now retains the additional upstream fields most relevant to future refinement:

- `V2Counts`
- `V2Themes`
- `V2Locations`
- `V2Persons`
- `V2Organizations`
- `GCAM`
- `AllNames`
- `Amounts`
- `TranslationInfo`
- `Extras`

## Verified Findings

Latest verified warehouse state after the enrichment migration run on `2026-04-06`:

- Bronze rows: `644`
- Silver rows: `644`
- Silver canonical rows: `628`
- Gold rows under the current no-language-gate contract: `626`
- Bronze rows with populated `source_name`: `644`
- Bronze rows with populated `source_url`: `644`
- Bronze rows with populated `source_domain`: `644`
- Bronze rows with populated `title`: `643`
- Bronze rows with populated `tone_raw`: `644`
- Bronze rows with populated `TranslationInfo`: `0`
- Bronze rows with populated native `language_raw`: `0`
- Bronze rows with populated resolved `language`: `644`
- Bronze rows with populated `mentioned_country_code`: `644`
- Silver rows with populated `source_domain`: `644`
- Silver rows with populated `normalized_url`: `644`
- Silver rows with populated `language`: `644`
- Silver rows with populated `mentioned_country_code`: `644`

Resolution mix in the latest Bronze window:

- `language_resolution_status = inferred`: `391`
- `language_resolution_status = undetermined`: `253`
- `mentioned_country_resolution_status = v2_locations`: `384`
- `mentioned_country_resolution_status = undetermined`: `260`

Historical contrast from the old English-only Gold contract:

- Gold rows under the old English-only contract: `0`

## Conclusions

- The current `language` gap is not explained by an obvious parser bug.
- The current landed GKG rows do not provide usable `TranslationInfo` values in the tested sample.
- `source_domain` is not a blocker; it is already fully derivable in Silver from the canonical URL.
- article geography is available from `V2Locations` for a substantial subset of landed rows and is the right source-backed path for country enrichment
- publisher country is still not a direct source field in the current Bronze path and should not be inferred from domains in this contract
- The GDELT transport path should default to the documented HTTP feed rather than forcing HTTPS with an SSL override.
- The deployed Cloud Run pipeline path is now proven end to end; the remaining weakness is source-field completeness, not orchestration.
- the Bronze and Silver contracts can now avoid blank language and country fields by using explicit sentinel values plus resolution-status columns

## Implication For Downstream Modeling

- `language` should use native `TranslationInfo` first and deterministic inference second, while preserving explicit provenance
- Gold can expose `language` plus resolution metadata as informational fields, but they should not act as serving gates in the current project state
- Gold can expose `mentioned_country` as article geography metadata, but it should not be presented as publisher country
- Gold should serve scored canonical rows without a language gate.
