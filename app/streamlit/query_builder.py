from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class FeedQueryConfig:
    table_fqn: str
    min_happy_factor: float = 70.0
    lookback_days: int = 7
    row_limit: int = 25


def _clamp_float(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _clamp_int(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def build_feed_query(
    config: FeedQueryConfig,
    *,
    now_utc: datetime | None = None,
) -> tuple[str, list[tuple[str, str, object]]]:
    threshold = _clamp_float(config.min_happy_factor, 0.0, 100.0)
    lookback_days = _clamp_int(config.lookback_days, 1, 30)
    row_limit = _clamp_int(config.row_limit, 1, 100)
    now_utc = now_utc or datetime.now(timezone.utc)
    published_after = now_utc - timedelta(days=lookback_days)

    sql = f"""
select
  article_id,
  serving_date,
  published_at,
  source_name,
  title,
  url,
  tone_score,
  happy_factor,
  happy_factor_version,
  ingested_at
from `{config.table_fqn}`
where happy_factor >= @min_happy_factor
  and serving_date >= date(@published_after)
"""

    parameters: list[tuple[str, str, object]] = [
        ("min_happy_factor", "FLOAT64", threshold),
        ("published_after", "TIMESTAMP", published_after),
        ("row_limit", "INT64", row_limit),
    ]

    sql += """
order by happy_factor desc, coalesce(published_at, ingested_at) desc, article_id desc
limit @row_limit
"""

    return sql.strip(), parameters


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
