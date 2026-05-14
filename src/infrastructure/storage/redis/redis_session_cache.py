"""RedisSessionCache — SessionCachePort 实现（Rule 4）。

组合注入 RedisMemoryCache（Rule 3 L1CachePort）和 RedisSessionStorage，
添加会话状态 save/load 语义。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import redis.asyncio as aioredis

from src.application.ports.session_cache_port import SessionCachePort
from src.infrastructure.storage.redis.key_builder import build_key
from src.infrastructure.utils import json_dumps, json_loads

if TYPE_CHECKING:
    from src.infrastructure.storage.redis.redis_memory_cache import RedisMemoryCache


class RedisSessionCache(SessionCachePort):
    """Redis 会话缓存 — 实现 SessionCachePort。

    组合 RedisMemoryCache（L1 缓存语义）和 Redis 直接操作（会话语义）。
    """

    _SESSION_NAMESPACE = "session"

    def __init__(self, cache: RedisMemoryCache, redis_client: aioredis.Redis):
        """初始化 RedisSessionCache。

        Args:
            cache: RedisMemoryCache 实例（Rule 3，L1CachePort 实现）
            redis_client: Redis 异步客户端（会话专用）
        """
        self._cache = cache
        self._redis = redis_client

    # -- L1CachePort methods (delegate to cache) --

    async def get(self, memory_type: str, owner_id: str, name: str) -> str | None:
        """获取缓存。"""
        return await self._cache.get(memory_type, owner_id, name)

    async def set(
        self,
        memory_type: str,
        owner_id: str,
        name: str,
        content: str,
        ttl: int | None = None,
    ) -> bool:
        """设置缓存。"""
        return await self._cache.set(memory_type, owner_id, name, content, ttl)

    async def delete(self, memory_type: str, owner_id: str, name: str) -> bool:
        """删除缓存。"""
        return await self._cache.delete(memory_type, owner_id, name)

    async def invalidate_pattern(self, memory_type: str, owner_id: str) -> int:
        """按 pattern 失效缓存。"""
        return await self._cache.invalidate_pattern(memory_type, owner_id)

    # -- SessionCachePort specific methods --

    async def save_session(
        self,
        session_id: str,
        agent_id: str,
        state: dict,
        ttl: int = 86400,
    ) -> None:
        """保存会话状态到 Redis Hash。"""
        key = build_key(self._SESSION_NAMESPACE, session_id)
        data = json_dumps({"session_id": session_id, "agent_id": agent_id, "state": state})
        await self._redis.hset(key, "data", data)
        await self._redis.expire(key, ttl)

    async def load_session(self, session_id: str) -> dict | None:
        """加载会话状态。"""
        key = build_key(self._SESSION_NAMESPACE, session_id)
        data = await self._redis.hget(key, "data")
        if data is None:
            return None
        raw = json_loads(data)
        if not isinstance(raw, dict):
            return None
        return raw

    async def delete_session(self, session_id: str) -> None:
        """删除会话。"""
        key = build_key(self._SESSION_NAMESPACE, session_id)
        await self._redis.delete(key)

    async def session_exists(self, session_id: str) -> bool:
        """检查会话是否存在。"""
        key = build_key(self._SESSION_NAMESPACE, session_id)
        return (await self._redis.exists(key)) > 0
