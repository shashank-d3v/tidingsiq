from __future__ import annotations

import csv
import importlib.util
import io
import os
import pathlib
import sys
import types
import urllib.error
import unittest
import zipfile
from datetime import datetime, timezone
from unittest import mock


MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "assets"
    / "bronze"
    / "gdelt_news_raw.py"
)
SPEC = importlib.util.spec_from_file_location("gdelt_news_raw", MODULE_PATH)
assert SPEC and SPEC.loader
_PANDAS_STUB_INSERTED = "pandas" not in sys.modules
if _PANDAS_STUB_INSERTED:
    sys.modules["pandas"] = types.SimpleNamespace(DataFrame=object, Series=object)
gdelt_news_raw = importlib.util.module_from_spec(SPEC)
sys.modules["gdelt_news_raw"] = gdelt_news_raw
SPEC.loader.exec_module(gdelt_news_raw)
if _PANDAS_STUB_INSERTED:
    sys.modules.pop("pandas", None)


class GdeltNewsRawTest(unittest.TestCase):
    def _valid_batch_time(self) -> datetime:
        return datetime(2026, 4, 2, 16, 45, tzinfo=timezone.utc)

    def _valid_row(self, *, timestamp: str = "20260402164500") -> list[str]:
        row = [""] * gdelt_news_raw.EXPECTED_GKG_ROW_WIDTH
        row[gdelt_news_raw.GKG_SOURCE_RECORD_ID] = "record-1"
        row[gdelt_news_raw.GKG_PUBLISHED_AT] = timestamp
        row[gdelt_news_raw.GKG_SOURCE_COLLECTION_IDENTIFIER] = "1"
        row[gdelt_news_raw.GKG_SOURCE_NAME] = "Example.com"
        row[gdelt_news_raw.GKG_DOCUMENT_IDENTIFIER] = "https://example.com/news/story"
        row[gdelt_news_raw.GKG_V2_COUNTS] = "COUNT"
        row[gdelt_news_raw.GKG_V2_THEMES] = "THEME"
        row[gdelt_news_raw.GKG_V2_LOCATIONS] = "1#American#US#US##39.82#-98.57#US#1"
        row[gdelt_news_raw.GKG_V2_PERSONS] = "PERSON"
        row[gdelt_news_raw.GKG_V2_ORGANIZATIONS] = "ORG"
        row[gdelt_news_raw.GKG_TONE] = "1.5,0,0,0,0,0,0"
        row[gdelt_news_raw.GKG_GCAM] = "GCAM"
        row[gdelt_news_raw.GKG_ALL_NAMES] = "ALL_NAMES"
        row[gdelt_news_raw.GKG_AMOUNTS] = "AMOUNTS"
        row[gdelt_news_raw.GKG_TRANSLATION_INFO] = "source:foo;srclc:eng;"
        row[gdelt_news_raw.GKG_EXTRAS] = "<PAGE_TITLE>Markets rally again</PAGE_TITLE>"
        return row

    def _zip_bytes(self, rows: list[list[str]] | None, *, member_name: str = "20260402164500.gkg.csv") -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            if rows is not None:
                payload = "\n".join("\t".join(row) for row in rows)
                archive.writestr(member_name, payload)
        return buffer.getvalue()

    def test_build_gkg_batch_url_defaults_to_secure_feed(self) -> None:
        batch_time = self._valid_batch_time()

        url = gdelt_news_raw._build_gkg_batch_url(batch_time)

        self.assertEqual(
            url,
            "https://data.gdeltproject.org/gdeltv2/20260402164500.gkg.csv.zip",
        )

    def test_build_gkg_batch_url_honors_override(self) -> None:
        batch_time = self._valid_batch_time()

        with mock.patch.dict(
            "os.environ", {"GDELT_BASE_URL": "https://example.com/feed/"}, clear=False
        ):
            url = gdelt_news_raw._build_gkg_batch_url(batch_time)

        self.assertEqual(url, "https://example.com/feed/20260402164500.gkg.csv.zip")

    def test_build_gkg_batch_url_rejects_non_gdelt_host_in_deployed_runtime(self) -> None:
        batch_time = self._valid_batch_time()

        with mock.patch.dict(
            "os.environ",
            {
                "GDELT_BASE_URL": "https://example.com/feed/",
                "CLOUD_RUN_JOB": "tidingsiq-pipeline",
            },
            clear=False,
        ):
            with self.assertRaisesRegex(ValueError, "example.com"):
                gdelt_news_raw._build_gkg_batch_url(batch_time)

    def test_build_gkg_batch_url_allows_expected_host_override_in_deployed_runtime(self) -> None:
        batch_time = self._valid_batch_time()

        with mock.patch.dict(
            "os.environ",
            {
                "GDELT_BASE_URL": "https://data.gdeltproject.org/gdeltv2/",
                "CLOUD_RUN_JOB": "tidingsiq-pipeline",
            },
            clear=False,
        ):
            url = gdelt_news_raw._build_gkg_batch_url(batch_time)

        self.assertEqual(
            url,
            "https://data.gdeltproject.org/gdeltv2/20260402164500.gkg.csv.zip",
        )

    def test_validate_gkg_download_url_rejects_wrong_filename_pattern(self) -> None:
        batch_time = self._valid_batch_time()

        with self.assertRaisesRegex(ValueError, "filename"):
            gdelt_news_raw._validate_gkg_download_url(
                "http://data.gdeltproject.org/gdeltv2/latest.zip",
                batch_time,
            )

    def test_extract_language_raw_from_translation_info(self) -> None:
        language = gdelt_news_raw._extract_language_raw("source:foo;srclc:eng;")

        self.assertEqual(language, "en")

    def test_extract_language_raw_returns_none_for_malformed_translation_info(self) -> None:
        language = gdelt_news_raw._extract_language_raw("source:foo;lang:english;")

        self.assertIsNone(language)

    def test_resolve_language_prefers_native_value(self) -> None:
        language, status = gdelt_news_raw._resolve_language(
            language_raw="en",
            title="Ignored because native value exists",
        )

        self.assertEqual((language, status), ("en", "native"))

    def test_resolve_language_falls_back_to_inference(self) -> None:
        with mock.patch.object(
            gdelt_news_raw,
            "_infer_language_from_title",
            return_value="fr",
        ):
            language, status = gdelt_news_raw._resolve_language(
                language_raw=None,
                title="Bonjour le monde",
            )

        self.assertEqual((language, status), ("fr", "inferred"))

    def test_resolve_language_returns_und_when_unresolved(self) -> None:
        with mock.patch.object(
            gdelt_news_raw,
            "_infer_language_from_title",
            return_value=None,
        ):
            language, status = gdelt_news_raw._resolve_language(
                language_raw=None,
                title="??",
            )

        self.assertEqual((language, status), ("und", "undetermined"))

    def test_infer_language_from_title_respects_detector_confidence(self) -> None:
        class FakeConfidence:
            def __init__(self, value: float) -> None:
                self.value = value
                self.language = types.SimpleNamespace(
                    iso_code_639_1=types.SimpleNamespace(name="EN")
                )

        fake_detector = types.SimpleNamespace(
            compute_language_confidence_values=lambda _: [FakeConfidence(0.91)]
        )

        with mock.patch.object(
            gdelt_news_raw,
            "_get_language_detector",
            return_value=fake_detector,
        ):
            language = gdelt_news_raw._infer_language_from_title(
                "Markets rally as inflation cools again"
            )

        self.assertEqual(language, "en")

    def test_infer_language_from_title_returns_none_when_confidence_is_too_low(self) -> None:
        class FakeConfidence:
            def __init__(self, value: float) -> None:
                self.value = value
                self.language = types.SimpleNamespace(
                    iso_code_639_1=types.SimpleNamespace(name="EN")
                )

        fake_detector = types.SimpleNamespace(
            compute_language_confidence_values=lambda _: [FakeConfidence(0.25)]
        )

        with mock.patch.object(
            gdelt_news_raw,
            "_get_language_detector",
            return_value=fake_detector,
        ):
            language = gdelt_news_raw._infer_language_from_title(
                "Markets rally as inflation cools again"
            )

        self.assertIsNone(language)

    def test_extract_mentioned_country_uses_most_frequent_country(self) -> None:
        v2_locations = (
            "1#American#US#US##39.828175#-98.5795#US#758;"
            "2#Kansas, United States#US#USKS##38.5111#-96.8005#KS#6;"
            "4#Ottawa, Ontario, Canada#CA#CA08#12755#45.4167#-75.7#-57076#1"
        )

        with mock.patch.object(
            gdelt_news_raw,
            "_country_name_from_code",
            side_effect=lambda code: {"US": "United States", "CA": "Canada"}.get(code),
        ):
            code, name, status = gdelt_news_raw._extract_mentioned_country(v2_locations)

        self.assertEqual((code, name, status), ("US", "United States", "v2_locations"))

    def test_extract_mentioned_country_returns_unknown_for_malformed_locations(self) -> None:
        code, name, status = gdelt_news_raw._extract_mentioned_country("bad-data-without-hash")

        self.assertEqual((code, name, status), ("ZZ", "Unknown", "undetermined"))

    def test_extract_source_domain_prefers_url_host(self) -> None:
        source_domain = gdelt_news_raw._extract_source_domain(
            "https://www.example.com/news/story",
            "Example.com",
        )

        self.assertEqual(source_domain, "example.com")

    def test_extract_source_domain_falls_back_to_source_name(self) -> None:
        source_domain = gdelt_news_raw._extract_source_domain(None, "www.Example.com")

        self.assertEqual(source_domain, "example.com")

    def test_fetch_batch_rows_returns_missing_result_for_404(self) -> None:
        with mock.patch.object(
            gdelt_news_raw,
            "_download_bytes",
            side_effect=urllib.error.HTTPError(
                url="http://data.gdeltproject.org/gdeltv2/20260402164500.gkg.csv.zip",
                code=404,
                msg="Not Found",
                hdrs=None,
                fp=None,
            ),
        ):
            result = gdelt_news_raw._fetch_batch_rows(
                batch_time=self._valid_batch_time(),
                ingestion_id="ingestion",
                ingested_at=datetime(2026, 4, 2, 17, 0, tzinfo=timezone.utc),
                source_window_start=datetime(2026, 4, 2, 16, 0, tzinfo=timezone.utc),
                source_window_end=datetime(2026, 4, 2, 16, 45, tzinfo=timezone.utc),
            )

        self.assertTrue(result.was_missing)
        self.assertEqual(result.accepted_rows, 0)

    def test_fetch_batch_rows_fails_on_corrupt_zip(self) -> None:
        expected_url = "http://data.gdeltproject.org/gdeltv2/20260402164500.gkg.csv.zip"
        with mock.patch.object(
            gdelt_news_raw,
            "_download_bytes",
            return_value=(b"not-a-zip", expected_url),
        ):
            with self.assertRaisesRegex(RuntimeError, gdelt_news_raw.ZIP_READ_FAILURE_REASON):
                gdelt_news_raw._fetch_batch_rows(
                    batch_time=self._valid_batch_time(),
                    ingestion_id="ingestion",
                    ingested_at=datetime(2026, 4, 2, 17, 0, tzinfo=timezone.utc),
                    source_window_start=datetime(2026, 4, 2, 16, 0, tzinfo=timezone.utc),
                    source_window_end=datetime(2026, 4, 2, 16, 45, tzinfo=timezone.utc),
                )

    def test_fetch_batch_rows_fails_on_empty_zip(self) -> None:
        expected_url = "http://data.gdeltproject.org/gdeltv2/20260402164500.gkg.csv.zip"
        with mock.patch.object(
            gdelt_news_raw,
            "_download_bytes",
            return_value=(self._zip_bytes(None), expected_url),
        ):
            with self.assertRaisesRegex(RuntimeError, gdelt_news_raw.ZIP_READ_FAILURE_REASON):
                gdelt_news_raw._fetch_batch_rows(
                    batch_time=self._valid_batch_time(),
                    ingestion_id="ingestion",
                    ingested_at=datetime(2026, 4, 2, 17, 0, tzinfo=timezone.utc),
                    source_window_start=datetime(2026, 4, 2, 16, 0, tzinfo=timezone.utc),
                    source_window_end=datetime(2026, 4, 2, 16, 45, tzinfo=timezone.utc),
                )

    def test_fetch_batch_rows_fails_when_downloaded_archive_has_zero_accepted_rows(self) -> None:
        expected_url = "https://data.gdeltproject.org/gdeltv2/20260402164500.gkg.csv.zip"
        malformed_row = self._valid_row()[:-1]
        with mock.patch.object(
            gdelt_news_raw,
            "_download_bytes",
            return_value=(self._zip_bytes([malformed_row]), expected_url),
        ):
            with self.assertRaisesRegex(RuntimeError, "zero accepted rows"):
                gdelt_news_raw._fetch_batch_rows(
                    batch_time=self._valid_batch_time(),
                    ingestion_id="ingestion",
                    ingested_at=datetime(2026, 4, 2, 17, 0, tzinfo=timezone.utc),
                    source_window_start=datetime(2026, 4, 2, 16, 0, tzinfo=timezone.utc),
                    source_window_end=datetime(2026, 4, 2, 16, 45, tzinfo=timezone.utc),
                )

    def test_fetch_batch_rows_fails_when_first_member_is_unreadable(self) -> None:
        expected_url = "http://data.gdeltproject.org/gdeltv2/20260402164500.gkg.csv.zip"
        with mock.patch.object(
            gdelt_news_raw,
            "_download_bytes",
            return_value=(self._zip_bytes([self._valid_row()]), expected_url),
        ):
            with mock.patch.object(gdelt_news_raw.zipfile.ZipFile, "open", side_effect=OSError("boom")):
                with self.assertRaisesRegex(RuntimeError, gdelt_news_raw.ZIP_READ_FAILURE_REASON):
                    gdelt_news_raw._fetch_batch_rows(
                        batch_time=self._valid_batch_time(),
                        ingestion_id="ingestion",
                        ingested_at=datetime(2026, 4, 2, 17, 0, tzinfo=timezone.utc),
                        source_window_start=datetime(2026, 4, 2, 16, 0, tzinfo=timezone.utc),
                        source_window_end=datetime(2026, 4, 2, 16, 45, tzinfo=timezone.utc),
                    )

    def test_read_batch_archive_counts_short_and_wide_rows_as_malformed(self) -> None:
        short_row = self._valid_row()[:-1]
        wide_row = self._valid_row() + ["EXTRA"]
        result = gdelt_news_raw._read_batch_archive(
            response_bytes=self._zip_bytes([self._valid_row(), short_row, wide_row]),
            batch_time=self._valid_batch_time(),
            ingestion_id="ingestion",
            ingested_at=datetime(2026, 4, 2, 17, 0, tzinfo=timezone.utc),
            source_window_start=datetime(2026, 4, 2, 16, 0, tzinfo=timezone.utc),
            source_window_end=datetime(2026, 4, 2, 16, 45, tzinfo=timezone.utc),
            source_url="http://data.gdeltproject.org/gdeltv2/20260402164500.gkg.csv.zip",
        )

        self.assertEqual(result.total_rows_seen, 3)
        self.assertEqual(result.accepted_rows, 1)
        self.assertEqual(result.malformed_rows, 2)
        self.assertEqual(
            result.malformed_reasons[gdelt_news_raw.MALFORMED_REASON_WIDTH_MISMATCH],
            2,
        )

    def test_read_batch_archive_counts_timestamp_parse_failures(self) -> None:
        bad_timestamp_row = self._valid_row(timestamp="not-a-timestamp")
        result = gdelt_news_raw._read_batch_archive(
            response_bytes=self._zip_bytes([self._valid_row(), bad_timestamp_row]),
            batch_time=self._valid_batch_time(),
            ingestion_id="ingestion",
            ingested_at=datetime(2026, 4, 2, 17, 0, tzinfo=timezone.utc),
            source_window_start=datetime(2026, 4, 2, 16, 0, tzinfo=timezone.utc),
            source_window_end=datetime(2026, 4, 2, 16, 45, tzinfo=timezone.utc),
            source_url="http://data.gdeltproject.org/gdeltv2/20260402164500.gkg.csv.zip",
        )

        self.assertEqual(result.total_rows_seen, 2)
        self.assertEqual(result.accepted_rows, 1)
        self.assertEqual(result.malformed_rows, 1)
        self.assertEqual(
            result.malformed_reasons[gdelt_news_raw.MALFORMED_REASON_TIMESTAMP_PARSE_FAILURE],
            1,
        )

    def test_read_batch_archive_accepts_large_gdelt_fields(self) -> None:
        row = self._valid_row()
        row[gdelt_news_raw.GKG_EXTRAS] = f"<PAGE_TITLE>{'A' * 150_000}</PAGE_TITLE>"
        previous_limit = csv.field_size_limit()
        try:
            with mock.patch.dict(
                "os.environ",
                {"GDELT_CSV_FIELD_SIZE_LIMIT": "200000"},
                clear=False,
            ):
                result = gdelt_news_raw._read_batch_archive(
                    response_bytes=self._zip_bytes([row]),
                    batch_time=self._valid_batch_time(),
                    ingestion_id="ingestion",
                    ingested_at=datetime(2026, 4, 2, 17, 0, tzinfo=timezone.utc),
                    source_window_start=datetime(2026, 4, 2, 16, 0, tzinfo=timezone.utc),
                    source_window_end=datetime(2026, 4, 2, 16, 45, tzinfo=timezone.utc),
                    source_url="http://data.gdeltproject.org/gdeltv2/20260402164500.gkg.csv.zip",
                )
        finally:
            csv.field_size_limit(previous_limit)

        self.assertEqual(result.accepted_rows, 1)
        self.assertEqual(result.malformed_rows, 0)

    def test_read_batch_archive_wraps_unrecoverable_csv_errors(self) -> None:
        row = self._valid_row()
        row[gdelt_news_raw.GKG_EXTRAS] = f"<PAGE_TITLE>{'A' * 128}</PAGE_TITLE>"
        previous_limit = csv.field_size_limit()
        try:
            with mock.patch.dict(
                "os.environ",
                {"GDELT_CSV_FIELD_SIZE_LIMIT": "64"},
                clear=False,
            ):
                with self.assertRaisesRegex(RuntimeError, "GDELT CSV parse failed"):
                    gdelt_news_raw._read_batch_archive(
                        response_bytes=self._zip_bytes([row]),
                        batch_time=self._valid_batch_time(),
                        ingestion_id="ingestion",
                        ingested_at=datetime(2026, 4, 2, 17, 0, tzinfo=timezone.utc),
                        source_window_start=datetime(2026, 4, 2, 16, 0, tzinfo=timezone.utc),
                        source_window_end=datetime(2026, 4, 2, 16, 45, tzinfo=timezone.utc),
                        source_url="http://data.gdeltproject.org/gdeltv2/20260402164500.gkg.csv.zip",
                    )
        finally:
            csv.field_size_limit(previous_limit)

    def test_enforce_run_guardrails_fails_on_high_malformed_ratio(self) -> None:
        with mock.patch.object(gdelt_news_raw, "_fetch_recent_accepted_row_counts", return_value=[]):
            with mock.patch.dict("os.environ", {"GDELT_MAX_MALFORMED_RATIO": "0.10"}, clear=False):
                with self.assertRaisesRegex(RuntimeError, "malformed row ratio"):
                    gdelt_news_raw._enforce_run_guardrails(
                        accepted_rows=8,
                        total_rows_seen=10,
                        malformed_rows=2,
                    )

    def test_enforce_run_guardrails_warns_on_recent_row_count_collapse_by_default(self) -> None:
        with mock.patch.object(
            gdelt_news_raw,
            "_fetch_recent_accepted_row_counts",
            return_value=[100, 120, 110, 90, 100],
        ):
            with mock.patch("builtins.print") as print_mock:
                gdelt_news_raw._enforce_run_guardrails(
                    accepted_rows=40,
                    total_rows_seen=40,
                    malformed_rows=0,
                )
        print_mock.assert_called_once()
        self.assertIn("accepted row count 40", print_mock.call_args.args[0])

    def test_enforce_run_guardrails_can_fail_on_recent_row_count_collapse(self) -> None:
        with mock.patch.object(
            gdelt_news_raw,
            "_fetch_recent_accepted_row_counts",
            return_value=[100, 120, 110, 90, 100],
        ):
            with mock.patch.dict(
                "os.environ",
                {"GDELT_LOW_ACCEPTED_ROW_ACTION": "fail"},
                clear=False,
            ):
                with self.assertRaisesRegex(RuntimeError, "accepted row count 40"):
                    gdelt_news_raw._enforce_run_guardrails(
                        accepted_rows=40,
                        total_rows_seen=40,
                        malformed_rows=0,
                    )

    def test_enforce_run_guardrails_accepts_healthy_payload(self) -> None:
        with mock.patch.object(
            gdelt_news_raw,
            "_fetch_recent_accepted_row_counts",
            return_value=[100, 120, 110, 90, 100],
        ):
            gdelt_news_raw._enforce_run_guardrails(
                accepted_rows=80,
                total_rows_seen=82,
                malformed_rows=2,
            )

    def test_resolve_requested_window_falls_back_from_same_day_midnight_bruin_interval(self) -> None:
        class FakeDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 4, 20, 6, 30, tzinfo=tz or timezone.utc)

        with mock.patch.object(gdelt_news_raw, "datetime", FakeDateTime), mock.patch.object(
            gdelt_news_raw,
            "_fetch_latest_manifest_batch_time",
            return_value=datetime(2026, 4, 20, 6, 30, tzinfo=timezone.utc),
        ):
            with mock.patch.dict(
                os.environ,
                {
                    "BRUIN_START_DATE": "2026-04-20T00:00:00Z",
                    "BRUIN_END_DATE": "2026-04-20T00:00:00Z",
                    "CLOUD_RUN_JOB": "tidingsiq-pipeline",
                },
                clear=False,
            ):
                start_dt, end_dt = gdelt_news_raw._resolve_requested_window()

        self.assertEqual(start_dt, datetime(2026, 4, 20, 4, 45, tzinfo=timezone.utc))
        self.assertEqual(end_dt, datetime(2026, 4, 20, 5, 30, tzinfo=timezone.utc))

    def test_resolve_requested_window_keeps_historical_zero_width_interval_outside_deployed_runtime(self) -> None:
        class FakeDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 4, 20, 6, 30, tzinfo=tz or timezone.utc)

        with mock.patch.object(gdelt_news_raw, "datetime", FakeDateTime):
            with mock.patch.dict(
                os.environ,
                {
                    "BRUIN_START_DATE": "2026-04-19T00:00:00Z",
                    "BRUIN_END_DATE": "2026-04-19T00:00:00Z",
                },
                clear=False,
            ):
                start_dt, end_dt = gdelt_news_raw._resolve_requested_window()

        self.assertEqual(start_dt, datetime(2026, 4, 19, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(end_dt, datetime(2026, 4, 19, 0, 0, tzinfo=timezone.utc))

    def test_resolve_requested_window_keeps_current_zero_width_interval_in_deployed_runtime(self) -> None:
        class FakeDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 4, 20, 6, 30, tzinfo=tz or timezone.utc)

        with mock.patch.object(gdelt_news_raw, "datetime", FakeDateTime):
            with mock.patch.dict(
                os.environ,
                {
                    "BRUIN_START_DATE": "2026-04-20T06:20:00Z",
                    "BRUIN_END_DATE": "2026-04-20T06:20:00Z",
                    "CLOUD_RUN_JOB": "tidingsiq-pipeline",
                    "GDELT_EXPLICIT_INTERVAL_REQUESTED": "true",
                },
                clear=False,
            ):
                start_dt, end_dt = gdelt_news_raw._resolve_requested_window()

        self.assertEqual(start_dt, datetime(2026, 4, 20, 6, 15, tzinfo=timezone.utc))
        self.assertEqual(end_dt, datetime(2026, 4, 20, 6, 15, tzinfo=timezone.utc))

    def test_parse_manifest_selects_gkg_entry(self) -> None:
        manifest = "\n".join(
            [
                "1 hash http://data.gdeltproject.org/gdeltv2/20260420060000.export.CSV.zip",
                "2 hash http://data.gdeltproject.org/gdeltv2/20260420060000.mentions.CSV.zip",
                "3 hash http://data.gdeltproject.org/gdeltv2/20260420060000.gkg.csv.zip",
            ]
        )

        result = gdelt_news_raw._parse_manifest_gkg_batch_time(
            manifest,
            current_time=datetime(2026, 4, 20, 6, 5, tzinfo=timezone.utc),
        )

        self.assertEqual(result, datetime(2026, 4, 20, 6, 0, tzinfo=timezone.utc))

    def test_manifest_validation_rejects_invalid_gkg_entries(self) -> None:
        current_time = datetime(2026, 4, 20, 6, 5, tzinfo=timezone.utc)
        invalid_manifests = {
            "host": "3 hash https://example.com/gdeltv2/20260420060000.gkg.csv.zip",
            "filename": "3 hash https://data.gdeltproject.org/gdeltv2/latest.gkg.csv.zip",
            "boundary": "3 hash https://data.gdeltproject.org/gdeltv2/20260420060700.gkg.csv.zip",
            "future": "3 hash https://data.gdeltproject.org/gdeltv2/20260420063000.gkg.csv.zip",
            "next_boundary": "3 hash https://data.gdeltproject.org/gdeltv2/20260420061500.gkg.csv.zip",
            "missing": "3 hash https://data.gdeltproject.org/gdeltv2/20260420060000.export.CSV.zip",
        }

        for case_name, manifest in invalid_manifests.items():
            with self.subTest(case_name=case_name):
                with self.assertRaises(ValueError):
                    gdelt_news_raw._parse_manifest_gkg_batch_time(
                        manifest,
                        current_time=current_time,
                    )

    def test_manifest_window_contains_exactly_four_batches(self) -> None:
        with mock.patch.object(
            gdelt_news_raw,
            "_fetch_latest_manifest_batch_time",
            return_value=datetime(2026, 4, 20, 6, 0, tzinfo=timezone.utc),
        ), mock.patch.dict(os.environ, {}, clear=True):
            result = gdelt_news_raw._resolve_rolling_window(
                datetime(2026, 4, 20, 6, 5, tzinfo=timezone.utc)
            )

        self.assertEqual(result.anchor, "manifest")
        self.assertEqual(
            result.batch_times,
            (
                datetime(2026, 4, 20, 4, 15, tzinfo=timezone.utc),
                datetime(2026, 4, 20, 4, 30, tzinfo=timezone.utc),
                datetime(2026, 4, 20, 4, 45, tzinfo=timezone.utc),
                datetime(2026, 4, 20, 5, 0, tzinfo=timezone.utc),
            ),
        )

    def test_manifest_failure_uses_publication_lag(self) -> None:
        with mock.patch.object(
            gdelt_news_raw,
            "_fetch_latest_manifest_batch_time",
            side_effect=ValueError("bad manifest"),
        ), mock.patch.dict(
            os.environ,
            {"GDELT_PUBLICATION_LAG_MINUTES": "60"},
            clear=True,
        ):
            result = gdelt_news_raw._resolve_rolling_window(
                datetime(2026, 4, 20, 6, 7, tzinfo=timezone.utc)
            )

        self.assertEqual(result.anchor, "lag")
        self.assertEqual(result.end_dt, datetime(2026, 4, 20, 5, 0, tzinfo=timezone.utc))

    def test_explicit_historical_window_bypasses_manifest(self) -> None:
        with mock.patch.object(
            gdelt_news_raw,
            "_fetch_latest_manifest_batch_time",
        ) as manifest_mock, mock.patch.dict(
            os.environ,
            {
                "BRUIN_START_DATE": "2026-04-19T23:45:00Z",
                "BRUIN_END_DATE": "2026-04-20T00:30:00Z",
            },
            clear=True,
        ):
            result = gdelt_news_raw._resolve_window_selection()

        manifest_mock.assert_not_called()
        self.assertEqual(result.anchor, "explicit")
        self.assertTrue(result.is_backfill)
        self.assertEqual(len(result.batch_times), 4)

    def test_bruin_datetime_variables_preserve_intraday_backfill_boundaries(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "BRUIN_START_DATE": "2026-08-20",
                "BRUIN_END_DATE": "2026-08-21",
                "BRUIN_START_DATETIME": "2026-08-20T23:45:00",
                "BRUIN_END_DATETIME": "2026-08-21T00:30:00",
            },
            clear=True,
        ):
            result = gdelt_news_raw._resolve_window_selection()

        self.assertEqual(result.start_dt, datetime(2026, 8, 20, 23, 45, tzinfo=timezone.utc))
        self.assertEqual(result.end_dt, datetime(2026, 8, 21, 0, 30, tzinfo=timezone.utc))
        self.assertEqual(
            [batch.strftime("%Y%m%d%H%M%S") for batch in result.batch_times],
            ["20260820234500", "20260821000000", "20260821001500", "20260821003000"],
        )

    def test_deployed_scheduled_bruin_interval_still_uses_live_manifest(self) -> None:
        with mock.patch.object(
            gdelt_news_raw,
            "_fetch_latest_manifest_batch_time",
            return_value=datetime(2026, 8, 26, 13, 45, tzinfo=timezone.utc),
        ) as manifest_mock, mock.patch.dict(
            os.environ,
            {
                "CLOUD_RUN_JOB": "tidingsiq-pipeline",
                "GDELT_EXPLICIT_INTERVAL_REQUESTED": "false",
                "BRUIN_START_DATETIME": "2026-08-25T00:00:00",
                "BRUIN_END_DATETIME": "2026-08-25T23:59:59",
            },
            clear=True,
        ):
            result = gdelt_news_raw._resolve_window_selection()

        manifest_mock.assert_called_once()
        self.assertEqual(result.anchor, "manifest")
        self.assertFalse(result.is_backfill)
        self.assertEqual(result.end_dt, datetime(2026, 8, 26, 13, 45, tzinfo=timezone.utc))

    def test_deployed_cli_interval_marker_keeps_explicit_backfill(self) -> None:
        with mock.patch.object(
            gdelt_news_raw,
            "_fetch_latest_manifest_batch_time",
        ) as manifest_mock, mock.patch.dict(
            os.environ,
            {
                "CLOUD_RUN_JOB": "tidingsiq-pipeline",
                "GDELT_EXPLICIT_INTERVAL_REQUESTED": "true",
                "BRUIN_START_DATETIME": "2026-08-20T23:45:00",
                "BRUIN_END_DATETIME": "2026-08-21T00:30:00",
            },
            clear=True,
        ):
            result = gdelt_news_raw._resolve_window_selection()

        manifest_mock.assert_not_called()
        self.assertEqual(result.anchor, "explicit")
        self.assertTrue(result.is_backfill)
        self.assertEqual(
            [batch.strftime("%Y%m%d%H%M%S") for batch in result.batch_times],
            ["20260820234500", "20260821000000", "20260821001500", "20260821003000"],
        )

    def test_download_retries_transient_http_error_then_succeeds(self) -> None:
        url = "https://data.gdeltproject.org/gdeltv2/lastupdate.txt"
        http_error = urllib.error.HTTPError(url, 503, "Unavailable", {}, None)
        with mock.patch.object(
            gdelt_news_raw,
            "_download_bytes",
            side_effect=[http_error, (b"ok", url)],
        ) as download_mock, mock.patch.object(
            gdelt_news_raw.time,
            "sleep",
        ) as sleep_mock, mock.patch.object(
            gdelt_news_raw.random,
            "uniform",
            return_value=0.0,
        ), mock.patch.dict(
            os.environ,
            {
                "GDELT_DOWNLOAD_MAX_ATTEMPTS": "4",
                "GDELT_DOWNLOAD_BACKOFF_SECONDS": "5,15,30",
            },
            clear=True,
        ):
            result = gdelt_news_raw._download_bytes_with_retry(
                url,
                resource_label="manifest",
            )

        self.assertEqual(result, (b"ok", url))
        self.assertEqual(download_mock.call_count, 2)
        sleep_mock.assert_called_once_with(5.0)

    def test_download_does_not_retry_permanent_http_error(self) -> None:
        url = "https://data.gdeltproject.org/gdeltv2/lastupdate.txt"
        with mock.patch.object(
            gdelt_news_raw,
            "_download_bytes",
            side_effect=urllib.error.HTTPError(url, 403, "Forbidden", {}, None),
        ) as download_mock, mock.patch.object(gdelt_news_raw.time, "sleep"):
            with self.assertRaises(urllib.error.HTTPError):
                gdelt_news_raw._download_bytes_with_retry(
                    url,
                    resource_label="manifest",
                )

        download_mock.assert_called_once()

    def test_recent_404_retries_then_succeeds(self) -> None:
        batch_time = datetime.now(timezone.utc)
        url = f"https://data.gdeltproject.org/gdeltv2/{batch_time:%Y%m%d%H%M%S}.gkg.csv.zip"
        http_error = urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        with mock.patch.object(
            gdelt_news_raw,
            "_download_bytes",
            side_effect=[http_error, (b"ok", url)],
        ) as download_mock, mock.patch.object(
            gdelt_news_raw.time,
            "sleep",
        ) as sleep_mock, mock.patch.object(
            gdelt_news_raw.random,
            "uniform",
            return_value=0.0,
        ):
            result = gdelt_news_raw._download_bytes_with_retry(
                url,
                batch_time=batch_time,
                resource_label=f"{batch_time:%Y%m%d%H%M%S}",
            )

        self.assertEqual(result, (b"ok", url))
        self.assertEqual(download_mock.call_count, 2)
        sleep_mock.assert_called_once_with(5.0)

    def test_retry_after_is_capped_at_sixty_seconds(self) -> None:
        url = "https://data.gdeltproject.org/gdeltv2/lastupdate.txt"
        http_error = urllib.error.HTTPError(
            url,
            503,
            "Unavailable",
            {"Retry-After": "120"},
            None,
        )
        with mock.patch.object(
            gdelt_news_raw,
            "_download_bytes",
            side_effect=[http_error, (b"ok", url)],
        ), mock.patch.object(gdelt_news_raw.time, "sleep") as sleep_mock:
            gdelt_news_raw._download_bytes_with_retry(url, resource_label="manifest")

        sleep_mock.assert_called_once_with(60.0)

    def test_redirect_validation_rejects_host_and_path_changes(self) -> None:
        original = "https://data.gdeltproject.org/gdeltv2/lastupdate.txt"
        with self.assertRaisesRegex(ValueError, "invalid host"):
            gdelt_news_raw._validate_gdelt_redirect(
                original,
                "https://example.com/gdeltv2/lastupdate.txt",
            )
        with self.assertRaisesRegex(ValueError, "resource path"):
            gdelt_news_raw._validate_gdelt_redirect(
                original,
                "https://data.gdeltproject.org/gdeltv2/other.txt",
            )

    def test_retryable_http_status_contract(self) -> None:
        recent_batch = datetime.now(timezone.utc)
        old_batch = datetime(2020, 1, 1, tzinfo=timezone.utc)
        url = "https://data.gdeltproject.org/gdeltv2/example.gkg.csv.zip"

        for status in (408, 429, 500, 502, 503, 504):
            with self.subTest(status=status):
                error = urllib.error.HTTPError(url, status, "temporary", {}, None)
                self.assertTrue(
                    gdelt_news_raw._is_retryable_http_error(
                        error,
                        batch_time=old_batch,
                    )
                )
        for status in (400, 404):
            with self.subTest(status=status):
                error = urllib.error.HTTPError(url, status, "recent only", {}, None)
                self.assertTrue(
                    gdelt_news_raw._is_retryable_http_error(
                        error,
                        batch_time=recent_batch,
                    )
                )
                self.assertFalse(
                    gdelt_news_raw._is_retryable_http_error(
                        error,
                        batch_time=old_batch,
                    )
                )

    def test_materialize_empty_window_emits_summary_and_preserves_empty_contract(self) -> None:
        batch_times = tuple(
            datetime(2026, 4, 20, 5, 15, tzinfo=timezone.utc)
            + gdelt_news_raw.timedelta(minutes=15 * offset)
            for offset in range(4)
        )
        window = gdelt_news_raw.RequestedWindow(
            start_dt=batch_times[0],
            end_dt=batch_times[-1],
            batch_times=batch_times,
            selection_mode="manifest",
            is_backfill=False,
        )
        empty_sentinel = object()

        with mock.patch.object(
            gdelt_news_raw,
            "_resolve_window_selection",
            return_value=window,
        ), mock.patch.object(
            gdelt_news_raw,
            "_fetch_batch_rows",
            return_value=gdelt_news_raw.BatchFetchResult(
                availability_status="unavailable",
                was_missing=True,
                missing_reason="HTTP 404",
            ),
        ), mock.patch.object(
            gdelt_news_raw,
            "_empty_dataframe",
            return_value=empty_sentinel,
        ), mock.patch.object(gdelt_news_raw, "_persist_source_attempt") as persist_mock, mock.patch("builtins.print") as print_mock:
            result = gdelt_news_raw.materialize()

        self.assertIs(result, empty_sentinel)
        attempt = persist_mock.call_args.args[0]
        self.assertEqual(attempt["accepted_row_count"], 0)
        self.assertEqual(attempt["downloaded_file_count"], 0)
        self.assertEqual(attempt["expected_file_count"], 4)
        self.assertEqual(attempt["missing_file_count"], 4)
        self.assertFalse(attempt["is_complete"])
        self.assertFalse(attempt["is_backfill"])
        summary = print_mock.call_args.args[0]
        self.assertIn("mode=live", summary)
        self.assertIn("expected_files=4", summary)
        self.assertIn("downloaded_files=0", summary)
        self.assertIn("completeness=empty", summary)
        self.assertIn("low_volume=unknown", summary)

    def test_source_attempt_load_waits_for_visibility_and_propagates_failure(self):
        bigquery = mock.MagicMock()
        client = bigquery.Client.return_value
        attempt = {"ingestion_id": "test_attempt", "downloaded_file_count": 0}
        with mock.patch.object(gdelt_news_raw, "_import_bigquery", return_value=bigquery), mock.patch.object(
            gdelt_news_raw, "_resolve_project_id", return_value="example-project"
        ):
            gdelt_news_raw._persist_source_attempt(attempt)
            args, kwargs = client.load_table_from_json.call_args
            self.assertEqual(args, ([attempt], "example-project.bronze.gdelt_ingestion_attempts"))
            self.assertEqual(kwargs["job_id"], "gdelt_attempt_test_attempt")
            client.load_table_from_json.return_value.result.assert_called_once()
            client.load_table_from_json.return_value.result.side_effect = RuntimeError("write failed")
            with self.assertRaisesRegex(RuntimeError, "write failed"):
                gdelt_news_raw._persist_source_attempt(attempt)

    def test_low_volume_waits_for_full_five_run_baseline(self) -> None:
        with mock.patch.object(
            gdelt_news_raw,
            "_fetch_recent_accepted_row_counts",
            return_value=[100, 100, 100, 100],
        ):
            result = gdelt_news_raw._enforce_run_guardrails(
                accepted_rows=1,
                total_rows_seen=1,
                malformed_rows=0,
            )

        self.assertFalse(result.low_volume)
        self.assertIsNone(result.baseline_average_accepted_row_count)

    def test_low_volume_is_not_evaluated_for_partial_window(self) -> None:
        with mock.patch.object(
            gdelt_news_raw,
            "_fetch_recent_accepted_row_counts",
        ) as history_mock:
            result = gdelt_news_raw._enforce_run_guardrails(
                accepted_rows=40,
                total_rows_seen=40,
                malformed_rows=0,
                evaluate_low_volume=False,
            )

        history_mock.assert_not_called()
        self.assertIsNone(result.low_volume)


if __name__ == "__main__":
    unittest.main()
