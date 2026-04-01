# Happy Factor Definition v1

## Purpose

The Happy Factor is the core application score used by TidingsIQ to rank and filter global news for positive sentiment.

Its purpose is not to provide a perfect emotional truth about an article. Instead, it acts as a practical, explainable, and tunable positivity-oriented score derived from GDELT signals.

The Streamlit application will allow users to set a minimum Happy Factor threshold and view only records that meet or exceed that value.

---

## Design Goals

The Happy Factor should be:

- simple enough to explain
- grounded in available GDELT fields
- cheap to compute in BigQuery
- stable enough for filtering and ranking
- flexible enough to improve later without breaking the app model

---

## Initial Inputs

The Happy Factor will be derived from available GDELT article-level signals, subject to final field validation during implementation.

### Candidate Inputs

| Input | Description | Expected Role |
|---|---|---|
| tone_score | Overall tone-related score from GDELT | Primary positivity or negativity indicator |
| positive_signal_score | Derived score from positive emotional indicators in GCAM-related fields | Reinforces positive content |
| negative_signal_score | Derived score from negative emotional indicators if retained | Used as downward adjustment |
| source_quality_weight | Optional future weighting by source reliability or relevance | Not in v1 |
| duplicate_penalty | Optional adjustment for duplicate-like records | Not in v1 core formula |

---

## Initial Scoring Philosophy

The first version of the Happy Factor should use a transparent formula that combines:

1. normalized tone
2. positive emotional signals
3. optional negative offset if required

The score should then be normalized into a user-friendly range.

Recommended target range for v1:

- **0 to 100**
- higher score means more positive or uplifting news
- the UI slider should filter on this scale

---

## Proposed v1 Formula

### Conceptual Formula

Happy Factor is a weighted score based on normalized tone and positive signal strength.

### Example Placeholder Formula

```sql
happy_factor =
  (0.7 * normalized_tone_score) +
  (0.3 * normalized_positive_signal_score)
````

Then map the result into a 0 to 100 scale.

### Optional Extended Formula

If negative signals are retained:

```sql
happy_factor =
  (0.6 * normalized_tone_score) +
  (0.3 * normalized_positive_signal_score) -
  (0.1 * normalized_negative_signal_score)
```

---

## Normalization Strategy

Because raw upstream values may not be directly suitable for filtering, each input should be normalized before combination.

### Example Approach

* map each input into a 0 to 1 scale
* compute weighted score
* multiply by 100
* round to a practical precision for display and filtering

### Example Output Interpretation

| Happy Factor Range | Interpretation                      |
| ------------------ | ----------------------------------- |
| 0 to 20            | strongly negative or low positivity |
| 21 to 40           | weak positivity                     |
| 41 to 60           | mixed or moderate positivity        |
| 61 to 80           | clearly positive                    |
| 81 to 100          | strongly positive or uplifting      |

---

## v1 Constraints

For the first implementation:

* avoid overly complex sentiment logic
* avoid custom machine learning
* avoid fuzzy heuristics that are hard to explain
* prefer deterministic SQL-friendly transformations

The Happy Factor must remain explainable in a README, demo, and interview setting.

---

## Planned Usage in the App

The Streamlit app will:

* expose a Happy Factor slider
* apply the threshold in a parameterized query against `gold.positive_news_feed`
* optionally sort results by descending Happy Factor

Example user interaction:

* slider set to 70
* app returns only articles with `happy_factor >= 70`

---

## Validation Plan

The Happy Factor should be validated through sample review before being treated as stable.

### Initial validation steps

1. inspect a sample of high-scoring articles
2. inspect a sample of low-scoring articles
3. confirm whether the score aligns with intuitive expectations
4. adjust weights if obviously misleading patterns appear

---

## Open Questions

1. Which exact GDELT fields will be used to derive positive and negative signals?
2. Is tone alone sufficient for v1, with emotional signals added later?
3. Should duplicate-like records affect score or only visibility?
4. Should the app filter only by threshold, or also rank by score?
5. What default slider value should be used in the first app version?

---

## Current v1 Recommendation

Use a simple weighted score based on:

* normalized tone score
* one derived positive signal score

Keep the formula transparent and easy to revise after reviewing real sample outputs.