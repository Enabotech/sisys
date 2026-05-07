"""RedisMemoryCache — L1 记忆缓存。

基于 Redis 的 L1 记忆缓存实现。
Key 格式：
- Private: `memory:user:{user_id}:{name}`
- Group: `memory:group:{group_id}:{name}`
TTL：24h-30h（随机值避免雪崩）

架构来源: architecture.md §11.2.3
"""

from __future__ import annotations

import random

import redis

# 默认 TTL 范围 (秒)
DEFAULT_TTL_MIN = 86400  # 24h
DEFAULT_TTL_MAX = 108000  # 30h


class RedisMemoryCache:
    """Redis 记忆缓存。

    负责 L1 层记忆缓存的读写和失效。
    """

    def __init__(self, redis_client: redis.Redis):
        """初始化缓存。

        Args:
            redis_client: Redis 客户端实例
        """
        self._redis = redis_client

    def get(self, memory_type: str, owner_id: str, name: str) -> str | None:
        """获取缓存的记忆内容。

        Args:
            memory_type: 记忆类型 ('private' | 'group')
            owner_id: 所有者 ID (user_id 或 group_id)
            name: 记忆名称

        Returns:
            缓存的记忆内容，不存在则返回 None
        """
        key = self._build_key(memory_type, owner_id, name)
        value = self._redis.get(key)
        if value is None:
            return None
        return value.decode("utf-8") if isinstance(value, bytes) else value

    def set(self, memory_type: str, owner_id: str, name: str, content: str, ttl: int | None = None) -> None:
        """设置缓存的记忆内容。

        Args:
            memory_type: 记忆类型 ('private' | 'group')
            owner_id: 所有者 ID
            name: 记忆名称
            content: 记忆内容
            ttl: TTL 秒数（默认随机 24h-30h）
        """
        key = self._build_key(memory_type, owner_id, name)
        effective_ttl = ttl if ttl is not None else self._generate_ttl()
        self._redis.setex(key, effective_ttl, content)

    def delete(self, memory_type: str, owner_id: str, name: str) -> None:
        """删除单个缓存的记忆。

        Args:
            memory_type: 记忆类型 ('private' | 'group')
            owner_id: 所有者 ID
            name: 记忆名称
        """
        key = self._build_key(memory_type, owner_id, name)
        self._redis.delete(key)

    def invalidate_pattern(self, memory_type: str, owner_id: str) -> None:
        """按 pattern 删除用户所有缓存。

        Args:
            memory_type: 记忆类型 ('private' | 'group')
            owner_id: 所有者 ID
        """
        pattern = self._build_pattern(memory_type, owner_id)
        keys = self._redis.keys(pattern)
        if keys:
            self._redis.delete(*keys)

    def _build_key(self, memory_type: str, owner_id: str, name: str) -> str:
        """构建缓存 key。

        Args:
            memory_type: 记忆类型 ('private' | 'group')
            owner_id: 所有者 ID
            name: 记忆名称

        Returns:
            缓存 key
        """
        if memory_type == "group":
            return f"memory:group:{owner_id}:{name}"
        return f"memory:user:{owner_id}:{name}"

    def _build_pattern(self, memory_type: str, owner_id: str) -> str:
        """构建缓存 key pattern。

        Args:
            memory_type: 记忆类型 ('private' | 'group')
            owner_id: 所有者 ID

        Returns:
            缓存 key pattern
        """
        if memory_type == "group":
            return f"memory:group:{owner_id}:*"
        return f"memory:user:{owner_id}:*"

    def _generate_ttl(self) -> int:
        """生成随机 TTL。

        Returns:
            TTL 秒数 (86400-108000)
        """
        return DEFAULT_TTL_MIN + random.randint(0, DEFAULT_TTL_MAX - DEFAULT_TTL_MIN)  # nosec B311
