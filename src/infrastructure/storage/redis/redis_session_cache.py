"""SISYS 基础设施层 Redis 会话缓存模块

基于 RedisAdapter 实现会话缓存端口，
支持会话专用 HSET/HGET 操作
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.application.ports.session_cache_port import SessionCachePort
from src.infrastructure.storage.redis.key_builder import build_key
from src.infrastructure.utils import json_dumps, json_loads

if TYPE_CHECKING:
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter


class RedisSessionCache(SessionCachePort):
    """Redis session cache — implements SessionCachePort.

    Composes RedisAdapter (Rule 3) for L1CachePort operations
    and uses adapter.raw_client for session-specific Hash operations.
    """

    _SESSION_NAMESPACE = "session"

    def __init__(self, adapter: RedisAdapter) -> None:
        self._adapter = adapter

    # === L1CachePort generic methods (delegated) ===

    async def get(self, key: str) -> str | None:
        return await self._adapter.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> bool:
        return await self._adapter.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        return await self._adapter.delete(key)

    async def exists(self, key: str) -> bool:
        return await self._adapter.exists(key)

    async def delete_pattern(self, pattern: str) -> int:
        return await self._adapter.delete_pattern(pattern)

    async def set_with_ttl(self, key: str, value: str, ttl: int) -> bool:
        return await self._adapter.set_with_ttl(key, value, ttl)

    async def set_nx(self, key: str, value: str, ttl: int) -> bool:
        """SET NX 原子写入（委派底层适配器实现）

        Args:
            key: 缓存键
            value: 待存储的值
            ttl: TTL 秒数

        Returns:
            键不存在且写入成功返回 True，键已存在返回 False
        """
        return await self._adapter.set_nx(key, value, ttl)

    async def eval(self, script: str, keys: list[str], args: list[str]) -> Any:
        """执行 Lua 脚本（委派底层适配器实现）

        Args:
            script: Lua 脚本代码
            keys: Redis key 参数
            args: 脚本参数

        Returns:
            Lua 脚本返回值
        """
        return await self._adapter.eval(script, keys, args)

    # === SessionCachePort session-specific methods ===

    async def save_session(
        self,
        session_id: str,
        agent_id: str,
        state: dict,
        ttl: int = 86400,
    ) -> None:
        key = build_key(self._SESSION_NAMESPACE, session_id)
        data = json_dumps({"session_id": session_id, "agent_id": agent_id, "state": state})
        await self._adapter.raw_client.hset(key, "data", data)
        await self._adapter.raw_client.expire(key, ttl)

    async def load_session(self, session_id: str) -> dict | None:
        key = build_key(self._SESSION_NAMESPACE, session_id)
        data = await self._adapter.raw_client.hget(key, "data")
        if data is None:
            return None
        raw = json_loads(data)
        if not isinstance(raw, dict):
            return None
        return raw

    async def delete_session(self, session_id: str) -> None:
        key = build_key(self._SESSION_NAMESPACE, session_id)
        await self._adapter.delete(key)

    async def session_exists(self, session_id: str) -> bool:
        key = build_key(self._SESSION_NAMESPACE, session_id)
        return await self._adapter.exists(key)
