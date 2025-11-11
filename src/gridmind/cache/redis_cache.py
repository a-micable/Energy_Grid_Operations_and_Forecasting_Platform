from __future__ import annotations

import json
from typing import Any

import structlog

from gridmind.core.exceptions import CacheInvalidationError

logger = structlog.get_logger(__name__)


class RedisCache:
    """Redis-backed cache with pattern invalidation."""

    FORECAST_PREFIX = "gridmind:forecast:"
    DISPATCH_PREFIX = "gridmind:dispatch:"
    BALANCING_PREFIX = "gridmind:balancing:"

    def __init__(self, redis_client: Any, default_ttl: int = 300) -> None:
        self._redis = redis_client
        self._default_ttl = default_ttl
        self._local_version: dict[str, int] = {}

    def _key(self, prefix: str, entity_id: str) -> str:
        return f"{prefix}{entity_id}"

    async def get(self, prefix: str, entity_id: str) -> dict | None:
        key = self._key(prefix, entity_id)
        data = await self._redis.get(key)
        if data is None:
            return None
        return json.loads(data)

    async def set(
        self, prefix: str, entity_id: str, value: dict, *, ttl: int | None = None
    ) -> None:
        key = self._key(prefix, entity_id)
        await self._redis.setex(key, ttl or self._default_ttl, json.dumps(value))
        self._local_version[key] = self._local_version.get(key, 0) + 1

    async def invalidate(self, prefix: str, entity_id: str) -> None:
        key = self._key(prefix, entity_id)
        deleted = await self._redis.delete(key)
        self._local_version.pop(key, None)
        logger.info("cache_invalidated", key=key, deleted=bool(deleted))

    async def invalidate_pattern(self, pattern: str) -> int:
        keys = []
        async for key in self._redis.scan_iter(match=pattern):
            keys.append(key)
        if not keys:
            return 0
        count = await self._redis.delete(*keys)
        for key in keys:
            self._local_version.pop(key.decode() if isinstance(key, bytes) else key, None)
        logger.info("cache_pattern_invalidated", pattern=pattern, count=count)
        return count

    async def get_or_set(
        self,
        prefix: str,
        entity_id: str,
        factory: Any,
        *,
        ttl: int | None = None,
    ) -> dict:
        cached = await self.get(prefix, entity_id)
        if cached is not None:
            return cached
        value = await factory()
        await self.set(prefix, entity_id, value, ttl=ttl)
        return value

    def check_version_consistency(self, prefix: str, entity_id: str, expected_version: int) -> bool:
        key = self._key(prefix, entity_id)
        current = self._local_version.get(key, 0)
        if current != expected_version:
            raise CacheInvalidationError(
                f"Cache version mismatch for {key}: expected {expected_version}, got {current}"
            )
        return True
