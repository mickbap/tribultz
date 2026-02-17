from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional, cast
from fastapi import HTTPException, status
import redis
from app.config import settings

logger = logging.getLogger(__name__)

class RateLimiter:
    """
    Hybrid Rate Limiter (Redis with In-Memory Fallback).
    Strict MVP requirement: 10 requests per 60 seconds per user.
    """
    def __init__(self):
        self.ttl = 60  # seconds
        self.limit = 10 # requests per window
        self.redis: Optional[redis.Redis] = None
        self._memory_store: Dict[str, List[int]] = {}

        if settings.REDIS_URL:
            try:
                self.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
                # Test connection
                self.redis.ping()
                logger.info(f"RateLimiter connected to Redis: {settings.REDIS_URL}")
            except Exception as e:
                logger.warning(f"RateLimiter failed to connect to Redis: {e}. Fallback to in-memory.")
                self.redis = None

    def check_or_raise(self, key: str):
        """
        Check limit for key (usually user_id). Raises 429 if exceeded.
        """
        if self.redis:
            self._check_redis(key)
        else:
            self._check_memory(key)

    def _check_redis(self, key: str):
        # Redis is guaranteed to be connected if this is called
        if self.redis is None:
             # Should not happen if called correctly from check_or_raise
             self._check_memory(key)
             return

        pk = f"ratelimit:{key}"
        try:
            # Atomic increment
            current = cast(int, self.redis.incr(pk))
            if current == 1:
                self.redis.expire(pk, self.ttl)
            
            if current > self.limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Try again later."
                )
        except redis.RedisError as e:
            logger.error(f"Redis error in RateLimiter: {e}")
            # Fail open for Redis errors to maximize availability, 
            # OR fail closed if strictness is paramount.
            # Choosing fail open with fallback to memory if meaningful, 
            # but syncing memory across workers is impossible without Redis.
            # Verify requirement: "implement in-memory + disclaimer".
            # Let's switch to memory check if Redis fails.
            self._check_memory(key)

    def _check_memory(self, key: str):
        now = int(time.time())
        window_start = now - self.ttl
        
        history = self._memory_store.get(key, [])
        # Cleanup old timestamps
        valid_history = [ts for ts in history if ts > window_start]
        
        if len(valid_history) >= self.limit:
             raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded (local/fallback). Try again later."
            )
        
        valid_history.append(now)
        self._memory_store[key] = valid_history
