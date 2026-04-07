# Happy Factor

## Purpose

`happy_factor` is the application ranking score used to surface more positive news in TidingsIQ. It is intentionally practical and explainable, not a claim of objective emotional truth.

The scoring layer now separates:
- ranking score
- feed eligibility

This is the key design change from the earlier tone-only version.

## Output Contract

Persisted in `gold.positive_news_feed`:

- `base_happy_factor`
- `happy_factor`
- `happy_factor_version`
- `is_positive_feed_eligible`
- `positive_guardrail_version`
- `exclusion_reason`

Interpretation:
- `base_happy_factor` is the tone-only score
- `happy_factor` is the final guardrailed score
- `is_positive_feed_eligible` decides whether the row belongs in the default positive feed

## Implemented Versions

### Historical version

- `happy_factor_version = 'v1_tone_only'`

This version used only:

```sql
base_happy_factor = clamp((tone_score + 10) / 20, 0, 1) * 100
```

That version was useful for ranking experiments, but it could still score obviously negative topics too highly if the title wording looked positive enough.

### Current version

- `happy_factor_version = 'v2_1_guardrailed_tone'`
- `positive_guardrail_version = 'v1_1_title_rules'`

The current Gold model keeps the same tone normalization as the base score, then applies title-based guardrails.

## Implemented Formula

### 1. Base score

```sql
base_happy_factor = round(
  100 * clamp((tone_score + 10) / 20, 0, 1),
  2
)
```

Examples:
- `tone_score = 0` => `50`
- `tone_score = 5.88` => `79.4`
- `tone_score = 12.5` => `100`
- `tone_score <= -10` => `0`

### 2. Title guardrails

The current title rules use three classes:
- `allow`
- `deny_soft`
- `deny_hard`

Matching rules:
- token rules use normalized whole-word matching
- phrase rules use normalized substring matching
- `allow` can override `deny_soft`
- `deny_hard` always wins

### 3. Final score

```sql
positive_bonus = least(10, 2 * allow_token_hits + 5 * allow_phrase_hits)
soft_penalty = 12 if soft_deny_hit and not allow_hit else 0
happy_factor = clamp(base_happy_factor + positive_bonus - soft_penalty, 0, 100)
```

### 4. Eligibility rule

```sql
is_positive_feed_eligible = true only when:
- happy_factor >= 65
- hard_deny_hit = false
- not (soft_deny_hit = true and allow_hit = false)
```

This means the score ranks, but eligibility decides whether the article is shown in the default positive feed.

## Why This Is Better

The guardrail layer addresses a real failure mode from the earlier implementation:
- tone-only scoring could let obituary, explosion, probe, or similar titles remain highly ranked

The current model improves that without pretending to solve sentiment with custom NLP.

## Rule Source

The title rules are not buried inside ad hoc SQL constants anymore. They live in:

- `gold.positive_feed_guardrail_terms`

This allows:
- inspectable rule sets
- versioning
- easier future edits without redesigning the scoring model

## UI Usage

The app should default to:
- `is_positive_feed_eligible = true`
- `happy_factor >= 65`

The threshold slider remains useful, but the positive-feed gate is now more than just a score cutoff.

## Validation Expectations

The current scoring layer should satisfy these checks:

1. high-score rows with hard deny terms should not be eligible
2. soft deny titles should be excluded unless an allow term or phrase applies
3. hard deny terms should override allow terms
4. the eligible feed should remain meaningfully non-empty
5. score and eligibility should remain explainable from persisted fields

## Future Direction

Later scoring improvements may add:
- validated GKG signal mappings
- better phrase modeling
- stronger audit and review workflows

Those should ship as new versions, not by silently changing:
- `v2_1_guardrailed_tone`
- `v1_1_title_rules`
