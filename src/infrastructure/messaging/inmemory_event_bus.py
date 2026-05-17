"""基础设施层内存事件总线模块。

基于内存的事件总线实现，支持幂等性去重和线程安全的事件分发，
适用于测试和 MVP 阶段

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import threading
import uuid

from src.domain.events.base import DomainEvent
from src.domain.events.listener import InMemoryEventListener
from src.domain.ports.event_publisher import InMemoryEventPublisher


class InMemoryEventBus(InMemoryEventPublisher):
    """内存事件总线，提供幂等性保证。

    维护已处理事件 ID 集合以防止重复处理，按事件类型分发到已注册的监听器。
    所有公共方法通过可重入锁保护线程安全。

    Attributes:
        processed_event_ids: 已处理的事件 ID 集合。
        listener: 用于分发事件的事件监听器。
    """

    def __init__(self, listener: InMemoryEventListener | None = None) -> None:
        """初始化内存事件总线。

        Args:
            listener: 可选的事件监听器，用于分发事件。
        """
        self._lock = threading.RLock()
        self.processed_event_ids: set[uuid.UUID] = set()
        self._listener = listener
        self._published_events: list[DomainEvent] = []

    def publish(self, event: DomainEvent) -> None:
        """发布领域事件（带幂等性检查）。

        事件先分发到监听器，成功后记录为已处理。
        若分发失败，事件可被重试。

        Args:
            event: 要发布的领域事件。

        Raises:
            ValueError: 当 event 为 None 时。
        """
        if event is None:
            raise ValueError("event must not be None")

        with self._lock:
            # 幂等性检查
            if event.event_id in self.processed_event_ids:
                return  # 已处理，跳过

            # 先分发到监听器，成功后记录为已处理
            if self._listener is not None:
                self._listener.dispatch(event)

            # 记录为已处理（仅在成功分发后）
            self.processed_event_ids.add(event.event_id)
            self._published_events.append(event)

    @property
    def published_events(self) -> list[DomainEvent]:
        """获取所有已发布事件列表（按发布顺序）。

        Returns:
            已发布事件的列表副本。
        """
        with self._lock:
            return list(self._published_events)

    def reset(self) -> None:
        """清空所有已处理事件 ID 和已发布事件列表（用于测试）。"""
        with self._lock:
            self.processed_event_ids.clear()
            self._published_events.clear()
