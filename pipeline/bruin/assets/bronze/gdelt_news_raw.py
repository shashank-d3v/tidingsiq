"""@bruin
name: bronze.gdelt_news_raw
type: python
image: python:3.11
connection: bigquery-default

materialization:
  type: table
  strategy: merge

columns:
  - name: ingestion_id
    type: string
    checks:
      - name: not_null
  - name: ingested_at
    type: timestamp
    checks:
      - name: not_null
  - name: source_window_start
    type: timestamp
  - name: source_window_end
    type: timestamp
  - name: source_record_id
    type: string
    primary_key: true
    checks:
      - name: not_null
      - name: unique
  - name: source_collection_identifier
    type: string
  - name: document_identifier
    type: string
  - name: source_url
    type: string
  - name: source_name
    type: string
  - name: source_domain
    type: string
  - name: title
    type: string
  - name: language_raw
    type: string
  - name: language
    type: string
    checks:
      - name: not_null
  - name: language_resolution_status
    type: string
    checks:
      - name: not_null
  - name: mentioned_country_code
    type: string
    checks:
      - name: not_null
  - name: mentioned_country_name
    type: string
    checks:
      - name: not_null
  - name: mentioned_country_resolution_status
    type: string
    checks:
      - name: not_null
  - name: published_at
    type: timestamp
  - name: tone_raw
    type: float
  - name: positive_signal_raw
    type: float
  - name: negative_signal_raw
    type: float
  - name: raw_payload
    type: string
@bruin"""

from __future__ import annotations

import csv
import functools
import html
import io
import json
import math
import os
import re
import urllib.error
import urllib.request
import uuid
import zipfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import pandas as pd

try:
    from lingua import LanguageDetectorBuilder
except ImportError:  # pragma: no cover - optional at unit-test import time
    LanguageDetectorBuilder = None

try:
    import pycountry
except ImportError:  # pragma: no cover - optional at unit-test import time
    pycountry = None


