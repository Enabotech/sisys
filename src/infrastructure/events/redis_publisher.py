"""Redis Event Publisher — 基础设施层实现。

实现 Story 1.2 定义的 EventPublisher 接口。
用于 Redis Pub/Sub 实时通知通道（尽力而为，允许丢失）。
"""

from __future__ import annotations

import json
import logging

import redis

from src.domain.events.base import DomainEvent
from src.infrastructure.config.redis import RedisConfig

logger = logging.getLogger(__name__)


class RedisEventPublisher:
    """Redis Pub/Sub 事件发布器。

    使用连接池管理 Redis 连接，支持事件序列化后发布。
    注意：Redis 通道为"尽力而为"，不参与事务一致性与可靠投递承诺。
    """

    def __init__(self, config: RedisConfig):
        """初始化 RedisEventPublisher。

        Args:
            config: Redis 连接配置
        """
        self._config = config
        self._pool: redis.ConnectionPool | None = None

    def _get_pool(self) -> redis.ConnectionPool:
        """懒加载连接池。"""
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

    def publish(self, event: DomainEvent, channel: str) -> None:
        """发布事件到 Redis 频道。

        Args:
            event: 领域事件实例
            channel: Redis 频道名（推荐格式: sisys:rt:{event_type_lowercase}）

        Raises:
            redis.ConnectionError: 当 Redis 连接失败时
        """
        pool = self._get_pool()
        try:
            with redis.Redis(connection_pool=pool) as client:
                payload = json.dumps(event.to_dict())
                client.publish(channel, payload)
                logger.debug("Published event %s to channel %s", event.event_id, channel)
        except redis.ConnectionError as e:
            logger.error(
                "Failed to publish event %s to Redis channel %s: %s",
                event.event_id,
                channel,
                e,
            )
            raise

    def close(self) -> None:
        """关闭连接池。"""
        if self._pool:
            self._pool.disconnect()
            self._pool = None
            logger.debug("Redis connection pool closed")
