"""基础设施层 Redis KV 适配器模块

实现 L1CachePort，使用 Redis 字符串操作。所有 Rule 4 组件的 Redis KV 访问入口

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.ports.l1_cache import L1CachePort

if TYPE_CHECKING:
    import redis.asyncio as aioredis


class RedisAdapter(L1CachePort):
    """通用 Redis KV 适配器，实现 L1CachePort

    使用 Redis 字符串操作，是所有 Rule 4 组件的 Redis KV 访问入口

    Attributes:
        _redis: aioredis.Redis 实例（由 RedisManager 提供）
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        """初始化 Redis 适配器

        Args:
            redis_client: aioredis.Redis 实例（由 RedisManager 提供）
        """
        self._redis = redis_client

    async def get(self, key: str) -> str | None:
        """根据键获取值

        Args:
            key: Redis 键

        Returns:
            字符串值，键不存在返回 None
        """
        value = await self._redis.get(key)
        if value is None:
            return None
        return value.decode("utf-8") if isinstance(value, bytes) else value

    async def set(self, key: str, value: str, ttl: int | None = None) -> bool:
        """设置键值对

        Args:
            key: Redis 键
            value: 字符串值
            ttl: 过期时间（秒），为 None 时永不过期

        Returns:
            设置成功返回 True
        """
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
