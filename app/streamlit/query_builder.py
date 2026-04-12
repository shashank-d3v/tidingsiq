from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from datetime import datetime
import re
from urllib.parse import urlsplit, urlunsplit

OPTIONAL_STRING_COLUMNS = {
    "language",
    "language_resolution_status",
    "mentioned_country_code",
    "mentioned_country_name",
    "mentioned_country_resolution_status",
}

EXPLORATORY_TITLE_DENY_PATTERN = re.compile(
    (
        r"\b("
        r"kill(?:er|ed|ing)?|murder(?:ed|ing)?|manslaughter|"
        r"shoot(?:ing|ings|er|ers)?|shot|stabb(?:ed|ing)?|"
        r"rape|suicide|bomb(?:ing)?|throat|meth|"
        r"foot chase|charges? pile up|accused of serious crimes"
        r")\b"
    ),
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FeedQueryConfig:
    table_fqn: str
    min_happy_factor: float = 65.0
    lookback_days: int = 7
    row_limit: int = 25
    eligible_only: bool = True


@dataclass(frozen=True)
class VisibleFeedState:
    recommended_rows: list[dict[str, object]]
    more_to_explore_rows: list[dict[str, object]]
    visible_rows: list[dict[str, object]]
    summary: dict[str, float | int]
    more_to_explore_empty_reason: str | None


def _clamp_float(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _clamp_int(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def build_feed_query(
    config: FeedQueryConfig,
    *,
    available_columns: set[str] | None = None,
) -> tuple[str, list[tuple[str, str, object]]]:
    threshold = _clamp_float(config.min_happy_factor, 0.0, 100.0)
    lookback_days = _clamp_int(config.lookback_days, 1, 30)
    row_limit = _clamp_int(config.row_limit, 1, 200)
    eligible_only = bool(config.eligible_only)

    select_columns = _build_select_columns(available_columns)

    if eligible_only:
        sql = f"""
select
{select_columns}
from `{config.table_fqn}`
where happy_factor >= @min_happy_factor
  and serving_date >= date_sub(current_date("UTC"), interval @lookback_days day)
  and is_positive_feed_eligible = true
"""
        parameters: list[tuple[str, str, object]] = [
            ("min_happy_factor", "FLOAT64", threshold),
            ("lookback_days", "INT64", lookback_days),
            ("row_limit", "INT64", row_limit),
        ]
    else:
        sql = f"""
with recommended as (
  select
{select_columns}
  from `{config.table_fqn}`
  where serving_date >= date_sub(current_date("UTC"), interval @lookback_days day)
    and is_positive_feed_eligible = true
  order by happy_factor asc, coalesce(published_at, ingested_at) desc, article_id desc
  limit @row_limit
),
more_to_explore as (
  select
{select_columns}
  from `{config.table_fqn}`
  where serving_date >= date_sub(current_date("UTC"), interval @lookback_days day)
    and exclusion_reason = 'below_threshold'
  order by happy_factor asc, coalesce(published_at, ingested_at) desc, article_id desc
  limit @row_limit
)
select
  *
from recommended
union all
select
  *
from more_to_explore
"""
        parameters = [
            ("lookback_days", "INT64", lookback_days),
            ("row_limit", "INT64", row_limit),
        ]

    if eligible_only:
        sql += """
order by happy_factor asc, coalesce(published_at, ingested_at) desc, article_id desc
limit @row_limit
"""

    return sql.strip(), parameters


def _build_select_columns(available_columns: set[str] | None) -> str:
    ordered_columns = [
        "source_record_id",
        "article_id",
        "serving_date",
        "published_at",
        "source_name",
        "language",
        "language_resolution_status",
        "mentioned_country_code",
        "mentioned_country_name",
        "mentioned_country_resolution_status",
        "title",
        "url",
        "tone_score",
        "base_happy_factor",
        "happy_factor",
        "happy_factor_version",
        "is_positive_feed_eligible",
        "positive_guardrail_version",
        "exclusion_reason",
        "allow_hit_count",
        "soft_deny_hit_count",
        "hard_deny_hit_count",
        "ingested_at",
    ]
    lines = []
    for column in ordered_columns:
        if available_columns is None or column in available_columns:
            lines.append(f"  {column}")
        elif column in OPTIONAL_STRING_COLUMNS:
            lines.append(f"  cast(null as string) as {column}")
        else:
            lines.append(f"  {column}")
    return ",\n".join(lines)


def summarize_feed(rows: list[dict[str, object]]) -> dict[str, float | int]:
    if not rows:
        return {
            "row_count": 0,
            "avg_happy_factor": 0.0,
            "max_happy_factor": 0.0,
            "source_count": 0,
        }

    happy_factors = [
        float(row["happy_factor"])
        for row in rows
        if row.get("happy_factor") is not None
    ]
    source_names = {
        str(row["source_name"]).strip()
        for row in rows
        if row.get("source_name")
    }

    return {
        "row_count": len(rows),
        "avg_happy_factor": round(sum(happy_factors) / len(happy_factors), 2)
        if happy_factors
        else 0.0,
        "max_happy_factor": round(max(happy_factors), 2) if happy_factors else 0.0,
        "source_count": len(source_names),
    }


def split_feed_rows(
    rows: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    rows = dedupe_story_rows(rows)
    recommended = sort_feed_rows([
        row for row in rows if bool(row.get("is_positive_feed_eligible")) is True
    ])
    more_to_explore = sort_feed_rows([
        row for row in rows if row.get("exclusion_reason") == "below_threshold"
    ])
    return recommended, more_to_explore


def filter_exploratory_rows(
    rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    safe_rows: list[dict[str, object]] = []
    score_floor = 35.0

    for row in rows:
        happy_factor = _coerce_float(row.get("happy_factor"))
        tone_score = _coerce_float(row.get("tone_score"))
        hard_deny_hits = int(row.get("hard_deny_hit_count") or 0)
        title = str(row.get("title") or "")

        if happy_factor is None or happy_factor < score_floor:
            continue
        if tone_score is None or tone_score < 0.0:
            continue
        if hard_deny_hits > 0:
            continue
        if EXPLORATORY_TITLE_DENY_PATTERN.search(title):
            continue

        safe_rows.append(row)

    return sort_feed_rows(safe_rows)


def filter_rows_by_min_happy_factor(
    rows: list[dict[str, object]],
    *,
    min_happy_factor: float,
) -> list[dict[str, object]]:
    threshold = float(min_happy_factor)
    return [
        row
        for row in rows
        if row.get("happy_factor") is not None
        and float(row["happy_factor"]) >= threshold
    ]


def build_visible_feed_state(
    rows: list[dict[str, object]],
    *,
    min_happy_factor: float,
    feed_sort_order: str,
) -> VisibleFeedState:
    recommended_candidates, more_to_explore_candidates = split_feed_rows(rows)
    safe_more_to_explore_rows = filter_exploratory_rows(more_to_explore_candidates)
    recommended_rows = filter_rows_by_min_happy_factor(
        recommended_candidates,
        min_happy_factor=min_happy_factor,
    )
    more_to_explore_rows = filter_rows_by_min_happy_factor(
        safe_more_to_explore_rows,
        min_happy_factor=min_happy_factor,
    )

    if feed_sort_order == "Most optimistic first":
        recommended_rows = list(reversed(recommended_rows))
        more_to_explore_rows = list(reversed(more_to_explore_rows))

    visible_rows = recommended_rows + more_to_explore_rows
    more_to_explore_empty_reason = _resolve_more_to_explore_empty_reason(
        candidate_rows=more_to_explore_candidates,
        safe_rows=safe_more_to_explore_rows,
        visible_rows=more_to_explore_rows,
        min_happy_factor=min_happy_factor,
    )

    return VisibleFeedState(
        recommended_rows=recommended_rows,
        more_to_explore_rows=more_to_explore_rows,
        visible_rows=visible_rows,
        summary=summarize_feed(visible_rows),
        more_to_explore_empty_reason=more_to_explore_empty_reason,
    )


def sort_feed_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(
        rows,
        key=lambda row: (
            _coerce_float(row.get("happy_factor"))
            if row.get("happy_factor") is not None
            else float("inf"),
            -_coerce_timestamp_order(row.get("published_at") or row.get("ingested_at")),
            str(row.get("article_id") or ""),
        ),
    )


def dedupe_story_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    deduped: list[dict[str, object]] = []
    seen_keys: set[tuple[str, str]] = set()

    for row in rows:
        key = _story_dedupe_key(row)
        if not key[1]:
            deduped.append(row)
            continue
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(row)

    return deduped


def _story_dedupe_key(row: dict[str, object]) -> tuple[str, str]:
    normalized_title = _normalize_story_title(row.get("title"))
    if normalized_title:
        return ("title", normalized_title)

    normalized_url = _normalize_story_url(row.get("url"))
    if normalized_url:
        return ("url", normalized_url)

    source_name = str(row.get("source_name") or "").strip().lower()
    article_id = str(row.get("article_id") or "").strip().lower()
    return ("fallback", f"{source_name}:{article_id}")


def _normalize_story_title(value: object) -> str:
    title = str(value or "").strip().lower()
    if not title:
        return ""

    title = re.sub(r"\s+\|\s+[^|]+$", "", title)
    title = re.sub(r"\b\d{4,}\b", " ", title)
    title = re.sub(r"[^\w\s]", " ", title)
    title = re.sub(r"\s+", " ", title)
    return title.strip()


def _normalize_story_url(value: object) -> str:
    raw_url = str(value or "").strip().lower()
    if not raw_url:
        return ""

    parts = urlsplit(raw_url)
    normalized_path = re.sub(r"/+$", "", parts.path or "")
    normalized = urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            normalized_path,
            "",
            "",
        )
    )
    return normalized.strip()


def build_timeline_data(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}

    for row in rows:
        label = _coerce_serving_date_label(row.get("serving_date"))
        if label is None:
            continue
        current = grouped.setdefault(
            label,
            {
                "serving_date": label,
                "story_count": 0,
                "eligible_count": 0,
                "happy_total": 0.0,
                "happy_count": 0,
            },
        )
        current["story_count"] = int(current["story_count"]) + 1
        if bool(row.get("is_positive_feed_eligible")) is True:
            current["eligible_count"] = int(current["eligible_count"]) + 1
        happy_factor = _coerce_float(row.get("happy_factor"))
        if happy_factor is not None:
            current["happy_total"] = float(current["happy_total"]) + happy_factor
            current["happy_count"] = int(current["happy_count"]) + 1

    timeline = []
    for label in sorted(grouped.keys()):
        point = grouped[label]
        happy_count = int(point["happy_count"])
        timeline.append(
            {
                "serving_date": label,
                "story_count": int(point["story_count"]),
                "eligible_count": int(point["eligible_count"]),
                "avg_happy_factor": round(
                    float(point["happy_total"]) / happy_count,
                    2,
                )
                if happy_count
                else 0.0,
            }
        )
    return timeline


def build_source_rankings(
    rows: list[dict[str, object]],
    *,
    limit: int = 8,
) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}

    for row in rows:
        if bool(row.get("is_positive_feed_eligible")) is not True:
            continue
        source_name = str(row.get("source_name") or "Unknown source").strip()
        current = grouped.setdefault(
            source_name,
            {
                "source_name": source_name,
                "story_count": 0,
                "happy_total": 0.0,
            },
        )
        current["story_count"] = int(current["story_count"]) + 1
        happy_factor = _coerce_float(row.get("happy_factor"))
        if happy_factor is not None:
            current["happy_total"] = float(current["happy_total"]) + happy_factor

    rankings = [
        {
            "source_name": source_name,
            "story_count": int(values["story_count"]),
            "avg_happy_factor": round(
                float(values["happy_total"]) / int(values["story_count"]),
                2,
            )
            if int(values["story_count"])
            else 0.0,
        }
        for source_name, values in grouped.items()
    ]
    rankings.sort(
        key=lambda row: (
            -int(row["story_count"]),
            -float(row["avg_happy_factor"]),
            str(row["source_name"]),
        )
    )
    return rankings[:limit]


def build_score_distribution(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    buckets = [
        ("Below 65", None, 65.0),
        ("65-70", 65.0, 70.0),
        ("70-75", 70.0, 75.0),
        ("75-80", 75.0, 80.0),
        ("80-85", 80.0, 85.0),
        ("85+", 85.0, None),
    ]
    counts = {label: 0 for label, _, _ in buckets}

    for row in rows:
        happy_factor = _coerce_float(row.get("happy_factor"))
        if happy_factor is None:
            continue
        for label, low, high in buckets:
            if low is None and happy_factor < float(high):
                counts[label] += 1
                break
            if high is None and happy_factor >= float(low):
                counts[label] += 1
                break
            if low is not None and high is not None and low <= happy_factor < high:
                counts[label] += 1
                break

    return [{"bucket": label, "story_count": counts[label]} for label, _, _ in buckets]


def build_eligibility_breakdown(
    rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    labels = {
        "eligible": "Eligible",
        "below_threshold": "Below Threshold",
        "hard_deny_term": "Hard Deny Term",
        "soft_deny_without_exception": "Soft Deny Without Exception",
        "missing_title": "Missing Title",
        "missing_url": "Missing URL",
    }
    counts = {key: 0 for key in labels}

    for row in rows:
        if bool(row.get("is_positive_feed_eligible")) is True:
            counts["eligible"] += 1
            continue
        reason = str(row.get("exclusion_reason") or "")
        if reason in counts:
            counts[reason] += 1

    return [{"bucket": labels[key], "story_count": counts[key]} for key in labels]


def _resolve_more_to_explore_empty_reason(
    *,
    candidate_rows: list[dict[str, object]],
    safe_rows: list[dict[str, object]],
    visible_rows: list[dict[str, object]],
    min_happy_factor: float,
) -> str | None:
    if visible_rows:
        return None
    if not candidate_rows:
        return "No below-threshold stories matched the current filters."
    if not safe_rows:
        return "Below-threshold stories matched the current filters, but the safety screen removed them."

    threshold_label = int(min_happy_factor) if float(min_happy_factor).is_integer() else round(float(min_happy_factor), 1)
    return (
        "Below-threshold stories matched the current filters, but none met the current "
        f"Min Happy Factor of {threshold_label}."
    )


def paginate_rows(
    rows: list[dict[str, object]],
    *,
    page_number: int,
    page_size: int,
) -> tuple[list[dict[str, object]], int, int, int]:
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    total_rows = len(rows)
    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    current_page = max(1, min(page_number, total_pages))
    start_index = (current_page - 1) * page_size
    end_index = start_index + page_size
    return rows[start_index:end_index], current_page, total_pages, total_rows


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _coerce_serving_date_label(value: object) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and value:
        return value
    return None


def _coerce_timestamp_order(value: object) -> float:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.timestamp()
        return value.astimezone().timestamp()
    return 0.0
