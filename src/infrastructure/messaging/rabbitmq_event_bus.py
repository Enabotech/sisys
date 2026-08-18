"""基础设施层 RabbitMQ 事件总线模块

基于 Outbox 模式实现可靠事件传输，事件先持久化到发件箱再异步发布到
RabbitMQ，保证消息不丢失
"""

from __future__ import annotations

from typing import Any

from src.domain.events.base import DomainEvent
from src.domain.events.publish_result import ChannelResult, PublishResult
from src.domain.ports.event_publisher import EventPublisher
from src.infrastructure.messaging.channel_router import ChannelRouter


class RabbitMQEventBus(EventPublisher):
    """RabbitMQ RELIABLE 通道事件总线实现

    通过 Outbox 模式保证可靠传输：
    1. publish() 将事件保存到 Outbox（与业务操作同事务）
    2. AsyncOutboxPoller 异步读取 Outbox 并发布到 RabbitMQ
    """

    def __init__(
        self,
        outbox_repository: Any,
        router: ChannelRouter,
    ) -> None:
        """初始化 RabbitMQEventBus

        Args:
            outbox_repository: Outbox 仓储实现
            router: 通道路由器
        """
        self._outbox_repo = outbox_repository
        self._router = router

    async def publish(self, event: DomainEvent) -> PublishResult:
        """发布事件到 Outbox（可靠路径）

        Args:
            event: 领域事件
            channel: 事件发布通道（可选）

        Returns:
            PublishResult: 发布结果
        """
        routing_key = self._router.get_rabbitmq_routing_key(event.event_type)
        if routing_key is None:
            return PublishResult(
                event_id=str(event.event_id),
                results=(ChannelResult("reliable", False, f"No routing key mapping for {event.event_type}"),),
            )

        try:
            await self._outbox_repo.save(event)
            return PublishResult(
                event_id=str(event.event_id),
                results=(ChannelResult("reliable", True),),
            )
        except Exception as e:
            return PublishResult(
                event_id=str(event.event_id),
                results=(ChannelResult("reliable", False, str(e)),),
            )

    async def close(self) -> None:
        """关闭事件总线（无资源需清理）"""
        pass
