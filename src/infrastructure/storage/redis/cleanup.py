"""Redis Cleanup Utility.

提供安全的 Redis 键清理功能，使用 SCAN 而非 KEYS 命令，
避免在大键空间上造成阻塞。
"""

from __future__ import annotations

import logging
import threading

import redis

from src.infrastructure.config.redis import RedisConfig
from src.infrastructure.storage.redis.key_builder import build_key

logger = logging.getLogger(__name__)


class RedisCleanup:
    """Redis 清理工具。

    使用 SCAN 命令批量删除指定命名空间的键，
    避免使用 KEYS 命令造成的阻塞问题。

    Args:
        config: Redis 连接配置
    """

    def __init__(self, config: RedisConfig):
        """初始化 Redis 清理工具。

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

    def cleanup_namespace(self, namespace: str, batch_size: int = 100) -> int:
        """清理指定命名空间的所有键。

        使用 SCAN 命令迭代匹配的键，并批量删除。

        Args:
            namespace: 命名空间（如 session, cache:semantic, blackboard）
            batch_size: 每批扫描的键数量（默认 100）

        Returns:
            删除的键数量
        """
        pool = self._get_pool()
        deleted_count = 0

        try:
            with redis.Redis(connection_pool=pool) as client:
                pattern = build_key(namespace, "*")
                cursor = 0

                while True:
                    cursor, keys = client.scan(cursor=cursor, match=pattern, count=batch_size)

                    if keys:
                        batch_deleted = client.delete(*keys)
                        deleted_count += batch_deleted
                        logger.debug("Deleted %d keys matching pattern %s", batch_deleted, pattern)

                    if cursor == 0:
                        break

                logger.info(
                    "Cleanup completed for namespace %s: %d keys deleted",
                    namespace,
                    deleted_count,
                )

        except redis.ConnectionError as e:
            logger.error("Failed to cleanup namespace %s in Redis: %s", namespace, e)

        return deleted_count

    def close(self) -> None:
        """关闭连接池。"""
        if self._pool:
            self._pool.disconnect()
            self._pool = None
            logger.debug("Redis connection pool closed")

    def __enter__(self) -> RedisCleanup:
        """上下文管理器入口。"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器出口，确保连接池关闭。"""
        self.close()
        return None
