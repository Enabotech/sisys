"""SISYS 基础设施层 Redis 连接管理器模块

集中管理 Redis 异步连接池生命周期，所有 Redis 组件
应通过此管理器获取客户端而非自建连接池
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import redis.asyncio as aioredis

from src.domain.ports.connection_manager import ConnectionManager
from src.infrastructure.config.redis import RedisConfig

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class RedisManager(ConnectionManager):
    """Redis async connection lifecycle manager.

    Lazily creates a single aioredis.ConnectionPool and provides
    aioredis.Redis instances to all Redis components.

    Args:
        config: Redis connection configuration
    """

    def __init__(self, config: RedisConfig):
        """Initialize RedisConnectionManager.

        Args:
            config: Redis connection configuration
        """
        self._config = config
        self._pool: aioredis.ConnectionPool | None = None
        self._redis: aioredis.Redis | None = None

    def get_client(self) -> aioredis.Redis:
        """Get an aioredis.Redis client backed by the shared connection pool.

        Returns:
            Redis async client instance (cached, same instance per manager)
        """
        if self._pool is None:
            self._pool = aioredis.ConnectionPool(
                host=self._config.host,
                port=self._config.port,
                db=self._config.db,
                password=self._config.password,
                max_connections=self._config.max_connections,
                socket_timeout=self._config.socket_timeout,
                decode_responses=True,
            )
            logger.info(
                "Created Redis connection pool: %s:%d/%d (max_connections=%d)",
                self._config.host,
                self._config.port,
                self._config.db,
                self._config.max_connections,
            )
        if self._redis is None:
            self._redis = aioredis.Redis(connection_pool=self._pool)
        return self._redis

    async def health_check(self) -> bool:
        """Check Redis connection health via PING."""
        try:
            client = self.get_client()
            return await client.ping()
        except Exception as e:
            logger.error("Redis health check failed: %s", e)
            return False

    async def close(self) -> None:
        """Close the connection pool and release all connections."""
        if self._redis is not None:
            await self._redis.close()
            self._redis = None
        if self._pool is not None:
            await self._pool.disconnect()
            self._pool = None
            logger.info("Redis connection pool closed")
