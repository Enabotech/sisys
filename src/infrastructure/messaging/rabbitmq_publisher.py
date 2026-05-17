"""Async RabbitMQ Publisher — 基础设施层实现

统一 async 路径，使用 aio-pika 异步客户端
实现可靠事件传输，消息持久化
"""

from __future__ import annotations

import json
import logging

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractExchange

from src.domain.events.base import DomainEvent
from src.infrastructure.config.rabbitmq import RabbitMQConfig

logger = logging.getLogger(__name__)


class RabbitMQPublisher:
    """异步 RabbitMQ 事件发布器

    使用 aio-pika connect_robust 实现自动重连
    所有操作统一使用 async/await
    """

    def __init__(self, config: RabbitMQConfig):
        """初始化 RabbitMQPublisher

        Args:
            config: RabbitMQ 连接配置
        """
        self._config = config
        self._connection: AbstractConnection | None = None
        self._channel: AbstractChannel | None = None
        self._exchange: AbstractExchange | None = None

    async def connect(self) -> None:
        """连接到 RabbitMQ

        使用 connect_robust: 连接断开时自动重连
        连接成功后重新声明交换机
        """
        self._connection = await aio_pika.connect_robust(
            host=self._config.host,
            port=self._config.port,
            login=self._config.username,
            password=self._config.password,
            virtualhost=self._config.virtual_host,
        )
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=self._config.prefetch_count)

        # 声明交换机（每次连接后重新声明，确保重连后交换机存在）
        self._exchange = await self._channel.declare_exchange(
            self._config.exchange_name,
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )
        logger.info(
            "Connected to RabbitMQ, exchange declared: %s",
            self._config.exchange_name,
        )

    async def async_publish(
        self,
        event: DomainEvent,
        routing_key: str,
        retry_count: int = 0,
    ) -> None:
        """异步发布事件到 RabbitMQ

        Args:
            event: 领域事件实例
            routing_key: 路由键（格式: sisys.events.reliable.{event_type}）
            retry_count: 重试计数（用于消息头）

        Raises:
            RuntimeError: 如果未调用 connect() 先
        """
        if not self._exchange:
            raise RuntimeError("Not connected. Call connect() first.")

        payload = json.dumps(event.to_dict())
        message = aio_pika.Message(
            body=payload.encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
            message_id=str(event.event_id),
            headers={"x-retry-count": str(retry_count)},
        )

        await self._exchange.publish(message, routing_key=routing_key)
        logger.debug(
            "Published event %s to routing key %s",
            event.event_id,
            routing_key,
        )

    async def close(self) -> None:
        """关闭连接"""
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
            logger.info("RabbitMQ connection closed")
