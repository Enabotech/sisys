"""SISYS 基础设施层 Redis 会话存储模块

基于 Redis Hash 实现会话存储端口，支持自动过期

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import logging

import redis.asyncio as aioredis

from src.domain.ports.session_storage import SessionStorage
from src.infrastructure.storage.redis.key_builder import build_key
from src.infrastructure.utils import json_dumps, json_loads

logger = logging.getLogger(__name__)


class RedisSessionStorage(SessionStorage):
    """Redis 会话状态存储

    使用 Redis Hash (HSET/HGET/HDEL) 存储会话状态
    键格式: sisys:session:{session_id}
    支持自动 TTL 过期

    Args:
        redis_client: Redis 异步客户端（由 RedisConnectionManager 统一提供）
    """

    _NAMESPACE = "session"

    def __init__(self, redis_client: aioredis.Redis):
        """初始化 Redis Session Storage

        Args:
            redis_client: Redis 异步客户端
        """
        self._redis = redis_client

    async def save(self, session_id: str, agent_id: str, state: dict, ttl: int = 86400) -> None:
        """保存会话状态

        Args:
            session_id: 会话唯一标识
            agent_id: Agent 唯一标识
            state: 会话状态数据
            ttl: 过期时间（秒）

        Raises:
            aioredis.ConnectionError: Redis 连接失败时抛出
        """
        key = build_key(self._NAMESPACE, session_id)
        try:
            data = json_dumps({"session_id": session_id, "agent_id": agent_id, "state": state})
            await self._redis.hset(key, "data", data)
            await self._redis.expire(key, ttl)
            logger.debug("Saved session %s with TTL %d", session_id, ttl)
        except (aioredis.ConnectionError, aioredis.TimeoutError) as e:
            logger.error("Failed to save session %s to Redis: %s", session_id, e)

    async def load(self, session_id: str) -> dict | None:
        """加载会话状态

        Args:
            session_id: 会话唯一标识

        Returns:
            会话状态数据，如果不存在则返回 None
        """
        key = build_key(self._NAMESPACE, session_id)
        try:
            data = await self._redis.hget(key, "data")
            if data is None:
                return None
            raw = json_loads(data)
            if not isinstance(raw, dict):
                logger.warning("Unexpected data type in Redis key %s: %s", key, type(raw).__name__)
                return None
            return raw
        except (aioredis.ConnectionError, aioredis.TimeoutError) as e:
            logger.error("Failed to load session %s from Redis: %s", session_id, e)
            return None

    async def delete(self, session_id: str) -> None:
        """删除会话状态

        Args:
            session_id: 会话唯一标识

        Raises:
            aioredis.ConnectionError: Redis 连接失败时抛出
        """
        key = build_key(self._NAMESPACE, session_id)
        try:
            await self._redis.delete(key)
            logger.debug("Deleted session %s", session_id)
        except (aioredis.ConnectionError, aioredis.TimeoutError) as e:
            logger.error("Failed to delete session %s from Redis: %s", session_id, e)

    async def exists(self, session_id: str) -> bool:
        """检查会话状态是否存在

        Args:
            session_id: 会话唯一标识

        Returns:
            如果存在返回 True，否则返回 False

        Raises:
            aioredis.ConnectionError: Redis 连接失败时抛出
        """
        key = build_key(self._NAMESPACE, session_id)
        try:
            return (await self._redis.exists(key)) > 0
        except (aioredis.ConnectionError, aioredis.TimeoutError) as e:
            logger.error("Failed to check session %s existence in Redis: %s", session_id, e)
            return False

    async def __aenter__(self) -> RedisSessionStorage:
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器出口"""
        pass
