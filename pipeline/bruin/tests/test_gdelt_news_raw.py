from __future__ import annotations

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
sys.modules.setdefault("pandas", types.SimpleNamespace(DataFrame=object, Series=object))
gdelt_news_raw = importlib.util.module_from_spec(SPEC)
sys.modules["gdelt_news_raw"] = gdelt_news_raw
SPEC.loader.exec_module(gdelt_news_raw)


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

    def test_build_gkg_batch_url_defaults_to_documented_http_feed(self) -> None:
        batch_time = self._valid_batch_time()

        url = gdelt_news_raw._build_gkg_batch_url(batch_time)

        self.assertEqual(
            url,
            "http://data.gdeltproject.org/gdeltv2/20260402164500.gkg.csv.zip",
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

    def test_enforce_run_guardrails_fails_on_high_malformed_ratio(self) -> None:
        with mock.patch.object(gdelt_news_raw, "_fetch_recent_accepted_row_counts", return_value=[]):
            with mock.patch.dict("os.environ", {"GDELT_MAX_MALFORMED_RATIO": "0.10"}, clear=False):
                with self.assertRaisesRegex(RuntimeError, "malformed row ratio"):
                    gdelt_news_raw._enforce_run_guardrails(
                        accepted_rows=8,
                        total_rows_seen=10,
                        malformed_rows=2,
                    )

    def test_enforce_run_guardrails_fails_on_recent_row_count_collapse(self) -> None:
        with mock.patch.object(
            gdelt_news_raw,
            "_fetch_recent_accepted_row_counts",
            return_value=[100, 120, 110],
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
            return_value=[100, 120, 110],
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

        with mock.patch.object(gdelt_news_raw, "datetime", FakeDateTime):
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

        self.assertEqual(start_dt, datetime(2026, 4, 20, 5, 30, tzinfo=timezone.utc))
        self.assertEqual(end_dt, datetime(2026, 4, 20, 6, 30, tzinfo=timezone.utc))

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
                },
                clear=False,
            ):
                start_dt, end_dt = gdelt_news_raw._resolve_requested_window()

        self.assertEqual(start_dt, datetime(2026, 4, 20, 6, 20, tzinfo=timezone.utc))
        self.assertEqual(end_dt, datetime(2026, 4, 20, 6, 20, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
