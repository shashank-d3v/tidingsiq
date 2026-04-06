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
- `source_name` from `SourceCommonName`
- `document_identifier` from `DocumentIdentifier`
- `source_url` from `DocumentIdentifier` when `SourceCollectionIdentifier = 1`
- `title` from `Extras` via `<PAGE_TITLE>`
- `tone_raw` from `V2Tone`
- `language` from `TranslationInfo` when a source-language code is present

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

Latest verified warehouse state after a successful manual Cloud Run execution on `2026-04-06`:

- Bronze rows: `4426`
- Silver rows: `4426`
- Silver canonical rows: `4337`
- Gold rows under the current no-language-gate contract: `4323`
- Bronze rows with populated `source_name`: `4426`
- Bronze rows with populated `source_url`: `4426`
- Bronze rows with populated `title`: `4412`
- Bronze rows with populated `tone_raw`: `4426`
- Bronze rows with populated `TranslationInfo`: `0`
- Bronze rows with populated `language`: `0`
- Silver rows with populated `source_domain`: `4426`
- Silver rows with populated `normalized_url`: `4426`
- Silver rows with populated `language`: `0`
- Silver rows with populated `source_country`: `0`

Historical contrast from the old English-only Gold contract:

- Gold rows under the old English-only contract: `0`

## Conclusions

- The current `language` gap is not explained by an obvious parser bug.
- The current landed GKG rows do not provide usable `TranslationInfo` values in the tested sample.
- `source_domain` is not a blocker; it is already fully derivable in Silver from the canonical URL.
- `source_country` is not a direct source field in the current Bronze path.
- If `source_country` is added later, it should mean article-mentioned country derived from `V2Locations`, not publisher country inferred from a domain.
- The GDELT transport path should default to the documented HTTP feed rather than forcing HTTPS with an SSL override.
- The deployed Cloud Run pipeline path is now proven end to end; the remaining weakness is source-field completeness, not orchestration.

## Implication For Downstream Modeling

- `language` should remain internal and nullable in Bronze and Silver until a defensible source-backed extraction rule is validated.
- `language` should not be part of the Gold serving contract in the current project state.
- Gold should serve scored canonical rows without a language gate.
