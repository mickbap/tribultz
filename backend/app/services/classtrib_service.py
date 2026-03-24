"""ClassTrib lookup service via Conformidade Fácil API (SVRS).

Provides validation of cClassTrib codes against the official SVRS registry.
In-memory LRU cache to avoid repeated API calls (TTL 1h, max 1000 entries).
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_CACHE_MAX = 1000
_CACHE_TTL = 3600  # 1 hour


class _LRUCache:
    """Simple LRU cache with TTL."""

    def __init__(self, maxsize: int = _CACHE_MAX, ttl: int = _CACHE_TTL) -> None:
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl

    def get(self, key: str) -> tuple[bool, Any]:
        if key in self._store:
            ts, val = self._store[key]
            if time.monotonic() - ts < self._ttl:
                self._store.move_to_end(key)
                return True, val
            del self._store[key]
        return False, None

    def put(self, key: str, value: Any) -> None:
        self._store[key] = (time.monotonic(), value)
        self._store.move_to_end(key)
        while len(self._store) > self._maxsize:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()


class ClassTribService:
    """Client for the Conformidade Fácil ClassTrib API."""

    def __init__(self) -> None:
        self.base_url = settings.CLASSTRIB_API_URL
        self.timeout = 5.0
        self._cache = _LRUCache()

    async def lookup(self, code: str) -> dict[str, Any] | None:
        """Look up a ClassTrib code. Returns description dict or None if not found."""
        if not code or len(code) != 6 or not code.isdigit():
            return None

        hit, cached = self._cache.get(code)
        if hit:
            return cached

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(f"{self.base_url}/{code}")
                if resp.status_code == 200:
                    data = resp.json()
                    logger.info("classtrib_lookup_ok", extra={"code": code})
                    self._cache.put(code, data)
                    return data
                if resp.status_code == 404:
                    logger.info("classtrib_not_found", extra={"code": code})
                    self._cache.put(code, None)
                    return None
                logger.warning(
                    "classtrib_lookup_error",
                    extra={"code": code, "status": resp.status_code},
                )
                return None
        except httpx.HTTPError as exc:
            logger.error("classtrib_api_error", extra={"code": code, "error": str(exc)})
            return None

    async def validate(self, code: str) -> bool:
        """Check if a ClassTrib code exists in the official registry."""
        result = await self.lookup(code)
        return result is not None

    async def batch_validate(self, codes: set[str]) -> dict[str, bool | None]:
        """Validate multiple ClassTrib codes. Returns {code: True/False/None}.

        True = found, False = not found, None = API error (inconclusive).
        """
        results: dict[str, bool | None] = {}
        to_fetch: list[str] = []

        for code in codes:
            if not code or len(code) != 6 or not code.isdigit():
                results[code] = False
                continue
            hit, cached = self._cache.get(code)
            if hit:
                results[code] = cached is not None
            else:
                to_fetch.append(code)

        for code in to_fetch:
            result = await self.lookup(code)
            if result is not None:
                results[code] = True
            elif self._cache.get(code)[0]:
                # Was cached as None (404)
                results[code] = False
            else:
                results[code] = None  # API error

        return results


# Singleton
classtrib_service = ClassTribService()
