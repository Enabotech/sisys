"""基础设施层 RabbitMQ 异步事件消费者模块

基于 aio-pika 实现异步事件消费，使用手动 ACK/NACK 策略，
失败时通过 RedisRetryQueue 进行延迟重试，超过最大重试次数后进入死信队列

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractIncomingMessage, AbstractQueue

from src.domain.events.base import DomainEvent
from src.domain.ports.dead_letter_queue import DeadLetterQueue
from src.infrastructure.config.rabbitmq import RabbitMQConfig
from src.infrastructure.messaging.retry.redis_retry_queue import RedisRetryQueue

logger = logging.getLogger(__name__)

# 事件处理器类型
EventProcessor = Callable[[DomainEvent], Any]

DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY_SECONDS = 30


class RabbitMQConsumer:
    """异步 RabbitMQ 事件消费者

    使用手动 ACK/NACK 策略：
    - 成功时 ack()
    - 失败时通过 RedisRetryQueue 延迟重试
    - 超过最大重试次数时 nack(requeue=False) 死信
    """

    def __init__(
        self,
        config: RabbitMQConfig,
        idempotency_checker: Any = None,
        metrics_collector: Any = None,
        dlq: DeadLetterQueue | None = None,
        retry_queue: RedisRetryQueue | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay_seconds: int = DEFAULT_RETRY_DELAY_SECONDS,
    ):
        """初始化 RabbitMQConsumer

        Args:
            config: RabbitMQ 连接配置
            idempotency_checker: 幂等性检查器 (IdempotencyChecker)
            metrics_collector: 指标收集器 (EventMetricsCollector)
            dlq: 死信队列 (DeadLetterQueue)
            retry_queue: Redis 延迟重试队列 (RedisRetryQueue)
            max_retries: 最大重试次数
            retry_delay_seconds: 基础重试延迟秒数（指数退避）
        """
        self._config = config
        self._idempotency = idempotency_checker
        self._metrics = metrics_collector
        self._dlq = dlq
        self._retry_queue = retry_queue
        self._max_retries = max_retries
        self._retry_delay_seconds = retry_delay_seconds
        self._connection: AbstractConnection | None = None
        self._channel: AbstractChannel | None = None
        self._handlers: dict[str, list[EventProcessor]] = {}

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
        logger.info("RabbitMQConsumer connected")

    def register_handler(self, queue_name: str, handler: EventProcessor) -> None:
        """注册事件处理器

        Args:
            queue_name: 队列名
            handler: 事件处理器协程
        """
        if queue_name not in self._handlers:
            self._handlers[queue_name] = []
        self._handlers[queue_name].append(handler)

    async def async_consume(self, queue_name: str) -> AbstractQueue:
        """开始消费指定队列

        Args:
            queue_name: 队列名

        Returns:
            声明队列对象
        """
        # 声明队列（不自动 ACK）
        assert self._channel is not None, "Must call connect() before async_consume()"
        queue = await self._channel.declare_queue(queue_name, durable=True)
        await queue.consume(self._on_message)
        logger.info("Started consuming from queue: %s", queue_name)
        return queue

    async def bind_queue(self, queue_name: str, routing_key: str, exchange_name: str = "sisys.events.reliable") -> None:
        """绑定队列到交换器

        Args:
            queue_name: 队列名
            routing_key: 路由键（用于绑定）
            exchange_name: 交换器名，默认使用配置的交换器名
        """
        assert self._channel is not None, "Must call connect() before bind_queue()"
        queue = await self._channel.declare_queue(queue_name, durable=True)
        exchange = await self._channel.declare_exchange(exchange_name, aio_pika.ExchangeType.TOPIC, durable=True)
        await queue.bind(exchange, routing_key=routing_key)
        logger.info("Bound queue %s to exchange %s with routing key %s", queue_name, exchange_name, routing_key)

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        """消息处理回调，执行手动 ACK/NACK

        处理流程：反序列化 -> 幂等性检查 -> 执行处理器 -> ACK，
        失败时根据重试策略决定重试或死信

        Args:
            message: RabbitMQ 原始消息
        """
        event: DomainEvent | None = None  # 预先初始化为 None
        try:
            # 1. 反序列化
            event_dict = json.loads(message.body.decode())
            event_type = event_dict.get("event_type")
            # 验证 event_type 已注册
            if event_type not in DomainEvent._registry:
                raise ValueError(f"Unknown event_type: {event_type}")
            # 使用 DomainEvent.from_dict 正确处理 event_type
            # (subclass.from_dict fails because subclasses have event_type as init=False)
            event = DomainEvent.from_dict(event_dict)
            if event is None:
                logger.warning("Failed to deserialize event, rejecting message")
                await message.nack(requeue=False)
                return

            # 2. 幂等性检查（原子操作，异步）
            if self._idempotency and not await self._idempotency.try_acquire(event.event_id):
                await message.ack()  # 已处理，确认
                return

            # 3. 执行处理器
            start = time.time()
            # 优先匹配事件类型处理器，回退到默认处理器
            handlers = self._handlers.get(event_type, self._handlers.get("default", []))
            for handler in handlers:
                await handler(event)
            duration = time.time() - start

            # 4. 成功 → 手动 ACK
            await message.ack()
            if self._metrics:
                self._metrics.record_processed(event.event_type, duration)

        except Exception as e:
            # 5. 失败 → 决定重试或死信
            if event is None:
                # 反序列化失败，event 未定义 → 直接死信
                await message.nack(requeue=False)
                return
            await self._handle_failure(message, event, e)

    async def _handle_failure(
        self,
        message: AbstractIncomingMessage,
        event: DomainEvent,
        error: Exception,
    ) -> None:
        """失败处理，使用 RedisRetryQueue 延迟重试或发送到死信队列

        Args:
            message: RabbitMQ 原始消息
            event: 处理失败的领域事件
            error: 异常信息
        """
        retry_count = 0
        if message.headers:
            retry_count_raw = message.headers.get("x-retry-count", "0")
            try:
                retry_count = int(str(retry_count_raw)) if retry_count_raw else 0
            except (ValueError, TypeError):
                retry_count = 0

        # 超过最大重试次数 → 死信队列
        if retry_count >= self._max_retries:
            await message.nack(requeue=False)
            if self._dlq:
                await self._dlq.enqueue(event, str(error), retry_count)
            if self._metrics:
                self._metrics.record_dlq(event.event_type)
            logger.error(
                "Event %s failed after %d retries, sent to DLQ: %s",
                event.event_id,
                retry_count,
                error,
            )
            return

        # 通过 RedisRetryQueue 延迟重试
        if self._retry_queue:
            try:
                delay = self._retry_delay_seconds * (2**retry_count)
                retry_at = datetime.now(UTC) + timedelta(seconds=delay)
                await self._retry_queue.enqueue(
                    event_id=event.event_id,
                    event_type=event.event_type,
                    payload=event.to_dict(),
                    retry_at=retry_at,
                    retry_count=retry_count + 1,
                    error=str(error),
                )
                await message.ack()
                if self._metrics:
                    self._metrics.record_retried(event.event_type)
                logger.warning(
                    "Event %s failed, enqueued to retry queue (attempt %d/%d): %s",
                    event.event_id,
                    retry_count + 1,
                    self._max_retries,
                    error,
                )
                return
            except Exception as rq_error:
                logger.error(
                    "RedisRetryQueue.enqueue failed for event %s, falling back to nack(requeue=True): %s",
                    event.event_id,
                    rq_error,
                )

        # 降级：nack(requeue=True) 让 RabbitMQ 重新投递
        await message.nack(requeue=True)

    async def close(self) -> None:
        """关闭连接"""
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
            logger.info("RabbitMQConsumer connection closed")
