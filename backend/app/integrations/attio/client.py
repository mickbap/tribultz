"""AttioClient — low-level HTTP client for the Attio REST API.

PO-2026-07-CRM-001, fatia 1/12: auth, rate-limit-aware exponential retry,
error handling, and structured logs. Intentionally has no domain logic
(companies/people/pipeline) — those build on top of `request()` in later
fatias. Attio is the CRM for the commercial pipeline (lead→fechado); HubSpot
(app/tools/hubspot_tool.py) stays isolated for post-sale dunning/win-back.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.attio.com/v2"

# Status codes worth retrying at all. 429 (rate limited) is safe to retry for
# every HTTP method — the request was rejected before any processing. The
# others (5xx) are only retried for idempotent methods: retrying a POST after
# a 5xx risks double-creating a record, since we don't know if it succeeded
# server-side before the error.
_RETRYABLE_5XX = {500, 502, 503, 504}
_IDEMPOTENT_METHODS = {"GET", "PUT", "PATCH", "DELETE"}


class AttioAPIError(Exception):
    """Raised when an Attio API request fails after exhausting retries."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"Attio API error {status_code}: {message}")


def is_enabled() -> bool:
    return settings.ATTIO_ENABLED and bool(settings.ATTIO_API_KEY)


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.ATTIO_API_KEY}",
        "Content-Type": "application/json",
    }


def noop(entity: str, action: str = "skipped") -> dict[str, Any]:
    """Return a no-op result when Attio is disabled — mirrors hubspot_tool._noop."""
    return {"attio": "disabled", "entity": entity, "action": action}


class AttioClient:
    """Thin wrapper around httpx with retry/backoff and structured logging.

    Pass `transport` (e.g. httpx.MockTransport) in tests to avoid real network calls.
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay_seconds: float = 0.5,
        timeout_seconds: float = 15.0,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self._max_retries = max_retries
        self._base_delay = base_delay_seconds
        self._timeout = timeout_seconds
        self._transport = transport

    def request(
        self,
        method: str,
        path: str,
        json: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Issue an authenticated request against the Attio API.

        Retries with exponential backoff (honoring Retry-After when present)
        on 429 for any method, and on 5xx for idempotent methods only. Raises
        AttioAPIError immediately on non-retryable errors or once retries are
        exhausted.
        """
        url = f"{BASE_URL}{path}"
        attempt = 0

        while True:
            start = time.monotonic()
            try:
                with httpx.Client(transport=self._transport, timeout=self._timeout) as client:
                    resp = client.request(method, url, headers=_headers(), json=json, params=params)
            except httpx.TransportError as exc:
                if attempt >= self._max_retries:
                    logger.error(
                        "attio_request_transport_error_exhausted method=%s path=%s attempt=%d error=%s",
                        method, path, attempt, exc,
                    )
                    raise AttioAPIError(0, str(exc)) from exc
                logger.warning(
                    "attio_request_transport_error method=%s path=%s attempt=%d error=%s",
                    method, path, attempt, exc,
                )
                time.sleep(self._base_delay * (2**attempt))
                attempt += 1
                continue

            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.info(
                "attio_request method=%s path=%s status=%d attempt=%d duration_ms=%d",
                method, path, resp.status_code, attempt, elapsed_ms,
            )

            if resp.status_code < 300:
                return resp.json() if resp.content else {}

            retryable = resp.status_code == 429 or (
                resp.status_code in _RETRYABLE_5XX and method.upper() in _IDEMPOTENT_METHODS
            )
            if not retryable or attempt >= self._max_retries:
                _raise_for_response(resp)

            time.sleep(_retry_after_seconds(resp, self._base_delay * (2**attempt)))
            attempt += 1


def _retry_after_seconds(resp: httpx.Response, default: float) -> float:
    header = resp.headers.get("Retry-After")
    if header and header.isdigit():
        return float(header)
    return default


def _raise_for_response(resp: httpx.Response) -> None:
    try:
        message = str(resp.json().get("message", resp.text))
    except ValueError:
        message = resp.text
    logger.error("attio_request_failed status=%d message=%s", resp.status_code, message[:500])
    raise AttioAPIError(resp.status_code, message)


def ping() -> dict[str, Any]:
    """Minimal read call to validate the token — mirrors the curl in secrets_inventory.md."""
    if not is_enabled():
        return noop("ping")
    return AttioClient().request("GET", "/objects")
