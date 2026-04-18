# Gold Scoring V3 Shadow Rollout

## Added Assets

- `gold.scoring_eval_labels`: empty benchmark-label table for manual review results.
- `gold.url_validation_results`: latest async URL validation result per `normalized_url`.
- `gold.source_quality_snapshot`: trailing 30-day domain-quality snapshot with bounded adjustments.
- `gold.positive_news_feed_v3_shadow`: dual-score shadow table that preserves app-critical fields.

## Scoring Model

- `positivity_score`: tone-normalized base score plus deterministic constructive-language bonus.
- `suitability_score`: `100 - penalties + source adjustment`, clamped to `0-100`.
- `happy_factor`: `0.7 * positivity_score + 0.3 * suitability_score`.
- `is_positive_feed_eligible`: explicit gate based on title presence, URL quality, deny rules, and score thresholds.

Current `v3` defaults intentionally leave upstream GDELT-derived signal adjustments at `0` until they are validated against the labeled benchmark.

## Operational Scripts

- [generate_scoring_eval_sample.py](/Volumes/SWE/repos/DE%202026/tidingsiq/scripts/generate_scoring_eval_sample.py): generates a stratified CSV sample from current Gold for manual review.
- [compare_gold_score_versions.py](/Volumes/SWE/repos/DE%202026/tidingsiq/scripts/compare_gold_score_versions.py): compares current Gold and shadow Gold overlap, changed rows, exclusion mix, domain mix, and labeled precision.

## Validation Notes

- Unit tests cover deterministic score math, URL-status handling, and rollout-script SQL builders.
- URL validation now includes SSRF hardening before request dispatch and before every followed redirect, with blocked targets logged and surfaced as `unavailable`.
- Live validation for this path should combine a manual Cloud Run job execution with warehouse checks on `gold.url_validation_results` and a log search for `Blocked URL target`.
- Full `bruin validate` still depends on live BigQuery access and could not complete in the sandboxed environment used for implementation.

## Known Follow-Ups

- `gold.url_validation_results` currently caps fresh validations per run, but its due-for-recheck lookup still reads the full history table before deciding which candidate URLs to process. That is acceptable for the first bounded rollout, but it is not the intended long-term shape once the table grows.
- When this path is revisited, narrow the lookup to the current candidate `normalized_url` set or move the recheck-due logic into a warehouse-side join/filter so `URL_VALIDATION_MAX_URLS` also bounds the metadata-read cost.
