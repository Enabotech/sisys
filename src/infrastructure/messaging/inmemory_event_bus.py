"""基础设施层内存事件总线模块

基于内存的事件总线实现，支持幂等性去重和异步事件分发，
适用于测试和 MVP 阶段
"""

from __future__ import annotations

import asyncio
import uuid

from src.domain.events.base import DomainEvent
from src.domain.events.publish_result import ChannelResult, PublishResult
from src.domain.exceptions import ValidationError
from src.domain.ports.event_publisher import EventPublisher
from src.infrastructure.messaging.inmemory_event_listener import InMemoryEventListener


class InMemoryEventBus(EventPublisher):
    """内存事件总线，提供幂等性保证

    实现 EventPublisher Protocol，维护已处理事件 ID 集合以防止重复处理
    按事件类型分发到已注册的监听器
    """

    def __init__(self, listener: InMemoryEventListener | None = None) -> None:
        """初始化内存事件总线

        Args:
            listener: 可选的事件监听器，用于分发事件
        """
        self._lock = asyncio.Lock()
        self.processed_event_ids: set[uuid.UUID] = set()
        self._listener = listener
        self._published_events: list[DomainEvent] = []

    async def publish(self, event: DomainEvent) -> PublishResult:
        """发布领域事件（带幂等性检查）

        事件先分发到监听器，成功后记录为已处理
        若分发失败，事件可被重试

        Args:
            event: 要发布的领域事件

        Returns:
            PublishResult: 发布结果
        """
        if event is None:
            raise ValidationError(message="event must not be None")

        async with self._lock:
            if event.event_id in self.processed_event_ids:
                return PublishResult(event_id=str(event.event_id))

            if self._listener is not None:
                self._listener.dispatch(event)

            self.processed_event_ids.add(event.event_id)
            self._published_events.append(event)
            return PublishResult(
                event_id=str(event.event_id),
                results=(ChannelResult("inmemory", True),),
            )

    @property
    def published_events(self) -> list[DomainEvent]:
        """获取所有已发布事件列表（按发布顺序）"""
        return list(self._published_events)

    def reset(self) -> None:
        """清空所有已处理事件 ID 和已发布事件列表（用于测试）"""
        self.processed_event_ids.clear()
        self._published_events.clear()
