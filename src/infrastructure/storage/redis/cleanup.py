"""基础设施层 Redis 清理工具模块

提供按命名空间批量清理 Redis 键的工具，使用 SCAN 命令（非 KEYS）避免阻塞 Redis
"""

from __future__ import annotations

import logging

import redis.asyncio as aioredis

from src.domain.exceptions import ValidationError
from src.infrastructure.storage.redis.key_builder import build_key

logger = logging.getLogger(__name__)


class RedisCleanup:
    """Redis 命名空间清理工具

    使用 SCAN 命令批量删除指定命名空间下的所有键
    支持自定义批次大小，避免一次性删除大量键导致 Redis 阻塞

    Args:
        config: Redis 连接配置
    """

    def __init__(self, redis_client: aioredis.Redis):
        """初始化 Redis 清理工具

        Args:
            redis_client: Redis 异步客户端（由 RedisConnectionManager 提供）
        """
        self._redis = redis_client

    async def cleanup_namespace(self, namespace: str, batch_size: int = 100) -> int:
        """清理指定命名空间下的所有键

        使用 SCAN 命令分批扫描并删除键，不阻塞 Redis

        Args:
            namespace: 命名空间（不能为空）
            batch_size: 每批扫描的键数量，默认 100

        Returns:
            删除的键数量

        Raises:
            ValidationError: namespace 为空时抛出
        """
        if not namespace:
            raise ValidationError(message="namespace cannot be empty")

        pattern = build_key(namespace, "*")
        deleted_count = 0

        try:
            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(cursor=cursor, match=pattern, count=batch_size)
                if keys:
                    batch_deleted = await self._redis.delete(*keys)
                    deleted_count += batch_deleted
                    logger.debug("Cleaned up %d keys in namespace %s", batch_deleted, namespace)

                if cursor == 0:
                    break

            logger.info("Total cleaned up %d keys in namespace %s", deleted_count, namespace)
            return deleted_count

        except (aioredis.ConnectionError, aioredis.TimeoutError) as e:
            logger.error("Failed to cleanup namespace %s in Redis: %s", namespace, e)
            raise

    async def __aenter__(self) -> RedisCleanup:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass
