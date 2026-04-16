from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest
from urllib.error import HTTPError

from pipeline.bruin.assets.gold.url_validation_results import _records_dataframe
from pipeline.bruin.url_validation_v3 import (
    STATUS_BROKEN,
    STATUS_REDIRECT_LOOP,
    STATUS_TIMEOUT,
    STATUS_VALID,
    is_recheck_due,
    is_syntactically_valid_url,
    validate_url,
)


class _FakeResponse:
    def __init__(self, url: str, status: int, headers: dict[str, str] | None = None) -> None:
        self.url = url
        self.status = status
        self.headers = headers or {}

    def getcode(self) -> int:
        return self.status


class _SequenceOpener:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.methods: list[str] = []

    def open(self, request, timeout=None):  # noqa: ANN001
        self.methods.append(request.get_method())
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class UrlValidationV3Test(unittest.TestCase):
    def test_url_shape_validation_requires_http_scheme_and_hostname(self) -> None:
        self.assertTrue(is_syntactically_valid_url("https://example.com/story"))
        self.assertFalse(is_syntactically_valid_url("ftp://example.com/story"))
        self.assertFalse(is_syntactically_valid_url("https:///story"))
        self.assertFalse(is_syntactically_valid_url(""))

    def test_recheck_due_uses_status_windows(self) -> None:
        now_utc = datetime(2026, 4, 12, tzinfo=timezone.utc)

        self.assertFalse(
            is_recheck_due(
                status="valid",
                checked_at=now_utc - timedelta(days=10),
                now=now_utc,
            )
        )
        self.assertTrue(
            is_recheck_due(
                status="timeout",
                checked_at=now_utc - timedelta(days=8),
                now=now_utc,
            )
        )
        self.assertTrue(
            is_recheck_due(
                status="unchecked",
                checked_at=now_utc - timedelta(days=1),
                now=now_utc,
            )
        )

    def test_validate_url_falls_back_to_get_after_head_405(self) -> None:
        opener = _SequenceOpener(
            [
                HTTPError(
                    url="https://example.com/story",
                    code=405,
                    msg="Method Not Allowed",
                    hdrs={},
                    fp=None,
                ),
                _FakeResponse("https://example.com/story", 200),
            ]
        )

        outcome = validate_url("https://example.com/story", opener=opener)

        self.assertEqual(opener.methods, ["HEAD", "GET"])
        self.assertEqual(outcome.status, STATUS_VALID)

    def test_validate_url_marks_not_found_as_broken(self) -> None:
        opener = _SequenceOpener(
            [
                HTTPError(
                    url="https://example.com/missing",
                    code=404,
                    msg="Not Found",
                    hdrs={},
                    fp=None,
                )
            ]
        )

        outcome = validate_url("https://example.com/missing", opener=opener)

        self.assertEqual(outcome.status, STATUS_BROKEN)
        self.assertEqual(outcome.http_status_code, 404)

    def test_validate_url_detects_redirect_loops(self) -> None:
        opener = _SequenceOpener(
            [
                HTTPError(
                    url="https://example.com/start",
                    code=302,
                    msg="Found",
                    hdrs={"Location": "https://example.com/loop"},
                    fp=None,
                ),
                HTTPError(
                    url="https://example.com/loop",
                    code=302,
                    msg="Found",
                    hdrs={"Location": "https://example.com/start"},
                    fp=None,
                ),
            ]
        )

        outcome = validate_url("https://example.com/start", opener=opener)

        self.assertEqual(outcome.status, STATUS_REDIRECT_LOOP)

    def test_validate_url_maps_timeout(self) -> None:
        opener = _SequenceOpener([TimeoutError("timed out")])

        outcome = validate_url("https://example.com/slow", opener=opener)

        self.assertEqual(outcome.status, STATUS_TIMEOUT)

    def test_records_dataframe_keeps_nullable_integer_columns(self) -> None:
        dataframe = _records_dataframe(
            [
                {
                    "normalized_url": "https://example.com/a",
                    "checked_at": datetime(2026, 4, 16, tzinfo=timezone.utc),
                    "final_url": "https://example.com/a",
                    "http_status_code": 200,
                    "redirect_count": 0,
                    "status": STATUS_VALID,
                },
                {
                    "normalized_url": "https://example.com/b",
                    "checked_at": datetime(2026, 4, 16, tzinfo=timezone.utc),
                    "final_url": None,
                    "http_status_code": None,
                    "redirect_count": 1,
                    "status": STATUS_TIMEOUT,
                },
            ]
        )

        self.assertEqual(str(dataframe["http_status_code"].dtype), "Int64")
        self.assertEqual(str(dataframe["redirect_count"].dtype), "Int64")


if __name__ == "__main__":
    unittest.main()
