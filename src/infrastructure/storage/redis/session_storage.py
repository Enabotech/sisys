"""Redis Session Storage — 基础设施层实现。

实现 Story 1.4 定义的 SessionStorage 接口。
使用 Redis Hash 存储会话状态，支持自动过期。
"""

from __future__ import annotations

import json
import logging
import threading

import redis

from src.infrastructure.config.redis import RedisConfig
from src.infrastructure.storage.redis.key_builder import build_key

logger = logging.getLogger(__name__)


class RedisSessionStorage:
    """Redis 会话状态存储。

    使用 Redis Hash (HSET/HGET/HDEL) 存储会话状态。
    键格式: sisys:session:{session_id}
    支持自动 TTL 过期。

    Args:
        config: Redis 连接配置
    """

    _NAMESPACE = "session"

    def __init__(self, config: RedisConfig):
        """初始化 Redis Session Storage。

        Args:
            config: Redis 连接配置
        """
        self._config = config
        self._pool: redis.ConnectionPool | None = None
        self._pool_lock = threading.Lock()

    def _get_pool(self) -> redis.ConnectionPool:
        """懒加载连接池（线程安全）。"""
        if self._pool is None:
            with self._pool_lock:
                if self._pool is None:
                    self._pool = redis.ConnectionPool(
                        host=self._config.host,
                        port=self._config.port,
                        db=self._config.db,
                        password=self._config.password,
                        max_connections=self._config.max_connections,
                        socket_timeout=self._config.socket_timeout,
                        decode_responses=True,
                    )
        return self._pool

    async def save(self, session_id: str, agent_id: str, state: dict, ttl: int = 86400) -> None:
        """保存会话状态。

        Args:
            session_id: 会话唯一标识
            agent_id: Agent 唯一标识
            state: 会话状态数据
            ttl: 过期时间（秒）

        Raises:
            redis.ConnectionError: Redis 连接失败时抛出
        """
        key = build_key(self._NAMESPACE, session_id)
        pool = self._get_pool()
        try:
            with redis.Redis(connection_pool=pool) as client:
                data = json.dumps({"session_id": session_id, "agent_id": agent_id, "state": state})
                client.hset(key, "data", data)
                client.expire(key, ttl)
                logger.debug("Saved session %s with TTL %d", session_id, ttl)
        except redis.ConnectionError as e:
            logger.error("Failed to save session %s to Redis: %s", session_id, e)
            raise

    async def load(self, session_id: str) -> dict | None:
        """加载会话状态。

        Args:
            session_id: 会话唯一标识

        Returns:
            会话状态数据，如果不存在则返回 None
        """
        key = build_key(self._NAMESPACE, session_id)
        pool = self._get_pool()
        try:
            with redis.Redis(connection_pool=pool) as client:
                data = client.hget(key, "data")
                if data is None:
                    return None
                raw = json.loads(data)
                if not isinstance(raw, dict):
                    logger.warning("Unexpected data type in Redis key %s: %s", key, type(raw).__name__)
                    return None
                return raw
        except redis.ConnectionError as e:
            logger.error("Failed to load session %s from Redis: %s", session_id, e)
            raise

    async def delete(self, session_id: str) -> None:
        """删除会话状态。

        Args:
            session_id: 会话唯一标识

        Raises:
            redis.ConnectionError: Redis 连接失败时抛出
        """
        key = build_key(self._NAMESPACE, session_id)
        pool = self._get_pool()
        try:
            with redis.Redis(connection_pool=pool) as client:
                client.delete(key)
                logger.debug("Deleted session %s", session_id)
        except redis.ConnectionError as e:
            logger.error("Failed to delete session %s from Redis: %s", session_id, e)
            raise

    async def exists(self, session_id: str) -> bool:
        """检查会话状态是否存在。

        Args:
            session_id: 会话唯一标识

        Returns:
            如果存在返回 True，否则返回 False

        Raises:
            redis.ConnectionError: Redis 连接失败时抛出
        """
        key = build_key(self._NAMESPACE, session_id)
        pool = self._get_pool()
        try:
            with redis.Redis(connection_pool=pool) as client:
                return client.exists(key) > 0
        except redis.ConnectionError as e:
            logger.error("Failed to check session %s existence in Redis: %s", session_id, e)
            raise

    def close(self) -> None:
        """关闭连接池。"""
        if self._pool:
            self._pool.disconnect()
            self._pool = None
            logger.debug("Redis connection pool closed")

    def __enter__(self) -> RedisSessionStorage:
        """上下文管理器入口。"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器出口，确保连接池关闭。"""
        self.close()
        return None
