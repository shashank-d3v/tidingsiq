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
  - name: bronze_run_total_row_count
    type: integer
  - name: bronze_run_accepted_row_count
    type: integer
  - name: bronze_run_malformed_row_count
    type: integer
  - name: bronze_run_malformed_ratio
    type: float
  - name: bronze_run_expected_file_count
    type: integer
  - name: bronze_run_downloaded_file_count
    type: integer
  - name: bronze_run_missing_file_count
    type: integer
  - name: bronze_run_is_complete
    type: boolean
  - name: bronze_run_is_backfill
    type: boolean
  - name: bronze_run_low_volume
    type: boolean
  - name: bronze_run_baseline_average_accepted_row_count
    type: float
  - name: bronze_run_low_volume_threshold
    type: float
  - name: raw_payload
    type: string
@bruin"""

from __future__ import annotations

import csv
import dataclasses
import functools
import html
import io
import json
import math
import os
import random
import re
import socket
import sys
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
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


DEFAULT_GDELT_BASE_URL = "https://data.gdeltproject.org/gdeltv2"
EXPECTED_GDELT_HOST = "data.gdeltproject.org"
GDELT_FILE_GRANULARITY_MINUTES = 15
DEFAULT_LOOKBACK_MINUTES = 60
DEFAULT_MAX_FILES = 4
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_PUBLICATION_LAG_MINUTES = 60
DEFAULT_DOWNLOAD_MAX_ATTEMPTS = 4
DEFAULT_DOWNLOAD_BACKOFF_SECONDS = (5.0, 15.0, 30.0)
DEFAULT_RECENT_FILE_HOURS = 24
RETRY_JITTER_RATIO = 0.20
MAX_RETRY_AFTER_SECONDS = 60.0
DEFAULT_CSV_FIELD_SIZE_LIMIT = 16 * 1024 * 1024
DEFAULT_MAX_MALFORMED_RATIO = 0.05
DEFAULT_MIN_ACCEPTED_ROW_RATIO = 0.50
DEFAULT_LOW_ACCEPTED_ROW_ACTION = "warn"
DEFAULT_BASELINE_RUNS = 5
DEFAULT_BRONZE_TABLE = "bronze.gdelt_news_raw"
GDELT_LASTUPDATE_URL = "https://data.gdeltproject.org/gdeltv2/lastupdate.txt"
TITLE_PATTERN = re.compile(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>", re.DOTALL)
LANGUAGE_PATTERN = re.compile(r"srclc:([a-zA-Z_-]{2,8})(?:;|$)")
GKG_ZIP_FILENAME_PATTERN = re.compile(r"^\d{14}\.gkg\.csv\.zip$")
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
EXPECTED_GKG_ROW_WIDTH = GKG_EXTRAS + 1
DEPLOYED_RUNTIME_ENV_VARS = (
    "CLOUD_RUN_JOB",
    "CLOUD_RUN_EXECUTION",
    "K_SERVICE",
    "K_REVISION",
)

MALFORMED_REASON_MISSING_SOURCE_RECORD_ID = "missing_source_record_id"
MALFORMED_REASON_TIMESTAMP_PARSE_FAILURE = "timestamp_parse_failure"
MALFORMED_REASON_WIDTH_MISMATCH = "width_mismatch"
ZIP_READ_FAILURE_REASON = "zip_read_failure"
RETRYABLE_HTTP_STATUSES = {408, 429, 500, 502, 503, 504}


@dataclasses.dataclass
class BatchFetchResult:
    records: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    total_rows_seen: int = 0
    accepted_rows: int = 0
    malformed_rows: int = 0
    malformed_reasons: Counter[str] = dataclasses.field(default_factory=Counter)
    availability_status: str = "available"
    was_missing: bool = False
    missing_reason: str | None = None


@dataclasses.dataclass(frozen=True)
class RequestedWindow:
    start_dt: datetime
    end_dt: datetime
    batch_times: tuple[datetime, ...]
    selection_mode: str
    is_backfill: bool

    @property
    def anchor(self) -> str:
        return "lag" if self.selection_mode == "lag_fallback" else self.selection_mode


@dataclasses.dataclass(frozen=True)
class RunGuardrailResult:
    low_volume: bool | None = None
    baseline_average_accepted_row_count: float | None = None
    low_volume_threshold: float | None = None


class GdeltArchiveUnavailable(RuntimeError):
    """A validated GDELT resource remained unavailable after bounded retries."""


def materialize(**kwargs: Any) -> pd.DataFrame:
    """Fetch a bounded set of GDELT GKG files and land article metadata in Bronze."""
    window = _resolve_window_selection()
    batch_times = list(window.batch_times)

    if not batch_times:
        return _empty_dataframe()

    ingestion_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{uuid.uuid4().hex[:8]}"
    ingested_at = datetime.now(timezone.utc)
    actual_window_start = batch_times[0]
    actual_window_end = batch_times[-1]

    rows: list[dict[str, Any]] = []
    total_rows_seen = 0
    accepted_rows = 0
    malformed_rows = 0
    successful_batches = 0
    missing_batches: list[str] = []
    missing_archives: list[dict[str, str]] = []

    for batch_time in batch_times:
        batch_result = _fetch_batch_rows(
            batch_time=batch_time,
            ingestion_id=ingestion_id,
            ingested_at=ingested_at,
            source_window_start=actual_window_start,
            source_window_end=actual_window_end,
        )
        rows.extend(batch_result.records)
        total_rows_seen += batch_result.total_rows_seen
        accepted_rows += batch_result.accepted_rows
        malformed_rows += batch_result.malformed_rows
        if not batch_result.was_missing:
            successful_batches += 1
        else:
            batch_timestamp = f"{batch_time:%Y%m%d%H%M%S}"
            missing_batches.append(batch_timestamp)
            missing_archives.append(
                {
                    "batch_timestamp": batch_timestamp,
                    "reason": batch_result.missing_reason or "unavailable",
                }
            )

    expected_file_count = len(batch_times)
    missing_file_count = expected_file_count - successful_batches
    is_complete = successful_batches == expected_file_count
    completeness = "complete" if is_complete else "partial" if successful_batches else "empty"
    guardrail_result = RunGuardrailResult()
    if successful_batches > 0:
        guardrail_result = _enforce_run_guardrails(
            accepted_rows=accepted_rows,
            total_rows_seen=total_rows_seen,
            malformed_rows=malformed_rows,
            evaluate_low_volume=is_complete and not window.is_backfill,
        )

    low_volume = guardrail_result.low_volume
    # Persist source-fetch outcomes even when there are no article rows to load.
    # This describes downloads, not the subsequent Bruin/dlt warehouse commit.
    _persist_source_attempt({
        "ingestion_id": ingestion_id,
        "latest_ingested_at": ingested_at.isoformat(),
        "source_window_start": actual_window_start.isoformat(),
        "source_window_end": actual_window_end.isoformat(),
        "accepted_row_count": accepted_rows,
        "malformed_ratio": _calculate_ratio(malformed_rows, total_rows_seen),
        "expected_file_count": expected_file_count,
        "downloaded_file_count": successful_batches,
        "missing_file_count": missing_file_count,
        "is_complete": is_complete,
        "is_backfill": window.is_backfill,
        "low_volume": low_volume,
    })
    _emit_ingestion_summary(
        ingestion_id=ingestion_id,
        window=window,
        expected_file_count=expected_file_count,
        downloaded_file_count=successful_batches,
        missing_batches=missing_batches,
        completeness=completeness,
        accepted_rows=accepted_rows,
        malformed_rows=malformed_rows,
        low_volume=low_volume,
    )

    if not rows:
        return _empty_dataframe()

    malformed_ratio = _calculate_ratio(malformed_rows, total_rows_seen)
    for row in rows:
        raw_payload = json.loads(row["raw_payload"])
        raw_payload.update(
            {
                "bronze_run_total_row_count": total_rows_seen,
                "bronze_run_accepted_row_count": accepted_rows,
                "bronze_run_malformed_row_count": malformed_rows,
                "bronze_run_malformed_ratio": malformed_ratio,
                "bronze_run_expected_file_count": expected_file_count,
                "bronze_run_downloaded_file_count": successful_batches,
                "bronze_run_missing_file_count": missing_file_count,
                "bronze_run_is_complete": is_complete,
                "bronze_run_is_backfill": window.is_backfill,
                "bronze_run_low_volume": low_volume,
                "bronze_run_baseline_average_accepted_row_count": guardrail_result.baseline_average_accepted_row_count,
                "bronze_run_low_volume_threshold": guardrail_result.low_volume_threshold,
                "bronze_run_missing_batch_timestamps": missing_batches,
                "bronze_run_missing_archives": missing_archives,
                "bronze_run_window_selection_mode": window.selection_mode,
            }
        )
        row.update(
            {
                "bronze_run_total_row_count": total_rows_seen,
                "bronze_run_accepted_row_count": accepted_rows,
                "bronze_run_malformed_row_count": malformed_rows,
                "bronze_run_malformed_ratio": malformed_ratio,
                "bronze_run_expected_file_count": expected_file_count,
                "bronze_run_downloaded_file_count": successful_batches,
                "bronze_run_missing_file_count": missing_file_count,
                "bronze_run_is_complete": is_complete,
                "bronze_run_is_backfill": window.is_backfill,
                "bronze_run_low_volume": low_volume,
                "bronze_run_baseline_average_accepted_row_count": guardrail_result.baseline_average_accepted_row_count,
                "bronze_run_low_volume_threshold": guardrail_result.low_volume_threshold,
                "raw_payload": json.dumps(raw_payload, ensure_ascii=True),
            }
        )

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
            "bronze_run_total_row_count",
            "bronze_run_accepted_row_count",
            "bronze_run_malformed_row_count",
            "bronze_run_malformed_ratio",
            "bronze_run_expected_file_count",
            "bronze_run_downloaded_file_count",
            "bronze_run_missing_file_count",
            "bronze_run_is_complete",
            "bronze_run_is_backfill",
            "bronze_run_low_volume",
            "bronze_run_baseline_average_accepted_row_count",
            "bronze_run_low_volume_threshold",
            "raw_payload",
        ]
    ]


SOURCE_ATTEMPT_FIELDS = (
    ("ingestion_id", "STRING"),
    ("latest_ingested_at", "TIMESTAMP"),
    ("source_window_start", "TIMESTAMP"),
    ("source_window_end", "TIMESTAMP"),
    ("accepted_row_count", "INTEGER"),
    ("malformed_ratio", "FLOAT"),
    ("expected_file_count", "INTEGER"),
    ("downloaded_file_count", "INTEGER"),
    ("missing_file_count", "INTEGER"),
    ("is_complete", "BOOLEAN"),
    ("is_backfill", "BOOLEAN"),
    ("low_volume", "BOOLEAN"),
)


def _persist_source_attempt(attempt: dict[str, Any]) -> None:
    imported_bigquery = _import_bigquery()
    project_id = _resolve_project_id()
    if imported_bigquery is None or not project_id:
        raise RuntimeError("Recording GDELT source attempts requires BigQuery and a project ID")
    client = imported_bigquery.Client(project=project_id)
    table_id = f"{project_id}.bronze.gdelt_ingestion_attempts"
    schema = [imported_bigquery.SchemaField(name, kind) for name, kind in SOURCE_ATTEMPT_FIELDS]
    table = imported_bigquery.Table(table_id, schema=schema)
    table.time_partitioning = imported_bigquery.TimePartitioning(field="latest_ingested_at")
    client.create_table(table, exists_ok=True)
    # A deterministic load job prevents an ambiguous API retry from appending
    # the same attempt twice. Wait for visibility before returning to Bruin.
    client.load_table_from_json(
        [attempt], table_id,
        job_id=f"gdelt_attempt_{attempt['ingestion_id']}",
        job_config=imported_bigquery.LoadJobConfig(
            schema=schema, write_disposition="WRITE_APPEND",
        ),
    ).result()


def _emit_ingestion_summary(
    *,
    ingestion_id: str,
    window: RequestedWindow,
    expected_file_count: int,
    downloaded_file_count: int,
    missing_batches: list[str],
    completeness: str,
    accepted_rows: int,
    malformed_rows: int,
    low_volume: bool | None,
) -> None:
    low_volume_text = "unknown" if low_volume is None else str(low_volume).lower()
    missing_text = ",".join(missing_batches) or "none"
    mode = "backfill" if window.is_backfill else "live"
    print(
        "GDELT_INGESTION_SUMMARY "
        f"ingestion_id={ingestion_id} mode={mode} anchor={window.anchor} "
        f"expected_files={expected_file_count} downloaded_files={downloaded_file_count} "
        f"missing_files={expected_file_count - downloaded_file_count} "
        f"missing_batches={missing_text} completeness={completeness} "
        f"accepted_rows={accepted_rows} malformed_rows={malformed_rows} "
        f"low_volume={low_volume_text}"
    )


def _resolve_requested_window() -> tuple[datetime, datetime]:
    selection = _resolve_window_selection()
    return selection.start_dt, selection.end_dt


def _resolve_window_selection() -> RequestedWindow:
    start_raw = os.environ.get("BRUIN_START_DATETIME") or os.environ.get(
        "BRUIN_START_DATE"
    )
    end_raw = os.environ.get("BRUIN_END_DATETIME") or os.environ.get("BRUIN_END_DATE")
    current_time = datetime.now(timezone.utc)

    # Bruin always exports a computed interval, including for ordinary scheduled
    # executions. The container entrypoint records whether the operator actually
    # supplied --start-date/--end-date so deployed rolling runs do not mistake
    # Bruin's generated daily interval for an explicit historical backfill.
    if _is_deployed_runtime() and not _explicit_interval_requested():
        return _resolve_rolling_window(current_time)

    if start_raw and end_raw:
        start_dt = _parse_bruin_datetime(start_raw)
        end_dt = _parse_bruin_datetime(end_raw)
    else:
        return _resolve_rolling_window(current_time)

    if start_dt > end_dt:
        raise ValueError("BRUIN_START_DATE must be less than or equal to BRUIN_END_DATE.")

    if _should_fallback_to_runtime_lookback_window(
        start_dt=start_dt,
        end_dt=end_dt,
        current_time=current_time,
    ):
        print(
            "Bruin interval resolved to a stale zero-width deployed window "
            f"({start_dt.isoformat()} to {end_dt.isoformat()}); "
            "falling back to the rolling Bronze lookback window."
        )
        return _resolve_rolling_window(current_time)

    batch_times = tuple(_select_batch_times(start_dt, end_dt))
    if batch_times:
        start_dt, end_dt = batch_times[0], batch_times[-1]
    is_backfill = end_dt < current_time - timedelta(
        minutes=GDELT_FILE_GRANULARITY_MINUTES
    )
    return RequestedWindow(
        start_dt=start_dt,
        end_dt=end_dt,
        batch_times=batch_times,
        selection_mode="explicit",
        is_backfill=is_backfill,
    )


def _explicit_interval_requested() -> bool:
    return os.environ.get("GDELT_EXPLICIT_INTERVAL_REQUESTED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _default_requested_window(current_time: datetime) -> tuple[datetime, datetime]:
    selection = _resolve_lag_fallback_window(current_time)
    return selection.start_dt, selection.end_dt


def _resolve_rolling_window(current_time: datetime) -> RequestedWindow:
    try:
        manifest_batch_time = _fetch_latest_manifest_batch_time(current_time)
        # lastupdate.txt can lead actual GKG availability by nearly an hour.
        # A valid manifest is an upper bound, not proof its ZIPs are readable.
        safe_end = _floor_to_batch_boundary(
            current_time - timedelta(minutes=_publication_lag_minutes())
        )
        batch_times = tuple(_batch_times_ending_at(min(manifest_batch_time, safe_end)))
        return RequestedWindow(
            start_dt=batch_times[0],
            end_dt=batch_times[-1],
            batch_times=batch_times,
            selection_mode="manifest",
            is_backfill=False,
        )
    except Exception as exc:
        fallback = _resolve_lag_fallback_window(current_time)
        print(
            "GDELT_MANIFEST_FALLBACK "
            f"reason={type(exc).__name__} lag_minutes={_publication_lag_minutes()} "
            f"fallback_end={fallback.end_dt.isoformat()}"
        )
        return fallback


def _resolve_lag_fallback_window(current_time: datetime) -> RequestedWindow:
    end_dt = _floor_to_batch_boundary(
        current_time - timedelta(minutes=_publication_lag_minutes())
    )
    batch_times = tuple(_batch_times_ending_at(end_dt))
    return RequestedWindow(
        start_dt=batch_times[0],
        end_dt=batch_times[-1],
        batch_times=batch_times,
        selection_mode="lag_fallback",
        is_backfill=False,
    )


def _publication_lag_minutes() -> int:
    return int(
        os.environ.get(
            "GDELT_PUBLICATION_LAG_MINUTES",
            str(DEFAULT_PUBLICATION_LAG_MINUTES),
        )
    )


def _batch_times_ending_at(end_dt: datetime) -> list[datetime]:
    max_files = int(os.environ.get("GDELT_MAX_FILES", str(DEFAULT_MAX_FILES)))
    if max_files <= 0:
        return []
    end_dt = _floor_to_batch_boundary(end_dt)
    return [
        end_dt
        - timedelta(
            minutes=GDELT_FILE_GRANULARITY_MINUTES * offset
        )
        for offset in reversed(range(max_files))
    ]


def _fetch_latest_manifest_batch_time(current_time: datetime) -> datetime:
    response_bytes, resolved_url = _download_bytes_with_retry(
        GDELT_LASTUPDATE_URL,
        resource_label="manifest",
    )
    _validate_lastupdate_url(resolved_url)
    return _parse_manifest_gkg_batch_time(
        response_bytes.decode("utf-8"),
        current_time=current_time,
    )


def _validate_lastupdate_url(url: str) -> None:
    parsed = urlparse(url)
    if _normalized_host(parsed.netloc) != EXPECTED_GDELT_HOST:
        raise ValueError("GDELT lastupdate manifest resolved to an invalid host.")
    if parsed.path.rstrip("/") != "/gdeltv2/lastupdate.txt":
        raise ValueError("GDELT lastupdate manifest resolved to an invalid path.")


def _parse_manifest_gkg_batch_time(
    manifest_text: str,
    *,
    current_time: datetime,
) -> datetime:
    for line in manifest_text.splitlines():
        fields = line.split()
        if len(fields) < 3:
            continue
        candidate_url = fields[-1]
        parsed = urlparse(candidate_url)
        filename = parsed.path.rsplit("/", maxsplit=1)[-1]
        if not filename.endswith(".gkg.csv.zip"):
            continue
        if _normalized_host(parsed.netloc) != EXPECTED_GDELT_HOST:
            raise ValueError("GDELT manifest GKG entry used an invalid host.")
        if not GKG_ZIP_FILENAME_PATTERN.fullmatch(filename):
            raise ValueError("GDELT manifest GKG entry used an invalid filename.")
        batch_time = datetime.strptime(filename[:14], "%Y%m%d%H%M%S").replace(
            tzinfo=timezone.utc
        )
        if batch_time.minute % GDELT_FILE_GRANULARITY_MINUTES != 0:
            raise ValueError("GDELT manifest GKG timestamp was off the 15-minute boundary.")
        if batch_time > current_time:
            raise ValueError("GDELT manifest GKG timestamp was materially in the future.")
        return batch_time
    raise ValueError("GDELT lastupdate manifest contained no valid GKG entry.")


def _should_fallback_to_runtime_lookback_window(
    *,
    start_dt: datetime,
    end_dt: datetime,
    current_time: datetime,
) -> bool:
    if not _is_deployed_runtime():
        return False

    if start_dt != end_dt:
        return False

    return current_time - end_dt >= timedelta(
        minutes=GDELT_FILE_GRANULARITY_MINUTES
    )


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
) -> BatchFetchResult:
    url = _build_gkg_batch_url(batch_time)
    _validate_gkg_download_url(url, batch_time)
    try:
        response_bytes, resolved_url = _download_bytes_with_retry(
            url,
            batch_time=batch_time,
            resource_label=f"{batch_time:%Y%m%d%H%M%S}",
        )
    except GdeltArchiveUnavailable as exc:
        return BatchFetchResult(
            availability_status="unavailable",
            was_missing=True,
            missing_reason=str(exc),
        )
    _validate_gkg_download_url(resolved_url, batch_time)

    try:
        result = _read_batch_archive(
            response_bytes=response_bytes,
            batch_time=batch_time,
            ingestion_id=ingestion_id,
            ingested_at=ingested_at,
            source_window_start=source_window_start,
            source_window_end=source_window_end,
            source_url=resolved_url,
        )
        if result.total_rows_seen == 0:
            raise RuntimeError(
                f"GDELT validation failed for {batch_time:%Y%m%d%H%M%S}: "
                "downloaded archive contained zero rows."
            )
        if result.accepted_rows == 0:
            raise RuntimeError(
                f"GDELT validation failed for {batch_time:%Y%m%d%H%M%S}: "
                "downloaded archive produced zero accepted rows."
            )
        return result
    except zipfile.BadZipFile as exc:
        raise RuntimeError(
            f"GDELT {ZIP_READ_FAILURE_REASON} for {resolved_url}: ZIP could not be opened."
        ) from exc
    except (KeyError, OSError) as exc:
        raise RuntimeError(
            f"GDELT {ZIP_READ_FAILURE_REASON} for {resolved_url}: ZIP member could not be read."
        ) from exc


def _build_gkg_batch_url(batch_time: datetime) -> str:
    base_url = _resolve_gdelt_base_url()
    return f"{base_url}/{batch_time:%Y%m%d%H%M%S}.gkg.csv.zip"


def _resolve_gdelt_base_url() -> str:
    base_url = os.environ.get("GDELT_BASE_URL", DEFAULT_GDELT_BASE_URL).rstrip("/")
    parsed = urlparse(base_url)
    host = _normalized_host(parsed.netloc)

    if not parsed.scheme or not host:
        raise ValueError("GDELT_BASE_URL must be an absolute URL with a host.")

    if _is_deployed_runtime() and host != EXPECTED_GDELT_HOST:
        raise ValueError(
            f"GDELT_BASE_URL host '{host}' is not allowed in deployed runtimes; "
            f"expected '{EXPECTED_GDELT_HOST}'."
        )

    return base_url


def _is_deployed_runtime() -> bool:
    return any(os.environ.get(env_var) for env_var in DEPLOYED_RUNTIME_ENV_VARS)


def _validate_gkg_download_url(url: str, batch_time: datetime) -> None:
    parsed = urlparse(url)
    host = _normalized_host(parsed.netloc)
    filename = parsed.path.rsplit("/", maxsplit=1)[-1]
    expected_filename = f"{batch_time:%Y%m%d%H%M%S}.gkg.csv.zip"

    if host != EXPECTED_GDELT_HOST:
        raise ValueError(
            f"GDELT download host '{host or '<missing>'}' is invalid; "
            f"expected '{EXPECTED_GDELT_HOST}'."
        )

    if not GKG_ZIP_FILENAME_PATTERN.fullmatch(filename):
        raise ValueError(
            f"GDELT download filename '{filename}' is invalid; expected '*.gkg.csv.zip'."
        )

    if filename != expected_filename:
        raise ValueError(
            f"GDELT download filename '{filename}' does not match expected batch file "
            f"'{expected_filename}'."
        )


def _normalized_host(netloc: str) -> str:
    host = netloc.lower().strip()
    host = re.sub(r":\d+$", "", host)
    return host.rstrip(".")


class _ValidatingGdeltRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_gdelt_redirect(req.full_url, newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _validate_gdelt_redirect(previous_url: str, new_url: str) -> None:
    previous = urlparse(previous_url)
    redirected = urlparse(new_url)
    if redirected.scheme not in {"http", "https"}:
        raise ValueError("GDELT redirect used an unsupported URL scheme.")
    if _normalized_host(redirected.netloc) != EXPECTED_GDELT_HOST:
        raise ValueError("GDELT redirect resolved to an invalid host.")
    if redirected.path != previous.path:
        raise ValueError("GDELT redirect changed the validated resource path.")


def _download_bytes(url: str) -> tuple[bytes, str]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "TidingsIQ/0.1 Bronze Ingestion"},
    )
    timeout = int(os.environ.get("GDELT_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
    opener = urllib.request.build_opener(_ValidatingGdeltRedirectHandler())
    with opener.open(request, timeout=timeout) as response:
        resolved_url = getattr(response, "geturl", lambda: url)()
        return response.read(), str(resolved_url or url)


def _download_bytes_with_retry(
    url: str,
    *,
    batch_time: datetime | None = None,
    resource_label: str,
) -> tuple[bytes, str]:
    max_attempts = int(
        os.environ.get(
            "GDELT_DOWNLOAD_MAX_ATTEMPTS",
            str(DEFAULT_DOWNLOAD_MAX_ATTEMPTS),
        )
    )
    if max_attempts < 1:
        raise ValueError("GDELT_DOWNLOAD_MAX_ATTEMPTS must be at least 1.")

    delays = _download_backoff_seconds()
    last_error: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            payload = _download_bytes(url)
            print(
                "GDELT_DOWNLOAD_ATTEMPT "
                f"resource={resource_label} url={url} attempt={attempt} "
                "status=success delay_seconds=0.00 outcome=success"
            )
            return payload
        except urllib.error.HTTPError as exc:
            last_error = exc
            retryable = _is_retryable_http_error(exc, batch_time=batch_time)
            if not retryable:
                if exc.code in {400, 404} and batch_time is not None:
                    print(
                        "GDELT_DOWNLOAD_ATTEMPT "
                        f"resource={resource_label} url={url} attempt={attempt} "
                        f"status={exc.code} delay_seconds=0.00 outcome=unavailable"
                    )
                    raise GdeltArchiveUnavailable(
                        f"HTTP {exc.code} for {resource_label}"
                    ) from exc
                print(
                    "GDELT_DOWNLOAD_ATTEMPT "
                    f"resource={resource_label} url={url} attempt={attempt} "
                    f"status={exc.code} delay_seconds=0.00 outcome=failed"
                )
                raise
            if attempt >= max_attempts:
                break
            delay = _retry_delay_seconds(
                attempt=attempt,
                delays=delays,
                retry_after=_retry_after_seconds(exc),
            )
            print(
                "GDELT_DOWNLOAD_ATTEMPT "
                f"resource={resource_label} url={url} attempt={attempt} outcome=retry "
                f"status={exc.code} delay_seconds={delay:.2f}"
            )
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionResetError) as exc:
            last_error = exc
            if attempt >= max_attempts:
                break
            delay = _retry_delay_seconds(attempt=attempt, delays=delays)
            print(
                "GDELT_DOWNLOAD_ATTEMPT "
                f"resource={resource_label} url={url} attempt={attempt} outcome=retry "
                f"exception={type(exc).__name__} delay_seconds={delay:.2f}"
            )
            time.sleep(delay)

    reason = type(last_error).__name__ if last_error is not None else "unknown"
    status = getattr(last_error, "code", None)
    status_text = f" status={status}" if status is not None else ""
    print(
        "GDELT_DOWNLOAD_ATTEMPT "
        f"resource={resource_label} url={url} attempt={max_attempts} "
        f"exception={reason}{status_text} delay_seconds=0.00 outcome=unavailable"
    )
    raise GdeltArchiveUnavailable(
        f"{resource_label} unavailable after {max_attempts} attempts ({reason}{status_text})"
    ) from last_error


def _download_backoff_seconds() -> tuple[float, ...]:
    raw_value = os.environ.get("GDELT_DOWNLOAD_BACKOFF_SECONDS")
    if raw_value is None:
        return DEFAULT_DOWNLOAD_BACKOFF_SECONDS
    delays = tuple(float(value.strip()) for value in raw_value.split(",") if value.strip())
    if not delays or any(delay < 0 for delay in delays):
        raise ValueError("GDELT_DOWNLOAD_BACKOFF_SECONDS must contain non-negative delays.")
    return delays


def _is_retryable_http_error(
    error: urllib.error.HTTPError,
    *,
    batch_time: datetime | None,
) -> bool:
    if error.code in RETRYABLE_HTTP_STATUSES:
        return True
    if error.code not in {400, 404}:
        return False
    if batch_time is None:
        return True
    recent_hours = int(
        os.environ.get("GDELT_RECENT_FILE_HOURS", str(DEFAULT_RECENT_FILE_HOURS))
    )
    return datetime.now(timezone.utc) - batch_time <= timedelta(hours=recent_hours)


def _retry_delay_seconds(
    *,
    attempt: int,
    delays: tuple[float, ...],
    retry_after: float | None = None,
) -> float:
    if retry_after is not None:
        return min(max(retry_after, 0.0), MAX_RETRY_AFTER_SECONDS)
    base_delay = delays[min(attempt - 1, len(delays) - 1)]
    jitter = random.uniform(-RETRY_JITTER_RATIO, RETRY_JITTER_RATIO)
    return max(0.0, base_delay * (1.0 + jitter))


def _retry_after_seconds(error: urllib.error.HTTPError) -> float | None:
    if error.code not in {429, 503} or error.headers is None:
        return None
    raw_value = error.headers.get("Retry-After")
    if not raw_value:
        return None
    try:
        return float(raw_value)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(raw_value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max(
                0.0,
                (retry_at.astimezone(timezone.utc) - datetime.now(timezone.utc)).total_seconds(),
            )
        except (TypeError, ValueError, OverflowError):
            return None


def _read_batch_archive(
    *,
    response_bytes: bytes,
    batch_time: datetime,
    ingestion_id: str,
    ingested_at: datetime,
    source_window_start: datetime,
    source_window_end: datetime,
    source_url: str,
) -> BatchFetchResult:
    result = BatchFetchResult()
    _configure_csv_field_size_limit()

    with zipfile.ZipFile(io.BytesIO(response_bytes)) as archive:
        member_names = archive.namelist()
        if not member_names:
            raise RuntimeError(
                f"GDELT {ZIP_READ_FAILURE_REASON} for {source_url}: ZIP contained no members."
            )

        member_name = member_names[0]
        if not member_name:
            raise RuntimeError(
                f"GDELT {ZIP_READ_FAILURE_REASON} for {source_url}: first ZIP member was empty."
            )

        with archive.open(member_name, "r") as zipped_file:
            text_stream = io.TextIOWrapper(zipped_file, encoding="utf-8", errors="replace")
            reader = csv.reader(text_stream, delimiter="\t")

            try:
                for row in reader:
                    result.total_rows_seen += 1

                    if len(row) != EXPECTED_GKG_ROW_WIDTH:
                        _mark_malformed(result, MALFORMED_REASON_WIDTH_MISMATCH)
                        continue

                    parsed_row, malformed_reason = _parse_gkg_row(
                        row=row,
                        ingestion_id=ingestion_id,
                        ingested_at=ingested_at,
                        source_window_start=source_window_start,
                        source_window_end=source_window_end,
                        source_url=source_url,
                    )
                    if malformed_reason is not None:
                        _mark_malformed(result, malformed_reason)
                        continue

                    if parsed_row is None:
                        _mark_malformed(result, MALFORMED_REASON_MISSING_SOURCE_RECORD_ID)
                        continue

                    result.records.append(parsed_row)
                    result.accepted_rows += 1
            except csv.Error as exc:
                raise RuntimeError(
                    f"GDELT CSV parse failed for {source_url}: {exc}. "
                    "Increase GDELT_CSV_FIELD_SIZE_LIMIT if upstream fields legitimately exceed "
                    f"{csv.field_size_limit()} bytes."
                ) from exc

    return result


def _configure_csv_field_size_limit() -> None:
    configured_limit = int(
        os.environ.get("GDELT_CSV_FIELD_SIZE_LIMIT", str(DEFAULT_CSV_FIELD_SIZE_LIMIT))
    )
    csv.field_size_limit(min(configured_limit, sys.maxsize))


def _mark_malformed(result: BatchFetchResult, reason: str) -> None:
    result.malformed_rows += 1
    result.malformed_reasons[reason] += 1


def _parse_gkg_row(
    *,
    row: list[str],
    ingestion_id: str,
    ingested_at: datetime,
    source_window_start: datetime,
    source_window_end: datetime,
    source_url: str,
) -> tuple[dict[str, Any] | None, str | None]:
    source_record_id = row[GKG_SOURCE_RECORD_ID].strip()
    if not source_record_id:
        return None, MALFORMED_REASON_MISSING_SOURCE_RECORD_ID

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
    try:
        published_at = _parse_gdelt_timestamp(row[GKG_PUBLISHED_AT])
    except ValueError:
        return None, MALFORMED_REASON_TIMESTAMP_PARSE_FAILURE

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

    return (
        {
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
            "published_at": published_at,
            "tone_raw": _extract_tone(row[GKG_TONE]),
            "positive_signal_raw": None,
            "negative_signal_raw": None,
            "raw_payload": json.dumps(payload, ensure_ascii=True),
        },
        None,
    )


def _enforce_run_guardrails(
    *,
    accepted_rows: int,
    total_rows_seen: int,
    malformed_rows: int,
    evaluate_low_volume: bool = True,
) -> RunGuardrailResult:
    if total_rows_seen == 0:
        raise RuntimeError("GDELT validation failed: downloaded file contained zero rows.")

    if accepted_rows == 0:
        raise RuntimeError("GDELT validation failed: no rows passed containment checks.")

    malformed_ratio = _calculate_ratio(malformed_rows, total_rows_seen)
    max_malformed_ratio = float(
        os.environ.get("GDELT_MAX_MALFORMED_RATIO", str(DEFAULT_MAX_MALFORMED_RATIO))
    )
    if malformed_ratio > max_malformed_ratio:
        raise RuntimeError(
            f"GDELT validation failed: malformed row ratio {malformed_ratio:.2%} exceeded "
            f"allowed threshold {max_malformed_ratio:.2%}."
        )

    if not evaluate_low_volume:
        return RunGuardrailResult()

    recent_counts = _fetch_recent_accepted_row_counts()
    baseline_runs = int(os.getenv("GDELT_BASELINE_RUNS", str(DEFAULT_BASELINE_RUNS)))
    if len(recent_counts) < baseline_runs:
        return RunGuardrailResult(low_volume=False)

    average_recent_count = sum(recent_counts) / len(recent_counts)
    min_accepted_ratio = float(
        os.environ.get("GDELT_MIN_ACCEPTED_ROW_RATIO", str(DEFAULT_MIN_ACCEPTED_ROW_RATIO))
    )
    minimum_allowed_rows = average_recent_count * min_accepted_ratio
    low_volume = accepted_rows < minimum_allowed_rows

    if low_volume:
        message = (
            f"GDELT validation warning: accepted row count {accepted_rows} fell below "
            f"{min_accepted_ratio:.0%} of recent average {average_recent_count:.1f}."
        )
        action = os.environ.get(
            "GDELT_LOW_ACCEPTED_ROW_ACTION",
            DEFAULT_LOW_ACCEPTED_ROW_ACTION,
        ).strip().lower()
        if action == "fail":
            raise RuntimeError(message.replace("warning", "failed"))
        print(message)
    return RunGuardrailResult(
        low_volume=low_volume,
        baseline_average_accepted_row_count=average_recent_count,
        low_volume_threshold=minimum_allowed_rows,
    )


def _calculate_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _fetch_recent_accepted_row_counts() -> list[int]:
    imported_bigquery = _import_bigquery()
    project_id = _resolve_project_id()
    if imported_bigquery is None or not project_id:
        return []

    bronze_table_fqn = _table_fqn(
        project_id,
        os.getenv("TIDINGSIQ_BRONZE_TABLE", DEFAULT_BRONZE_TABLE),
    )
    history_runs = int(os.getenv("GDELT_BASELINE_RUNS", str(DEFAULT_BASELINE_RUNS)))
    expected_files = int(os.getenv("GDELT_MAX_FILES", str(DEFAULT_MAX_FILES)))

    sql = f"""
