from __future__ import annotations

from datetime import datetime, timedelta, timezone
import socket
import unittest
from unittest import mock
from urllib.error import HTTPError

from pipeline.bruin.assets.gold.url_validation_results import _records_dataframe
from pipeline.bruin.url_validation_v3 import (
    STATUS_BROKEN,
    STATUS_REDIRECT_LOOP,
    STATUS_TIMEOUT,
    STATUS_UNAVAILABLE,
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


def _addrinfo(*addresses: str) -> list[tuple[int, int, int, str, tuple[str, int]]]:
    return [
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, 443))
        for address in addresses
    ]


class UrlValidationV3Test(unittest.TestCase):
    def _patch_dns(
        self,
        mapping: dict[str, object] | None = None,
        *,
        default_addresses: tuple[str, ...] = ("93.184.216.34",),
    ):
        effective_mapping = mapping or {}

        def side_effect(host: str, port=None, type=0, proto=0, flags=0):  # noqa: ANN001
            result = effective_mapping.get(host)
            if isinstance(result, Exception):
                raise result
            if result is None:
                return _addrinfo(*default_addresses)
            return result

        return mock.patch(
            "pipeline.bruin.url_validation_v3.socket.getaddrinfo",
            side_effect=side_effect,
        )

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

        with self._patch_dns():
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

        with self._patch_dns():
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

        with self._patch_dns():
            outcome = validate_url("https://example.com/start", opener=opener)

        self.assertEqual(outcome.status, STATUS_REDIRECT_LOOP)

    def test_validate_url_maps_timeout(self) -> None:
        opener = _SequenceOpener([TimeoutError("timed out")])

        with self._patch_dns():
            outcome = validate_url("https://example.com/slow", opener=opener)

        self.assertEqual(outcome.status, STATUS_TIMEOUT)

    def test_validate_url_blocks_direct_ssrf_targets_before_request(self) -> None:
        cases = [
            ("http://127.0.0.1/story", "blocked_ip_literal"),
            ("http://10.0.0.8/story", "blocked_ip_literal"),
            ("http://192.168.1.8/story", "blocked_ip_literal"),
            ("http://169.254.169.254/latest/meta-data", "blocked_ip_literal"),
            ("http://metadata.google.internal/computeMetadata/v1/", "blocked_metadata_host"),
            ("http://8.8.8.8/story", "blocked_ip_literal"),
        ]

        for url, reason in cases:
            with self.subTest(url=url):
                opener = _SequenceOpener([])
                with self.assertLogs("pipeline.bruin.url_validation_v3", level="WARNING") as logs:
                    outcome = validate_url(url, opener=opener)

                self.assertEqual(outcome.status, STATUS_UNAVAILABLE)
                self.assertEqual(outcome.redirect_count, 0)
                self.assertEqual(opener.methods, [])
                self.assertIn(reason, logs.output[0])

    def test_validate_url_allows_public_news_url_after_dns_check(self) -> None:
        opener = _SequenceOpener([_FakeResponse("https://news.example.com/story", 200)])

        with self._patch_dns({"news.example.com": _addrinfo("93.184.216.34")}):
            outcome = validate_url("https://news.example.com/story", opener=opener)

        self.assertEqual(outcome.status, STATUS_VALID)
        self.assertEqual(outcome.redirect_count, 0)
        self.assertEqual(opener.methods, ["HEAD"])

    def test_validate_url_allows_public_redirect_target(self) -> None:
        opener = _SequenceOpener(
            [
                HTTPError(
                    url="https://news.example.com/start",
                    code=302,
                    msg="Found",
                    hdrs={"Location": "https://cdn.example.com/story"},
                    fp=None,
                ),
                _FakeResponse("https://cdn.example.com/story", 200),
            ]
        )

        with self._patch_dns(
            {
                "news.example.com": _addrinfo("93.184.216.34"),
                "cdn.example.com": _addrinfo("151.101.1.164"),
            }
        ):
            outcome = validate_url("https://news.example.com/start", opener=opener)

        self.assertEqual(outcome.status, STATUS_VALID)
        self.assertEqual(outcome.redirect_count, 1)
        self.assertEqual(opener.methods, ["HEAD", "HEAD"])

    def test_validate_url_blocks_redirect_targets_before_following_them(self) -> None:
        cases = [
            (
                "http://127.0.0.1/private",
                "blocked_ip_literal",
                {},
            ),
            (
                "http://169.254.169.254/latest/meta-data",
                "blocked_ip_literal",
                {},
            ),
            (
                "http://metadata.google.internal/computeMetadata/v1/",
                "blocked_metadata_host",
                {},
            ),
            (
                "https://internal.example/story",
                "blocked_private_ip",
                {"internal.example": _addrinfo("10.0.0.8")},
            ),
        ]

        for location, reason, mapping in cases:
            with self.subTest(location=location):
                opener = _SequenceOpener(
                    [
                        HTTPError(
                            url="https://news.example.com/start",
                            code=302,
                            msg="Found",
                            hdrs={"Location": location},
                            fp=None,
                        )
                    ]
                )
                with self._patch_dns({"news.example.com": _addrinfo("93.184.216.34"), **mapping}):
                    with self.assertLogs("pipeline.bruin.url_validation_v3", level="WARNING") as logs:
                        outcome = validate_url("https://news.example.com/start", opener=opener)

                self.assertEqual(outcome.status, STATUS_UNAVAILABLE)
                self.assertEqual(outcome.final_url, location)
                self.assertEqual(outcome.redirect_count, 0)
                self.assertEqual(opener.methods, ["HEAD"])
                self.assertIn(reason, logs.output[0])

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
