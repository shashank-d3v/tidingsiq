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
  - name: document_identifier
    type: string
  - name: source_url
    type: string
  - name: source_name
    type: string
  - name: title
    type: string
  - name: language
    type: string
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
import html
import io
import json
import math
import os
import re
import ssl
import urllib.error
import urllib.request
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd


GDELT_GKG_URL_TEMPLATE = "https://data.gdeltproject.org/gdeltv2/{timestamp}.gkg.csv.zip"
GDELT_FILE_GRANULARITY_MINUTES = 15
DEFAULT_LOOKBACK_MINUTES = 60
DEFAULT_MAX_FILES = 4
DEFAULT_TIMEOUT_SECONDS = 60
TITLE_PATTERN = re.compile(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>", re.DOTALL)
LANGUAGE_PATTERN = re.compile(r"srclc:(.*?);")

GKG_SOURCE_RECORD_ID = 0
GKG_PUBLISHED_AT = 1
GKG_SOURCE_COLLECTION_IDENTIFIER = 2
GKG_SOURCE_NAME = 3
GKG_DOCUMENT_IDENTIFIER = 4
GKG_TONE = 15
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
            "document_identifier",
            "source_url",
            "source_name",
            "title",
            "language",
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
    url = GDELT_GKG_URL_TEMPLATE.format(timestamp=batch_time.strftime("%Y%m%d%H%M%S"))
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


def _download_bytes(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "TidingsIQ/0.1 Bronze Ingestion"},
    )
    timeout = int(os.environ.get("GDELT_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
    context = None
    if os.environ.get("GDELT_DISABLE_SSL_VERIFY", "").lower() in {"1", "true", "yes"}:
        context = ssl._create_unverified_context()

    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
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
    page_title = _extract_page_title(row[GKG_EXTRAS])
    translation_info = _none_if_empty(row[GKG_TRANSLATION_INFO])
    language = _extract_language(translation_info)

    payload = {
        "gkg_source_file": source_url,
        "gkg_source_collection_identifier": source_collection_identifier,
        "gkg_source_common_name": _none_if_empty(row[GKG_SOURCE_NAME]),
        "gkg_document_identifier": document_identifier,
        "gkg_v2_tone": _none_if_empty(row[GKG_TONE]),
        "gkg_translation_info": translation_info,
        "gkg_extras": _none_if_empty(row[GKG_EXTRAS]),
    }

    return {
        "ingestion_id": ingestion_id,
        "ingested_at": ingested_at,
        "source_window_start": source_window_start,
        "source_window_end": source_window_end,
        "source_record_id": source_record_id,
        "document_identifier": document_identifier,
        "source_url": document_identifier if source_collection_identifier == "1" else None,
        "source_name": _none_if_empty(row[GKG_SOURCE_NAME]),
        "title": page_title,
        "language": language,
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


def _extract_language(translation_info: str | None) -> str | None:
    if not translation_info:
        return None

    match = LANGUAGE_PATTERN.search(translation_info)
    if not match:
        return None
    return match.group(1).strip() or None


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
            "document_identifier": pd.Series(dtype="string"),
            "source_url": pd.Series(dtype="string"),
            "source_name": pd.Series(dtype="string"),
            "title": pd.Series(dtype="string"),
            "language": pd.Series(dtype="string"),
            "published_at": pd.Series(dtype="datetime64[ns, UTC]"),
            "tone_raw": pd.Series(dtype="float64"),
            "positive_signal_raw": pd.Series(dtype="float64"),
            "negative_signal_raw": pd.Series(dtype="float64"),
            "raw_payload": pd.Series(dtype="string"),
        }
    )
