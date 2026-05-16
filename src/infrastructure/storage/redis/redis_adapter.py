"""RedisAdapter — Generic Redis KV adapter (Rule 3).

Implements L1CachePort using Redis string operations.
Single point of Redis access for all Rule 4 components.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.ports.l1_cache import L1CachePort

if TYPE_CHECKING:
    import redis.asyncio as aioredis


class RedisAdapter(L1CachePort):
    """Generic Redis KV adapter — Rule 3 infrastructure layer.

    Implements L1CachePort using Redis string operations.
    This is the single point of Redis KV access for all Rule 4 components.

    Args:
        redis_client: aioredis.Redis instance from RedisManager.
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client

    async def get(self, key: str) -> str | None:
        value = await self._redis.get(key)
        if value is None:
            return None
        return value.decode("utf-8") if isinstance(value, bytes) else value

    async def set(self, key: str, value: str, ttl: int | None = None) -> bool:
        if ttl is not None:
            await self._redis.setex(key, ttl, value)
        else:
            await self._redis.set(key, value)
        return True

    async def delete(self, key: str) -> bool:
        result = await self._redis.delete(key)
        return result > 0

    async def exists(self, key: str) -> bool:
        return (await self._redis.exists(key)) > 0

    async def delete_pattern(self, pattern: str) -> int:
        keys = [k async for k in self._redis.scan_iter(match=pattern)]
        if keys:
            await self._redis.delete(*keys)
        return len(keys)

    async def set_with_ttl(self, key: str, value: str, ttl: int) -> bool:
        await self._redis.setex(key, ttl, value)
        return True

    @property
    def raw_client(self) -> aioredis.Redis:
        """Expose underlying Redis client for data-structure-specific ops."""
        return self._redis
