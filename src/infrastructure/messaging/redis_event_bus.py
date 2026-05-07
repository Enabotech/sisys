"""RedisEventBus — Redis Pub/Sub real-time event bus implementation."""

from __future__ import annotations

from typing import Any

from src.application.ports.event_subscriber import EventSubscriber
from src.domain.events.base import DomainEvent
from src.domain.events.publish_result import PublishResult
from src.domain.ports.event_publisher import EventPublisher
from src.infrastructure.messaging.channel_router import ChannelRouter


class RedisEventBus(EventPublisher, EventSubscriber):
    """Redis Pub/Sub 事件总线实现。

    实现 EventPublisher 和 EventSubscriber 接口。
    通过 ChannelRouter 推断事件类型对应的传输通道。
    """

    def __init__(
        self,
        publisher: Any,
        subscriber: Any,
        router: ChannelRouter,
    ) -> None:
        """初始化 RedisEventBus。

        Args:
            publisher: Redis 发布器（异步）
            subscriber: Redis 订阅器
            router: 通道路由器
        """
        self._publisher = publisher
        self._subscriber = subscriber
        self._router = router

    async def publish(self, event: DomainEvent) -> PublishResult:
        """发布事件到 Redis 通道。

        Args:
            event: 领域事件

        Returns:
            PublishResult: 发布结果
        """
        channel = self._router.get_redis_channel(event.event_type)
        if channel is None:
            return PublishResult(
                event_id=str(event.event_id),
                redis_success=False,
            )

        try:
            await self._publisher.publish(event, channel)
            return PublishResult(
                event_id=str(event.event_id),
                redis_success=True,
            )
        except Exception as e:
            return PublishResult(
                event_id=str(event.event_id),
                redis_success=False,
                redis_error=str(e),
            )

    async def subscribe(
        self,
        event_type: str,
        handler: Any,
    ) -> None:
        """订阅领域事件。

        Args:
            event_type: 事件类型
            handler: 事件处理器
        """
        await self._subscriber.subscribe(event_type, handler)

    async def subscribe_async(
        self,
        event_type: str,
        handler: Any,
    ) -> None:
        """订阅领域事件（支持异步处理器）。

        Args:
            event_type: 事件类型
            handler: 异步事件处理器
        """
        await self._subscriber.subscribe_async(event_type, handler)

    async def start(self) -> None:
        """启动订阅者。"""
        await self._subscriber.start()

    async def close(self) -> None:
        """关闭发布者和订阅者。"""
        await self._publisher.close()
        await self._subscriber.close()
