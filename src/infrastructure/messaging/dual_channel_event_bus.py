"""DualChannelEventBus — unified event bus facade."""

from __future__ import annotations

from typing import Any

from src.domain.events.base import DomainEvent
from src.domain.events.publish_result import PublishResult
from src.domain.ports.event_publisher import EventPublisher
from src.infrastructure.messaging.channel_router import ChannelRouter, DeliveryMode
from src.infrastructure.messaging.rabbitmq_event_bus import RabbitMQEventBus
from src.infrastructure.messaging.redis_event_bus import RedisEventBus


class DualChannelEventBus(EventPublisher):
    """统一双通道事件总线入口

    根据 ChannelRouter 推断 DeliveryMode，将事件路由到对应通道：
    - REALTIME: RedisEventBus (Redis Pub/Sub)
    - RELIABLE: RabbitMQEventBus (Outbox 模式)

    订阅仅支持 REALTIME 模式，RELIABLE 模式抛出 ValueError
    """

    def __init__(
        self,
        redis_bus: RedisEventBus,
        rabbitmq_bus: RabbitMQEventBus,
        router: ChannelRouter,
    ) -> None:
        """初始化 DualChannelEventBus

        Args:
            redis_bus: Redis 实时通道总线
            rabbitmq_bus: RabbitMQ 可靠通道总线
            router: 通道路由器
        """
        self._redis_bus = redis_bus
        self._rabbitmq_bus = rabbitmq_bus
        self._router = router

    async def publish(self, event: DomainEvent, channel: str | None = None) -> PublishResult:
        """发布领域事件

        根据 DeliveryMode 路由到对应通道

        Args:
            event: 领域事件
            channel: 事件发布通道（可选）

        Returns:
            PublishResult: 组合发布结果
        """
        mode = self._router.get_delivery_mode(event.event_type)

        if mode == DeliveryMode.REALTIME:
            redis_result = await self._redis_bus.publish(event)
            return redis_result
        else:
            rabbitmq_result = await self._rabbitmq_bus.publish(event)
            return rabbitmq_result

    async def subscribe(
        self,
        event_type: str,
        handler: Any,
    ) -> None:
        """订阅领域事件（仅支持 REALTIME）

        Args:
            event_type: 事件类型
            handler: 事件处理器

        Raises:
            ValueError: 当事件类型为 RELIABLE 模式时
        """
        mode = self._router.get_delivery_mode(event_type)
        if mode == DeliveryMode.RELIABLE:
            raise ValueError(f"RELIABLE mode does not support subscribe: {event_type}")
        await self._redis_bus.subscribe(event_type, handler)

    async def start(self) -> None:
        """启动事件总线"""
        await self._redis_bus.start()

    async def close(self) -> None:
        """关闭事件总线"""
        await self._redis_bus.close()
        await self._rabbitmq_bus.close()
