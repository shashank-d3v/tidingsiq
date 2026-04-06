from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
import unittest
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
SPEC.loader.exec_module(gdelt_news_raw)


class GdeltNewsRawTest(unittest.TestCase):
    def test_build_gkg_batch_url_defaults_to_documented_http_feed(self) -> None:
        batch_time = datetime(2026, 4, 2, 16, 45, tzinfo=timezone.utc)

        url = gdelt_news_raw._build_gkg_batch_url(batch_time)

        self.assertEqual(
            url,
            "http://data.gdeltproject.org/gdeltv2/20260402164500.gkg.csv.zip",
        )

    def test_build_gkg_batch_url_honors_override(self) -> None:
        batch_time = datetime(2026, 4, 2, 16, 45, tzinfo=timezone.utc)

        with mock.patch.dict(
            "os.environ", {"GDELT_BASE_URL": "https://example.com/feed/"}, clear=False
        ):
            url = gdelt_news_raw._build_gkg_batch_url(batch_time)

        self.assertEqual(url, "https://example.com/feed/20260402164500.gkg.csv.zip")

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


if __name__ == "__main__":
    unittest.main()
