"""SISYS 基础设施层 Redis 记忆缓存模块

基于 RedisAdapter 实现记忆领域缓存端口，
支持记忆专用键构建与 TTL 随机化防止缓存雪崩
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from src.application.ports.memory_cache_port import MemoryCachePort

if TYPE_CHECKING:
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter

DEFAULT_TTL_MIN = 86400  # 24h
DEFAULT_TTL_MAX = 108000  # 30h


class RedisMemoryCache(MemoryCachePort):
    """Memory-domain Redis cache — Rule 4 infrastructure layer.

    Implements MemoryCachePort by composing RedisAdapter (Rule 3).
    Adds memory-specific key building and TTL randomization.

    Args:
        adapter: RedisAdapter instance (generic KV).
    """

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

    # === MemoryCachePort memory-specific methods ===

    async def get_memory(self, memory_type: str, owner_id: str, name: str) -> str | None:
        key = self._build_key(memory_type, owner_id, name)
        return await self._adapter.get(key)

    async def set_memory(
        self,
        memory_type: str,
        owner_id: str,
        name: str,
        content: str,
        ttl: int | None = None,
    ) -> bool:
        key = self._build_key(memory_type, owner_id, name)
        effective_ttl = ttl if ttl is not None else self._generate_ttl()
        return await self._adapter.set_with_ttl(key, content, effective_ttl)

    async def delete_memory(self, memory_type: str, owner_id: str, name: str) -> bool:
        key = self._build_key(memory_type, owner_id, name)
        return await self._adapter.delete(key)

    async def invalidate_owner(self, memory_type: str, owner_id: str) -> int:
        pattern = self._build_pattern(memory_type, owner_id)
        return await self._adapter.delete_pattern(pattern)

    # === Private helpers ===

    def _build_key(self, memory_type: str, owner_id: str, name: str) -> str:
        if memory_type == "group":
            return f"memory:group:{owner_id}:{name}"
        return f"memory:user:{owner_id}:{name}"

    def _build_pattern(self, memory_type: str, owner_id: str) -> str:
        if memory_type == "group":
            return f"memory:group:{owner_id}:*"
        return f"memory:user:{owner_id}:*"

    def _generate_ttl(self) -> int:
        return DEFAULT_TTL_MIN + random.randint(0, DEFAULT_TTL_MAX - DEFAULT_TTL_MIN)  # nosec B311
