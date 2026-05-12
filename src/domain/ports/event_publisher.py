"""EventPublisher abstract port — hexagonal architecture publish interface.

应用层仅依赖此接口发布事件，不关心底层传输实现。
对标 NServiceBus 的 IBus.Publish 接口。
"""

from __future__ import annotations

from typing import Protocol

from src.domain.events.base import DomainEvent
from src.domain.events.publish_result import PublishResult


class EventPublisher(Protocol):
    """事件发布抽象端口。

    定义事件发布接口。
    实现类负责：
    1. 通道选择（通过 ChannelRouter 推断）
    2. 序列化（DomainEvent → JSON）
    3. 错误处理（内部消化，返回 PublishResult）
    """

    async def publish(self, event: DomainEvent, channel: str | None = None) -> PublishResult:
        """发布领域事件。

        通道选择由实现类通过 ChannelRouter 推断。

        Args:
            event: 领域事件实例
            channel: 事件发布通道（可选）

        Returns:
            PublishResult: 发布结果的不可变数据类
        """


class InMemoryEventPublisher(Protocol):
    """Abstract event publisher interface.

    Implementations in the infrastructure layer publish events to
    the appropriate message bus (RabbitMQ, Redis pub/sub, etc.).

    P1-07 Fix: Use Protocol to prevent direct instantiation (structural typing).
    """

    def publish(self, event: DomainEvent) -> None:
        """Publish a domain event.

        Args:
            event: The domain event to publish.

        Raises:
            NotImplementedError: Always, since this is an abstract interface.
        """
