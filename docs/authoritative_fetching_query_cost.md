# Authoritative Fetching With Controlled Query Cost

## Status

Deferred future improvement. Not scheduled for current implementation.

## Intent

Gold should remain the source of truth for which rows match the user's active filters. The app should stop treating a locally filtered subset as if it were the full filtered universe.

This note now applies primarily to `The Brief`. `Pulse` has since been reshaped into a warehouse-wide dashboard backed by Gold operational aggregates rather than the Brief's filtered row scope.

## Planned Direction

- move truth-defining filters into the BigQuery query layer
- keep presentational-only state in the app layer
- replace the current broad lookback fetch with query-per-filter-signature
- use one authoritative filter signature for Brief rows, counts, and filter options
- add server-side pagination instead of paginating a locally cached result set
- cache rows, counts, and filter options with a short TTL
- build language, geography, and date options from Gold scope rather than from the first returned page

## Truth-Defining Filters To Move Into Query Layer

- lookback window
- serving date
- language
- geography

## Presentation-Only State To Keep Local

- current page state
- card layout
- sidebar and expansion state
- page chrome
- minor display ordering only if it does not change dataset membership

## Constraints

- Gold remains the only serving source
- Gold language and geography fields remain informational metadata, not eligibility semantics
- query-time predicates may still be applied to those fields for browsing
- query cost must stay bounded with selective predicates, capped page sizes, and short-lived cache entries
- local dedupe is not part of the first future rollout

## Planned Rollout

### Phase 1

Move Brief row filtering and counts to BigQuery.

### Phase 2

Move filter option generation to authoritative queries.

### Phase 3

Tune cache TTLs and pagination behavior from observed usage.

### Phase 4

Consider helper tables or pre-aggregates only if query cost remains too high.

## Validation Criteria

- displayed rows and count query always agree for the same filter signature
- changing a truth-defining filter changes rows and counts consistently
- filter options do not disappear just because they were absent from the first page

## Assumptions

- this is a future architecture note, not an implementation commitment
- the first pass should preserve current Gold semantics and avoid adding new warehouse tables unless cost forces it
- the current local-first Streamlit behavior remains the active implementation until this design is intentionally scheduled
