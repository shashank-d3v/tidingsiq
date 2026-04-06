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


if __name__ == "__main__":
    unittest.main()
