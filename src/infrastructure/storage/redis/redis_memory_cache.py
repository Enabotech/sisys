"""SISYS 基础设施层 Redis 记忆缓存模块

基于 RedisAdapter 实现记忆领域缓存端口，
支持记忆专用键构建与 TTL 随机化防止缓存雪崩

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

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