with recent_runs as (
  select
    ingestion_id,
    count(*) as accepted_row_count,
    max(ingested_at) as latest_ingested_at,
    coalesce(
      logical_or(bronze_run_is_complete),
      max(bronze_run_downloaded_file_count) >= @expected_files
    ) as is_complete,
    coalesce(logical_or(bronze_run_is_backfill), false) as is_backfill
  from `{bronze_table_fqn}`
  group by ingestion_id
)
select accepted_row_count
from recent_runs
where is_complete and not is_backfill
order by latest_ingested_at desc, ingestion_id desc
limit @history_runs
"""
    try:
        client = imported_bigquery.Client(project=project_id)
        rows = client.query(
            sql,
            job_config=imported_bigquery.QueryJobConfig(
                query_parameters=[
                    imported_bigquery.ScalarQueryParameter(
                        "history_runs",
                        "INT64",
                        history_runs,
                    ),
                    imported_bigquery.ScalarQueryParameter(
                        "expected_files",
                        "INT64",
                        expected_files,
                    ),
                ]
            ),
        ).result()
    except Exception:
        return []

    counts: list[int] = []
    for row in rows:
        accepted_row_count = row["accepted_row_count"]
        if accepted_row_count is not None:
            counts.append(int(accepted_row_count))
    return counts


def _import_bigquery():
    try:
        from google.cloud import bigquery as imported_bigquery
    except ImportError:  # pragma: no cover - runtime guard
        return None
    return imported_bigquery


def _resolve_project_id() -> str | None:
    return (
        os.getenv("BRUIN_PROJECT_ID")
        or os.getenv("TIDINGSIQ_GCP_PROJECT")
        or os.getenv("GOOGLE_CLOUD_PROJECT")
    )


def _table_fqn(project_id: str, table_name: str) -> str:
    normalized = table_name.strip().strip("`")
    if normalized.count(".") == 1:
        return f"{project_id}.{normalized}"
    if normalized.count(".") == 2:
        return normalized
    raise ValueError("table name must be dataset.table or project.dataset.table")


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
            "bronze_run_total_row_count": pd.Series(dtype="Int64"),
            "bronze_run_accepted_row_count": pd.Series(dtype="Int64"),
            "bronze_run_malformed_row_count": pd.Series(dtype="Int64"),
            "bronze_run_malformed_ratio": pd.Series(dtype="float64"),
            "bronze_run_expected_file_count": pd.Series(dtype="Int64"),
            "bronze_run_downloaded_file_count": pd.Series(dtype="Int64"),
            "bronze_run_missing_file_count": pd.Series(dtype="Int64"),
            "bronze_run_is_complete": pd.Series(dtype="boolean"),
            "bronze_run_is_backfill": pd.Series(dtype="boolean"),
            "bronze_run_low_volume": pd.Series(dtype="boolean"),
            "bronze_run_baseline_average_accepted_row_count": pd.Series(dtype="float64"),
            "bronze_run_low_volume_threshold": pd.Series(dtype="float64"),
            "raw_payload": pd.Series(dtype="string"),
        }
    )
