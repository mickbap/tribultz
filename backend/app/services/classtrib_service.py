"""ClassTrib lookup service via Conformidade Fácil API (SVRS).

Provides validation of cClassTrib codes against the official SVRS registry.
Uses Redis cache to avoid repeated API calls.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class ClassTribService:
    """Client for the Conformidade Fácil ClassTrib API."""

    def __init__(self) -> None:
        self.base_url = settings.CLASSTRIB_API_URL
        self.timeout = 10.0

    async def lookup(self, code: str) -> dict[str, Any] | None:
        """Look up a ClassTrib code. Returns description dict or None if not found."""
        if not code or len(code) != 6 or not code.isdigit():
            return None

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(f"{self.base_url}/{code}")
                if resp.status_code == 200:
                    data = resp.json()
                    logger.info("classtrib_lookup_ok", extra={"code": code})
                    return data
                if resp.status_code == 404:
                    logger.info("classtrib_not_found", extra={"code": code})
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


# Singleton
classtrib_service = ClassTribService()