DEFAULT_GDELT_BASE_URL = "http://data.gdeltproject.org/gdeltv2"
GDELT_FILE_GRANULARITY_MINUTES = 15
DEFAULT_LOOKBACK_MINUTES = 60
DEFAULT_MAX_FILES = 4
DEFAULT_TIMEOUT_SECONDS = 60
TITLE_PATTERN = re.compile(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>", re.DOTALL)
LANGUAGE_PATTERN = re.compile(r"srclc:([a-zA-Z_-]{2,8})(?:;|$)")
UNKNOWN_LANGUAGE = "und"
UNKNOWN_COUNTRY_CODE = "ZZ"
UNKNOWN_COUNTRY_NAME = "Unknown"
LANGUAGE_INFERENCE_MIN_CHARS = 12
LANGUAGE_INFERENCE_MIN_CONFIDENCE = 0.60
FALLBACK_LANGUAGE_CODE_MAP = {
    "eng": "en",
    "fra": "fr",
    "fre": "fr",
    "spa": "es",
    "deu": "de",
    "ger": "de",
    "ita": "it",
    "por": "pt",
}

GKG_SOURCE_RECORD_ID = 0
GKG_PUBLISHED_AT = 1
GKG_SOURCE_COLLECTION_IDENTIFIER = 2
GKG_SOURCE_NAME = 3
GKG_DOCUMENT_IDENTIFIER = 4
GKG_V2_COUNTS = 6
GKG_V2_THEMES = 8
GKG_V2_LOCATIONS = 10
GKG_V2_PERSONS = 12
GKG_V2_ORGANIZATIONS = 14
GKG_TONE = 15
GKG_GCAM = 17
GKG_ALL_NAMES = 23
GKG_AMOUNTS = 24
GKG_TRANSLATION_INFO = 25
GKG_EXTRAS = 26


def materialize(**kwargs: Any) -> pd.DataFrame:
    """Fetch a bounded set of GDELT GKG files and land article metadata in Bronze."""
    start_dt, end_dt = _resolve_requested_window()
    batch_times = _select_batch_times(start_dt, end_dt)

    if not batch_times:
        return _empty_dataframe()

    ingestion_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{uuid.uuid4().hex[:8]}"
    ingested_at = datetime.now(timezone.utc)
    actual_window_start = batch_times[0]
    actual_window_end = batch_times[-1]

    rows: list[dict[str, Any]] = []
    for batch_time in batch_times:
        rows.extend(
            _fetch_batch_rows(
                batch_time=batch_time,
                ingestion_id=ingestion_id,
                ingested_at=ingested_at,
                source_window_start=actual_window_start,
                source_window_end=actual_window_end,
            )
        )

    if not rows:
        return _empty_dataframe()

    df = pd.DataFrame.from_records(rows)
    return df[
        [
            "ingestion_id",
            "ingested_at",
            "source_window_start",
            "source_window_end",
            "source_record_id",
            "source_collection_identifier",
            "document_identifier",
            "source_url",
            "source_name",
            "source_domain",
            "title",
            "language_raw",
            "language",
            "language_resolution_status",
            "mentioned_country_code",
            "mentioned_country_name",
            "mentioned_country_resolution_status",
            "published_at",
            "tone_raw",
            "positive_signal_raw",
            "negative_signal_raw",
            "raw_payload",
        ]
    ]


def _resolve_requested_window() -> tuple[datetime, datetime]:
    start_raw = os.environ.get("BRUIN_START_DATE")
    end_raw = os.environ.get("BRUIN_END_DATE")

    if start_raw and end_raw:
        start_dt = _parse_bruin_datetime(start_raw)
        end_dt = _parse_bruin_datetime(end_raw)
    else:
        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(minutes=DEFAULT_LOOKBACK_MINUTES)

    if start_dt > end_dt:
        raise ValueError("BRUIN_START_DATE must be less than or equal to BRUIN_END_DATE.")

    return start_dt, end_dt


def _parse_bruin_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _floor_to_batch_boundary(dt: datetime) -> datetime:
    floored_minute = dt.minute - (dt.minute % GDELT_FILE_GRANULARITY_MINUTES)
    return dt.replace(minute=floored_minute, second=0, microsecond=0)


def _select_batch_times(start_dt: datetime, end_dt: datetime) -> list[datetime]:
    batch_start = _floor_to_batch_boundary(start_dt)
    batch_end = _floor_to_batch_boundary(end_dt)

    batches: list[datetime] = []
    current = batch_start
    while current <= batch_end:
        batches.append(current)
        current += timedelta(minutes=GDELT_FILE_GRANULARITY_MINUTES)

    max_files = int(os.environ.get("GDELT_MAX_FILES", str(DEFAULT_MAX_FILES)))
    if max_files > 0 and len(batches) > max_files:
        return batches[-max_files:]
    return batches


def _fetch_batch_rows(
    *,
    batch_time: datetime,
    ingestion_id: str,
    ingested_at: datetime,
    source_window_start: datetime,
    source_window_end: datetime,
) -> list[dict[str, Any]]:
    url = _build_gkg_batch_url(batch_time)
    try:
        response_bytes = _download_bytes(url)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return []
        raise

    records: list[dict[str, Any]] = []
    with zipfile.ZipFile(io.BytesIO(response_bytes)) as archive:
        member_name = archive.namelist()[0]
        with archive.open(member_name, "r") as zipped_file:
            text_stream = io.TextIOWrapper(zipped_file, encoding="utf-8", errors="replace")
            reader = csv.reader(text_stream, delimiter="\t")

            for row in reader:
                if not row or len(row) <= GKG_EXTRAS:
                    continue
                parsed_row = _parse_gkg_row(
                    row=row,
                    ingestion_id=ingestion_id,
                    ingested_at=ingested_at,
                    source_window_start=source_window_start,
                    source_window_end=source_window_end,
                    source_url=url,
                )
                if parsed_row is not None:
                    records.append(parsed_row)

    return records


def _build_gkg_batch_url(batch_time: datetime) -> str:
    base_url = os.environ.get("GDELT_BASE_URL", DEFAULT_GDELT_BASE_URL).rstrip("/")
    return f"{base_url}/{batch_time:%Y%m%d%H%M%S}.gkg.csv.zip"


def _download_bytes(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "TidingsIQ/0.1 Bronze Ingestion"},
    )
    timeout = int(os.environ.get("GDELT_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _parse_gkg_row(
    *,
    row: list[str],
    ingestion_id: str,
    ingested_at: datetime,
    source_window_start: datetime,
    source_window_end: datetime,
    source_url: str,
) -> dict[str, Any] | None:
    source_record_id = row[GKG_SOURCE_RECORD_ID].strip()
    if not source_record_id:
        return None

    document_identifier = _none_if_empty(row[GKG_DOCUMENT_IDENTIFIER])
    source_collection_identifier = _none_if_empty(row[GKG_SOURCE_COLLECTION_IDENTIFIER])
    source_name = _none_if_empty(row[GKG_SOURCE_NAME])
    article_url = document_identifier if source_collection_identifier == "1" else None
    source_domain = _extract_source_domain(article_url, source_name)
    page_title = _extract_page_title(row[GKG_EXTRAS])
    translation_info = _none_if_empty(row[GKG_TRANSLATION_INFO])
    language_raw = _extract_language_raw(translation_info)
    language, language_resolution_status = _resolve_language(
        language_raw=language_raw,
        title=page_title,
    )
    (
        mentioned_country_code,
        mentioned_country_name,
        mentioned_country_resolution_status,
    ) = _extract_mentioned_country(_none_if_empty(row[GKG_V2_LOCATIONS]))

    payload = {
        "gkg_source_file": source_url,
        "gkg_source_collection_identifier": source_collection_identifier,
        "gkg_source_common_name": source_name,
        "gkg_document_identifier": document_identifier,
        "gkg_v2_counts": _none_if_empty(row[GKG_V2_COUNTS]),
        "gkg_v2_themes": _none_if_empty(row[GKG_V2_THEMES]),
        "gkg_v2_locations": _none_if_empty(row[GKG_V2_LOCATIONS]),
        "gkg_v2_persons": _none_if_empty(row[GKG_V2_PERSONS]),
        "gkg_v2_organizations": _none_if_empty(row[GKG_V2_ORGANIZATIONS]),
        "gkg_v2_tone": _none_if_empty(row[GKG_TONE]),
        "gkg_gcam": _none_if_empty(row[GKG_GCAM]),
        "gkg_all_names": _none_if_empty(row[GKG_ALL_NAMES]),
        "gkg_amounts": _none_if_empty(row[GKG_AMOUNTS]),
        "gkg_translation_info": translation_info,
        "gkg_extras": _none_if_empty(row[GKG_EXTRAS]),
    }

    return {
        "ingestion_id": ingestion_id,
        "ingested_at": ingested_at,
        "source_window_start": source_window_start,
        "source_window_end": source_window_end,
        "source_record_id": source_record_id,
        "source_collection_identifier": source_collection_identifier,
        "document_identifier": document_identifier,
        "source_url": article_url,
        "source_name": source_name,
        "source_domain": source_domain,
        "title": page_title,
        "language_raw": language_raw,
        "language": language,
        "language_resolution_status": language_resolution_status,
        "mentioned_country_code": mentioned_country_code,
        "mentioned_country_name": mentioned_country_name,
        "mentioned_country_resolution_status": mentioned_country_resolution_status,
        "published_at": _parse_gdelt_timestamp(row[GKG_PUBLISHED_AT]),
        "tone_raw": _extract_tone(row[GKG_TONE]),
        "positive_signal_raw": None,
        "negative_signal_raw": None,
        "raw_payload": json.dumps(payload, ensure_ascii=True),
    }


def _parse_gdelt_timestamp(value: str) -> datetime | None:
    value = value.strip()
    if not value or value == "0":
        return None
    return datetime.strptime(value, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)


def _extract_tone(value: str) -> float | None:
    value = value.strip()
    if not value:
        return None

    first_component = value.split(",", maxsplit=1)[0].strip()
    if not first_component:
        return None

    tone_value = float(first_component)
    if math.isnan(tone_value):
        return None
    return tone_value


def _extract_page_title(extras_value: str) -> str | None:
    match = TITLE_PATTERN.search(extras_value or "")
    if not match:
        return None
    return html.unescape(match.group(1)).strip() or None


def _extract_language_raw(translation_info: str | None) -> str | None:
    if not translation_info:
        return None

    match = LANGUAGE_PATTERN.search(translation_info)
    if not match:
        return None

    return _normalize_language_code(match.group(1).strip())


def _resolve_language(*, language_raw: str | None, title: str | None) -> tuple[str, str]:
    if language_raw:
        return language_raw, "native"

    inferred_language = _infer_language_from_title(title)
    if inferred_language:
        return inferred_language, "inferred"

    return UNKNOWN_LANGUAGE, "undetermined"


def _infer_language_from_title(title: str | None) -> str | None:
    if not title:
        return None

    cleaned_title = re.sub(r"\s+", " ", title).strip()
    if len(cleaned_title) < LANGUAGE_INFERENCE_MIN_CHARS:
        return None

    detector = _get_language_detector()
    if detector is None:
        return None

    try:
        confidence_values = detector.compute_language_confidence_values(cleaned_title)
    except Exception:  # pragma: no cover - detector failures are environmental
        return None

    if not confidence_values:
        return None

    top_candidate = confidence_values[0]
    if getattr(top_candidate, "value", 0.0) < LANGUAGE_INFERENCE_MIN_CONFIDENCE:
        return None

    return _normalize_language_code(_lingua_language_to_code(top_candidate.language))


@functools.lru_cache(maxsize=1)
def _get_language_detector() -> Any:
    if LanguageDetectorBuilder is None:
        return None

    builder = LanguageDetectorBuilder.from_all_languages()
    preload = getattr(builder, "with_preloaded_language_models", None)
    if callable(preload):
        builder = preload()
    return builder.build()


def _lingua_language_to_code(language: Any) -> str | None:
    iso_code = getattr(language, "iso_code_639_1", None)
    if iso_code is not None:
        for attribute in ("name", "value"):
            candidate = getattr(iso_code, attribute, None)
            normalized = _normalize_language_code(candidate)
            if normalized:
                return normalized

    for attribute in ("name", "value"):
        candidate = getattr(language, attribute, None)
        normalized = _normalize_language_code(candidate)
        if normalized:
            return normalized

    return None


def _normalize_language_code(value: str | None) -> str | None:
    if not value:
        return None

    normalized = value.strip().lower().replace("_", "-")
    if not normalized:
        return None

    if pycountry is not None:
        language = (
            pycountry.languages.get(alpha_2=normalized)
            or pycountry.languages.get(alpha_3=normalized)
        )
        if language is not None:
            alpha_2 = getattr(language, "alpha_2", None)
            if alpha_2:
                return alpha_2.lower()

    if re.fullmatch(r"[a-z]{2}", normalized):
        return normalized

    return FALLBACK_LANGUAGE_CODE_MAP.get(normalized)


def _extract_source_domain(source_url: str | None, source_name: str | None) -> str | None:
    if source_url:
        parsed = urlparse(source_url)
        host = parsed.netloc or parsed.path
        host = host.lower().strip()
        if host:
            host = host.split("/", maxsplit=1)[0]
            host = re.sub(r":\d+$", "", host)
            host = re.sub(r"^www\.", "", host)
            if host:
                return host

    if source_name:
        normalized_source_name = source_name.lower().strip()
        normalized_source_name = re.sub(r"^www\.", "", normalized_source_name)
        return normalized_source_name or None

    return None


def _extract_mentioned_country(v2_locations: str | None) -> tuple[str, str, str]:
    if not v2_locations:
        return UNKNOWN_COUNTRY_CODE, UNKNOWN_COUNTRY_NAME, "undetermined"

    country_counts: Counter[str] = Counter()
    first_seen: dict[str, int] = {}

    for index, entry in enumerate(v2_locations.split(";")):
        parts = entry.split("#")
        if len(parts) < 3:
            continue

        country_code = _normalize_country_code(parts[2])
        if country_code is None:
            continue

        country_counts[country_code] += 1
        first_seen.setdefault(country_code, index)

    if not country_counts:
        return UNKNOWN_COUNTRY_CODE, UNKNOWN_COUNTRY_NAME, "undetermined"

    best_country_code = min(
        country_counts,
        key=lambda code: (-country_counts[code], first_seen[code]),
    )
    country_name = _country_name_from_code(best_country_code)
    if country_name is None:
        return UNKNOWN_COUNTRY_CODE, UNKNOWN_COUNTRY_NAME, "undetermined"

    return best_country_code, country_name, "v2_locations"


def _normalize_country_code(value: str | None) -> str | None:
    if not value:
        return None

    normalized = value.strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", normalized):
        return None
    return normalized


def _country_name_from_code(country_code: str | None) -> str | None:
    if not country_code or pycountry is None:
        return None

    country = pycountry.countries.get(alpha_2=country_code)
    if country is None:
        return None
    return getattr(country, "name", None)


def _none_if_empty(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _empty_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ingestion_id": pd.Series(dtype="string"),
            "ingested_at": pd.Series(dtype="datetime64[ns, UTC]"),
            "source_window_start": pd.Series(dtype="datetime64[ns, UTC]"),
            "source_window_end": pd.Series(dtype="datetime64[ns, UTC]"),
            "source_record_id": pd.Series(dtype="string"),
            "source_collection_identifier": pd.Series(dtype="string"),
            "document_identifier": pd.Series(dtype="string"),
            "source_url": pd.Series(dtype="string"),
            "source_name": pd.Series(dtype="string"),
            "source_domain": pd.Series(dtype="string"),
            "title": pd.Series(dtype="string"),
            "language_raw": pd.Series(dtype="string"),
            "language": pd.Series(dtype="string"),
            "language_resolution_status": pd.Series(dtype="string"),
            "mentioned_country_code": pd.Series(dtype="string"),
            "mentioned_country_name": pd.Series(dtype="string"),
            "mentioned_country_resolution_status": pd.Series(dtype="string"),
            "published_at": pd.Series(dtype="datetime64[ns, UTC]"),
            "tone_raw": pd.Series(dtype="float64"),
            "positive_signal_raw": pd.Series(dtype="float64"),
            "negative_signal_raw": pd.Series(dtype="float64"),
            "raw_payload": pd.Series(dtype="string"),
        }
    )
