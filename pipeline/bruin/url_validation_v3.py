from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

STATUS_VALID = "valid"
STATUS_BROKEN = "broken"
STATUS_TIMEOUT = "timeout"
STATUS_FORBIDDEN = "forbidden"
STATUS_REDIRECT_LOOP = "redirect_loop"
STATUS_UNAVAILABLE = "unavailable"
STATUS_UNCHECKED = "unchecked"

RECHECK_WINDOWS = {
    STATUS_VALID: timedelta(days=30),
    STATUS_TIMEOUT: timedelta(days=7),
    STATUS_UNAVAILABLE: timedelta(days=7),
    STATUS_FORBIDDEN: timedelta(days=14),
}


@dataclass(frozen=True)
class UrlValidationOutcome:
    final_url: str
    http_status_code: int | None
    redirect_count: int
    status: str


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def is_recheck_due(
    *,
    status: str | None,
    checked_at: datetime | None,
    now: datetime | None = None,
) -> bool:
    if checked_at is None:
        return True
    effective_now = now or datetime.now(timezone.utc)
    status_key = str(status or STATUS_UNCHECKED).lower()
    window = RECHECK_WINDOWS.get(status_key)
    if window is None:
        return True
    return checked_at + window <= effective_now.astimezone(timezone.utc)


def is_syntactically_valid_url(value: str | None) -> bool:
    raw_url = str(value or "").strip()
    if not raw_url:
        return False
    parts = urlparse(raw_url)
    if parts.scheme not in {"http", "https"}:
        return False
    if not parts.netloc:
        return False
    hostname = parts.hostname or ""
    return "." in hostname and not hostname.startswith(".")


def classify_http_status(status_code: int | None) -> str:
    if status_code is None:
        return STATUS_UNAVAILABLE
    if 200 <= status_code < 300:
        return STATUS_VALID
    if status_code in {401, 403}:
        return STATUS_FORBIDDEN
    if status_code in {404, 410}:
        return STATUS_BROKEN
    if 500 <= status_code < 600 or status_code == 429:
        return STATUS_UNAVAILABLE
    return STATUS_UNAVAILABLE


def _open_with_method(
    *,
    url: str,
    method: str,
    timeout_seconds: float,
    opener=None,
) -> tuple[str, int | None, dict[str, str], bool]:
    effective_opener = opener or build_opener(_NoRedirectHandler())
    request = Request(
        url,
        headers={"User-Agent": "TidingsIQUrlValidator/1.0"},
        method=method,
    )
    try:
        response = effective_opener.open(request, timeout=timeout_seconds)
        status_code = getattr(response, "status", None) or response.getcode()
        final_url = getattr(response, "url", url)
        headers = dict(getattr(response, "headers", {}) or {})
        return final_url, int(status_code) if status_code is not None else None, headers, False
    except HTTPError as error:
        headers = dict(error.headers or {})
        return error.geturl(), int(error.code), headers, 300 <= int(error.code) < 400


def _resolve_url(
    *,
    url: str,
    method: str,
    opener=None,
    timeout_seconds: float = 10.0,
    max_redirects: int = 5,
) -> UrlValidationOutcome:
    current_url = url
    seen_urls = {url}
    redirect_count = 0

    while True:
        final_url, status_code, headers, is_redirect = _open_with_method(
            url=current_url,
            method=method,
            timeout_seconds=timeout_seconds,
            opener=opener,
        )
        if is_redirect:
            location = headers.get("Location") or headers.get("location")
            if not location or redirect_count >= max_redirects:
                return UrlValidationOutcome(
                    final_url=current_url,
                    http_status_code=status_code,
                    redirect_count=redirect_count,
                    status=STATUS_REDIRECT_LOOP,
                )
            next_url = urljoin(current_url, location)
            if next_url in seen_urls:
                return UrlValidationOutcome(
                    final_url=next_url,
                    http_status_code=status_code,
                    redirect_count=redirect_count + 1,
                    status=STATUS_REDIRECT_LOOP,
                )
            seen_urls.add(next_url)
            current_url = next_url
            redirect_count += 1
            continue

        return UrlValidationOutcome(
            final_url=final_url,
            http_status_code=status_code,
            redirect_count=redirect_count,
            status=classify_http_status(status_code),
        )


def validate_url(
    url: str,
    *,
    opener=None,
    timeout_seconds: float = 10.0,
    max_redirects: int = 5,
) -> UrlValidationOutcome:
    try:
        head_outcome = _resolve_url(
            url=url,
            method="HEAD",
            opener=opener,
            timeout_seconds=timeout_seconds,
            max_redirects=max_redirects,
        )
        if head_outcome.http_status_code not in {405, 501}:
            return head_outcome
        return _resolve_url(
            url=url,
            method="GET",
            opener=opener,
            timeout_seconds=timeout_seconds,
            max_redirects=max_redirects,
        )
    except HTTPError as error:
        return UrlValidationOutcome(
            final_url=error.geturl(),
            http_status_code=int(error.code),
            redirect_count=0,
            status=classify_http_status(int(error.code)),
        )
    except (TimeoutError, socket.timeout):
        return UrlValidationOutcome(
            final_url=url,
            http_status_code=None,
            redirect_count=0,
            status=STATUS_TIMEOUT,
        )
    except URLError as error:
        reason: Any = getattr(error, "reason", None)
        if isinstance(reason, socket.timeout):
            return UrlValidationOutcome(
                final_url=url,
                http_status_code=None,
                redirect_count=0,
                status=STATUS_TIMEOUT,
            )
        return UrlValidationOutcome(
            final_url=url,
            http_status_code=None,
            redirect_count=0,
            status=STATUS_UNAVAILABLE,
        )
