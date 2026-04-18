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

BRIEF_SORT_ORDERS = {
    "Most optimistic first",
    "Least optimistic first",
}


@dataclass(frozen=True)
class FeedQueryConfig:
    table_fqn: str
    lookback_days: int = 7
    row_limit: int = 25


@dataclass(frozen=True)
class QueryParameterSpec:
    name: str
    type_name: str
    value: object
    is_array: bool = False


@dataclass(frozen=True)
class BriefScopeQueryConfig:
    table_fqn: str
    lookback_days: int = 7
    selected_languages: tuple[str, ...] = ()
    selected_geographies: tuple[str, ...] = ()


@dataclass(frozen=True)
class BriefRowsQueryConfig:
    table_fqn: str
    lookback_days: int = 7
    selected_languages: tuple[str, ...] = ()
    selected_geographies: tuple[str, ...] = ()
    sort_order: str = "Most optimistic first"
    page_number: int = 1
    page_size: int = 10


@dataclass(frozen=True)
class BriefLanguageOptionsQueryConfig:
    table_fqn: str
    lookback_days: int = 7
    selected_geographies: tuple[str, ...] = ()


@dataclass(frozen=True)
class BriefGeographyOptionsQueryConfig:
    table_fqn: str
    lookback_days: int = 7
    selected_languages: tuple[str, ...] = ()


@dataclass(frozen=True)
class VisibleFeedState:
    recommended_rows: list[dict[str, object]]
    visible_rows: list[dict[str, object]]
    summary: dict[str, float | int]

