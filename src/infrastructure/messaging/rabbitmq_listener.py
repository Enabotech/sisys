"""RabbitMQEventListener — 异步事件监听器实现

实现 EventListenerAsync 接口，用于异步事件消费
集成：
- DualIdempotencyChecker: Redis + PostgreSQL 双写幂等性检查
- RedisRetryQueue: 延迟重试队列
- PostgresDeadLetterQueue: 死信队列
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractQueue

from src.domain.events.base import DomainEvent
from src.domain.events.listener import EventListenerAsync
from src.infrastructure.config.rabbitmq import RabbitMQConfig
from src.infrastructure.messaging.retry.dual_idempotency_checker import (
    DualIdempotencyChecker,
)
from src.infrastructure.messaging.retry.redis_retry_queue import RedisRetryQueue

if TYPE_CHECKING:
    import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class RabbitMQEventListener(EventListenerAsync):
    """RabbitMQ 异步事件监听器

    实现 EventListenerAsync 接口，用于消费 RabbitMQ 消息
    集成幂等性检查、重试队列和死信队列

    Args:
        config: RabbitMQ 配置
        redis_client: Redis 客户端
        session: PostgreSQL 会话
    """

    def __init__(
        self,
        config: RabbitMQConfig,
        redis_client: aioredis.Redis,
    ):
        """初始化 RabbitMQEventListener

        Args:
            config: RabbitMQ 连接配置
            redis_client: 异步 Redis 客户端
        """
        self._config = config
        self._redis = redis_client
        self._idempotency = DualIdempotencyChecker(
            redis_client=redis_client,
        )
        self._retry_queue = RedisRetryQueue(redis_client=redis_client)
        # Dead letter queue will be set separately
        self._dlq = None
        self._connection: AbstractConnection | None = None
        self._channel: AbstractChannel | None = None
        self._queue: AbstractQueue | None = None

    def set_dead_letter_queue(self, dlq: Any) -> None:
        """设置死信队列

        Args:
            dlq: PostgresDeadLetterQueue 实例
        """
        self._dlq = dlq

    async def async_handle(self, event: DomainEvent) -> None:
        """异步处理事件

        Args:
            event: 要处理的事件

        Raises:
            Exception: 处理失败时根据重试策略决定是否重试
        """
        # 幂等性检查
        acquired = await self._idempotency.try_acquire(event.event_id)
        if not acquired:
            logger.debug("Event %s already processed, skipping", event.event_id)
            return

        try:
            # 事件处理逻辑（由子类或外部提供）
            await self._process_event(event)
        except Exception as e:
            logger.error("Error processing event %s: %s", event.event_id, e)
            # 失败时加入重试队列
            await self._retry_queue.enqueue(
                event_id=event.event_id,
                event_type=event.event_type,
                payload=event.to_dict(),
                retry_at=event.timestamp,  # Will be adjusted by retry policy
                retry_count=0,
                error=str(e),
            )
            raise

    async def _process_event(self, event: DomainEvent) -> None:
        """处理事件的实际逻辑

        Args:
            event: 领域事件
        """
        # Placeholder - actual processing would be done by registered handlers
        logger.debug("Processing event %s of type %s", event.event_id, event.event_type)

    async def connect(self) -> None:
        """连接到 RabbitMQ"""
        self._connection = await aio_pika.connect_robust(
            host=self._config.host,
            port=self._config.port,
            login=self._config.username,
            password=self._config.password,
            virtualhost=self._config.virtual_host,
        )
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=self._config.prefetch_count)
        logger.info("RabbitMQEventListener connected")

    async def close(self) -> None:
        """关闭连接"""
        if self._channel:
            await self._channel.close()
        if self._connection:
            await self._connection.close()
        logger.info("RabbitMQEventListener disconnected")
