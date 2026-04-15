"""Redis Cleanup Utility — 基础设施层实现。

提供按命名空间批量清理 Redis 键的工具。
使用 SCAN 命令（非 KEYS）避免阻塞 Redis。
"""

from __future__ import annotations

import asyncio
import logging

import redis.asyncio as aioredis

from src.infrastructure.config.redis import RedisConfig
from src.infrastructure.storage.redis.key_builder import build_key

logger = logging.getLogger(__name__)


class RedisCleanup:
    """Redis 命名空间清理工具。

    使用 SCAN 命令批量删除指定命名空间下的所有键。
    支持自定义批次大小，避免一次性删除大量键导致 Redis 阻塞。

    Args:
        config: Redis 连接配置
    """

    def __init__(self, config: RedisConfig):
        """初始化 Redis 清理工具。

        Args:
            config: Redis 连接配置
        """
        self._config = config
        self._pool: aioredis.ConnectionPool | None = None
        self._pool_lock = asyncio.Lock()

    def _get_pool(self) -> aioredis.ConnectionPool:
        """懒加载连接池（异步安全）。"""
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
        return self._pool

    async def cleanup_namespace(self, namespace: str, batch_size: int = 100) -> int:
        """清理指定命名空间下的所有键。

        使用 SCAN 命令分批扫描并删除键，不阻塞 Redis。

        Args:
            namespace: 命名空间（不能为空）
            batch_size: 每批扫描的键数量，默认 100

        Returns:
            删除的键数量

        Raises:
            ValueError: namespace 为空时抛出
        """
        if not namespace:
            raise ValueError("namespace cannot be empty")

        pattern = build_key(namespace, "*")
        pool = self._get_pool()
        deleted_count = 0

        try:
            async with aioredis.Redis(connection_pool=pool) as client:
                cursor = 0
                while True:
                    cursor, keys = await client.scan(cursor=cursor, match=pattern, count=batch_size)
                    if keys:
                        batch_deleted = await client.delete(*keys)
                        deleted_count += batch_deleted
                        logger.debug("Cleaned up %d keys in namespace %s", batch_deleted, namespace)

                    if cursor == 0:
                        break

                logger.info("Total cleaned up %d keys in namespace %s", deleted_count, namespace)
                return deleted_count

        except (aioredis.ConnectionError, aioredis.TimeoutError) as e:
            logger.error("Failed to cleanup namespace %s in Redis: %s", namespace, e)
            raise

    async def close(self) -> None:
        """异步关闭连接池。"""
        if self._pool:
            await self._pool.aclose()  # type: ignore[attr-defined]
            self._pool = None
            logger.debug("Redis connection pool closed")

    async def __aenter__(self) -> RedisCleanup:
        """异步上下文管理器入口。"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器出口，确保连接池关闭。"""
        await self.close()
