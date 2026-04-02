# Happy Factor

## Purpose

`happy_factor` is the application score used to filter and sort positive news in TidingsIQ. It is a practical ranking feature, not a claim of objective emotional truth.

The score must be:
- inexpensive to compute in BigQuery
- easy to explain in a portfolio setting
- stable enough for filtering
- versioned so the formula can evolve without breaking the app contract

## Output Contract

- scale: `0` to `100`
- higher values indicate more positive or uplifting article signals
- persisted in `gold.positive_news_feed`
- accompanied by `happy_factor_version`

## Inputs

Planned candidate inputs:

| Input | Status | Purpose |
|---|---|---|
| `tone_score` | Expected in v1 | Primary positivity signal after normalization |
| `positive_signal_score` | Pending GDELT validation | Reinforces explicitly positive emotional content |
| `negative_signal_score` | Pending GDELT validation | Optional downward adjustment |

Important constraint:

The exact upstream GDELT field mappings for positive and negative emotional signals are not yet confirmed. The first implementation must not invent them.

## Implemented v1 Strategy

The current repository implementation uses:

- `happy_factor_version = 'v1_tone_only'`

This is the safest initial release because the tone mapping is validated and the positive and negative signal mappings are still intentionally unresolved.

### Implemented formula

Concept:

```sql
normalized_tone_score = clamp((tone_score + 10) / 20, 0, 1)
happy_factor = 100 * normalized_tone_score
```

The current SQL implementation rounds `happy_factor` to two decimal places for display and filtering stability.

### Why this normalization

The current Bronze and Silver sample shows `tone_score` concentrated near neutral, with observed values roughly between `-16.2` and `14.4`. GDELT's documented API examples also treat values around `5` as fairly positive and `-5` as fairly negative. Using `-10` to `10` as the primary scoring band gives a simple, explainable first release:

- `tone_score <= -10` maps to `0`
- `tone_score = 0` maps to `50`
- `tone_score >= 10` maps to `100`

## Normalization Rules

The formula should only combine normalized inputs. For the current implementation:

- normalize each component to a `0` to `1` range
- clamp out-of-range values before scoring
- multiply the weighted result by `100`
- round to a practical precision for display and filtering

Future versions can replace this normalization only by changing `happy_factor_version`, not by silently redefining `v1_tone_only`.

## UI Usage

The Streamlit app should:
- expose a minimum `happy_factor` threshold
- default to a sensible but not overly restrictive threshold
- sort by descending `happy_factor` unless the user chooses otherwise

The UI should not need to know the internal formula. It should only depend on the persisted score and version.

## Validation Plan

Before treating the score as stable:

1. Review a sample of high-scoring records.
2. Review a sample of low-scoring records.
3. Check whether obviously neutral or negative articles are leaking into high-score results.
4. Adjust normalization or weights only after inspecting real examples.

## Non-Goals

For v1, `happy_factor` should not attempt to:
- summarize article meaning with custom NLP
- infer topic importance
- score source credibility
- remove all false positives

## Future Extension Rule

If validated positive or negative signal mappings are added later, they should ship as a new version such as:

- `happy_factor_version = 'v2_tone_plus_signal'`

The current implementation should remain frozen and explainable for portfolio review.
