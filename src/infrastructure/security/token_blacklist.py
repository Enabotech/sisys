"""SISYS 基础设施层 Token 黑名单模块。

基于 Redis 实现已撤销 JWT token 的黑名单管理，支持与 token 剩余有效期相同的 TTL 自动过期。

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from datetime import timedelta

from src.domain.ports.token_blacklist import TokenBlacklistPort

# Token 黑名单 key 前缀
BLACKLIST_KEY_PREFIX = "token:blacklist:"


class RedisTokenBlacklist(TokenBlacklistPort):
    """基于 Redis 的 Token 黑名单实现，存储已撤销的 JWT token。

    Attributes:
        _redis: Redis 异步客户端实例
        _default_ttl: 默认过期时间
    """

    def __init__(self, redis_client, default_ttl_hours: int = 24):
        """初始化 Token 黑名单。

        Args:
            redis_client: Redis 客户端实例（aioredis）
            default_ttl_hours: 默认 TTL 小时数
        """
        self._redis = redis_client
        self._default_ttl = timedelta(hours=default_ttl_hours)

    def _get_key(self, token: str) -> str:
        """生成 token 对应的黑名单 key。

        Args:
            token: JWT token 字符串

        Returns:
            Redis key
        """
        # 使用 token 的 hash 作为 key，避免存储原始长 token
        import hashlib

        token_hash = hashlib.sha256(token.encode()).hexdigest()
        return f"{BLACKLIST_KEY_PREFIX}{token_hash}"

    async def add(self, token: str, ttl: timedelta | None = None) -> None:
        """将 token 加入黑名单。

        Args:
            token: JWT token 字符串
            ttl: 可选的过期时间（默认使用配置的 default_ttl）
        """
        key = self._get_key(token)
        if ttl is None:
            ttl = self._default_ttl
        await self._redis.setex(key, ttl, "1")

    async def is_blacklisted(self, token: str) -> bool:
        """检查 token 是否在黑名单中。

        Args:
            token: JWT token 字符串

        Returns:
            True 如果 token 已被撤销
        """
        key = self._get_key(token)
        result: int = await self._redis.exists(key)
        return result > 0
