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

## Recommended v1 Strategy

Ship the scoring model in two possible stages, depending on what is validated during source integration.

### Option A: `v1_tone_only`

Use this if only the tone mapping is validated reliably.

Concept:

```sql
happy_factor = 100 * normalized_tone_score
```

This is the safest initial release because it keeps the scoring logic fully grounded in confirmed inputs.

### Option B: `v1_tone_plus_signal`

Use this only if positive-signal mappings are validated against real GDELT samples.

Concept:

```sql
happy_factor =
  100 * (
    0.7 * normalized_tone_score +
    0.3 * normalized_positive_signal_score
  )
```

If a reliable negative signal is later retained, it can be introduced in a new version rather than modifying an existing one silently.

## Normalization Rules

The formula should only combine normalized inputs. For v1:

- normalize each component to a `0` to `1` range
- clamp out-of-range values before scoring
- multiply the weighted result by `100`
- round to a practical precision for display and filtering

The exact normalization rule for `tone_score` depends on the raw GDELT value distribution and must be validated during implementation.

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

## Decision Rule

If GDELT emotional-signal mappings are still ambiguous at implementation time, the project should launch with:

- `happy_factor_version = 'v1_tone_only'`

This is preferable to shipping a more complex but weakly justified formula.