def _clamp_int(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def build_feed_query(
    config: FeedQueryConfig,
    *,
    available_columns: set[str] | None = None,
) -> tuple[str, list[tuple[str, str, object]]]:
    lookback_days = _clamp_int(config.lookback_days, 1, 30)
    row_limit = _clamp_int(config.row_limit, 1, 200)

    select_columns = _build_select_columns(available_columns)

    sql = f"""
select
{select_columns}
from `{config.table_fqn}`
where serving_date >= date_sub(current_date("UTC"), interval @lookback_days day)
  and is_positive_feed_eligible = true
"""
    parameters: list[tuple[str, str, object]] = [
        ("lookback_days", "INT64", lookback_days),
        ("row_limit", "INT64", row_limit),
    ]

    sql += """
order by happy_factor asc, coalesce(published_at, ingested_at) desc, article_id desc
limit @row_limit
"""

    return sql.strip(), parameters


def build_brief_rows_query(
    config: BriefRowsQueryConfig,
    *,
    available_columns: set[str] | None = None,
) -> tuple[str, list[QueryParameterSpec]]:
    lookback_days = _clamp_int(config.lookback_days, 1, 30)
    page_number = max(1, int(config.page_number))
    page_size = _clamp_int(config.page_size, 1, 200)
    offset_rows = (page_number - 1) * page_size
    sort_order = _normalize_brief_sort_order(config.sort_order)
    selected_languages = _normalize_brief_values(config.selected_languages)
    selected_geographies = _normalize_brief_values(config.selected_geographies)

    select_columns = _build_select_columns(
        available_columns,
        ordered_columns=[
            "article_id",
            "serving_date",
            "published_at",
            "source_name",
            "language",
            "mentioned_country_name",
            "title",
            "url",
            "tone_score",
            "happy_factor",
            "ingested_at",
        ],
    )
    where_sql, parameters = _build_brief_scope_clause(
        lookback_days=lookback_days,
        selected_languages=selected_languages,
        selected_geographies=selected_geographies,
        available_columns=available_columns,
    )

    sql = f"""
select
{select_columns}
from `{config.table_fqn}`
where {where_sql}
order by {_build_brief_order_by(sort_order)}
limit @page_size
offset @offset_rows
"""
    parameters.extend(
        [
            QueryParameterSpec("page_size", "INT64", page_size),
            QueryParameterSpec("offset_rows", "INT64", offset_rows),
        ]
    )
    return sql.strip(), parameters


def build_brief_scope_summary_query(
    config: BriefScopeQueryConfig,
    *,
    available_columns: set[str] | None = None,
) -> tuple[str, list[QueryParameterSpec]]:
    lookback_days = _clamp_int(config.lookback_days, 1, 30)
    selected_languages = _normalize_brief_values(config.selected_languages)
    selected_geographies = _normalize_brief_values(config.selected_geographies)
    where_sql, parameters = _build_brief_scope_clause(
        lookback_days=lookback_days,
        selected_languages=selected_languages,
        selected_geographies=selected_geographies,
        available_columns=available_columns,
    )

    sql = f"""
select
  count(*) as row_count,
  coalesce(round(avg(happy_factor), 2), 0.0) as avg_happy_factor,
  coalesce(round(max(happy_factor), 2), 0.0) as max_happy_factor,
  count(distinct nullif(trim(source_name), '')) as source_count
from `{config.table_fqn}`
where {where_sql}
"""
    return sql.strip(), parameters


def build_brief_language_options_query(
    config: BriefLanguageOptionsQueryConfig,
    *,
    available_columns: set[str] | None = None,
) -> tuple[str, list[QueryParameterSpec]]:
    lookback_days = _clamp_int(config.lookback_days, 1, 30)
    selected_geographies = _normalize_brief_values(config.selected_geographies)
    language_expr = _column_expression("language", available_columns)
    where_sql, parameters = _build_brief_scope_clause(
        lookback_days=lookback_days,
        selected_languages=(),
        selected_geographies=selected_geographies,
        available_columns=available_columns,
    )

    sql = f"""
with scoped_rows as (
  select
    upper(trim({language_expr})) as language
  from `{config.table_fqn}`
  where {where_sql}
)
select distinct
  language
from scoped_rows
where language is not null
  and language != ''
  and language != 'UND'
order by language asc
"""
    return sql.strip(), parameters


def build_brief_geography_options_query(
    config: BriefGeographyOptionsQueryConfig,
    *,
    available_columns: set[str] | None = None,
) -> tuple[str, list[QueryParameterSpec]]:
    lookback_days = _clamp_int(config.lookback_days, 1, 30)
    selected_languages = _normalize_brief_values(config.selected_languages)
    geography_expr = _column_expression("mentioned_country_name", available_columns)
    where_sql, parameters = _build_brief_scope_clause(
        lookback_days=lookback_days,
        selected_languages=selected_languages,
        selected_geographies=(),
        available_columns=available_columns,
    )

    sql = f"""
with scoped_rows as (
  select
    trim({geography_expr}) as geography
  from `{config.table_fqn}`
  where {where_sql}
)
select distinct
  geography
from scoped_rows
where geography is not null
  and geography != ''
  and lower(geography) != 'unknown'
order by geography asc
"""
    return sql.strip(), parameters


def _build_select_columns(
    available_columns: set[str] | None,
    ordered_columns: list[str] | None = None,
) -> str:
    if ordered_columns is None:
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


def _build_brief_scope_clause(
    *,
    lookback_days: int,
    selected_languages: tuple[str, ...],
    selected_geographies: tuple[str, ...],
    available_columns: set[str] | None = None,
) -> tuple[str, list[QueryParameterSpec]]:
    clauses = [
        'serving_date >= date_sub(current_date("UTC"), interval @lookback_days day)',
        "is_positive_feed_eligible = true",
    ]
    parameters = [QueryParameterSpec("lookback_days", "INT64", lookback_days)]

    if selected_languages:
        clauses.append(
            f"upper(trim({_column_expression('language', available_columns)})) in unnest(@selected_languages)"
        )
        parameters.append(
            QueryParameterSpec(
                "selected_languages",
                "STRING",
                selected_languages,
                is_array=True,
            )
        )

    if selected_geographies:
        clauses.append(
            f"trim({_column_expression('mentioned_country_name', available_columns)}) in unnest(@selected_geographies)"
        )
        parameters.append(
            QueryParameterSpec(
                "selected_geographies",
                "STRING",
                selected_geographies,
                is_array=True,
            )
        )

    return "\n  and ".join(clauses), parameters


def _column_expression(
    column: str,
    available_columns: set[str] | None,
) -> str:
    if available_columns is None or column in available_columns:
        return column
    if column in OPTIONAL_STRING_COLUMNS:
        return "cast(null as string)"
    return column


def _normalize_brief_values(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return tuple(sorted(normalized))


def _normalize_brief_sort_order(sort_order: str) -> str:
    if sort_order in BRIEF_SORT_ORDERS:
        return sort_order
    return "Most optimistic first"


def _build_brief_order_by(sort_order: str) -> str:
    if sort_order == "Least optimistic first":
        return "happy_factor asc, coalesce(published_at, ingested_at) desc, article_id desc"
    return "happy_factor desc, coalesce(published_at, ingested_at) desc, article_id desc"


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


def build_visible_feed_state(
    rows: list[dict[str, object]],
    *,
    feed_sort_order: str,
) -> VisibleFeedState:
    recommended_rows = sort_feed_rows([
        row
        for row in dedupe_story_rows(rows)
        if bool(row.get("is_positive_feed_eligible")) is True
    ])
    recommended_rows = sort_rows_for_display(
        recommended_rows,
        feed_sort_order=feed_sort_order,
    )
    visible_rows = list(recommended_rows)

    return VisibleFeedState(
        recommended_rows=recommended_rows,
        visible_rows=visible_rows,
        summary=summarize_feed(visible_rows),
    )


def sort_feed_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(
        rows,
        key=lambda row: (
            _coerce_float(row.get("happy_factor"))
            if row.get("happy_factor") is not None
            else float("inf"),
            -_row_timestamp_order(row),
            str(row.get("article_id") or ""),
        ),
    )


def sort_rows_for_display(
    rows: list[dict[str, object]],
    *,
    feed_sort_order: str,
) -> list[dict[str, object]]:
    if feed_sort_order == "Most optimistic first":
        return sorted(
            rows,
            key=lambda row: (
                -(
                    _coerce_float(row.get("happy_factor"))
                    if row.get("happy_factor") is not None
                    else float("-inf")
                ),
                -_row_timestamp_order(row),
                str(row.get("article_id") or ""),
            ),
        )
    if feed_sort_order == "Most recent news":
        return sorted(
            rows,
            key=lambda row: (
                -_row_timestamp_order(row),
                -(
                    _coerce_float(row.get("happy_factor"))
                    if row.get("happy_factor") is not None
                    else float("-inf")
                ),
                str(row.get("article_id") or ""),
            ),
        )
    if feed_sort_order == "Oldest news":
        return sorted(
            rows,
            key=lambda row: (
                _row_timestamp_order(row),
                -(
                    _coerce_float(row.get("happy_factor"))
                    if row.get("happy_factor") is not None
                    else float("-inf")
                ),
                str(row.get("article_id") or ""),
            ),
        )
    return list(rows)


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
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day).timestamp()
    if isinstance(value, str) and value.strip():
        normalized_value = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized_value)
        except ValueError:
            return 0.0
        if parsed.tzinfo is None:
            return parsed.timestamp()
        return parsed.astimezone().timestamp()
    return 0.0


def _row_timestamp_order(row: dict[str, object]) -> float:
    for candidate in (
        row.get("published_at"),
        row.get("ingested_at"),
        row.get("serving_date"),
    ):
        timestamp = _coerce_timestamp_order(candidate)
        if timestamp > 0:
            return timestamp
    return 0.0
