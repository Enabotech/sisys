"""领域层事件监听器接口模块

定义在领域层，由基础设施层实现。支持为特定事件类型注册处理器

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from .base import DomainEvent


class EventListener(Protocol):
    """抽象事件监听器接口

    订阅者为特定事件类型注册处理器，事件发布时接收通知
    """

    def on_event(self, event_type: str, handler: Callable[[DomainEvent], None]) -> None:
        """注册特定事件类型的处理器

        Args:
            event_type: 要监听的事件类型
            handler: 接收领域事件的回调函数
        """

    def dispatch(self, event: DomainEvent) -> None:
        """将事件分发给所有已注册的处理器

        Args:
            event: 要分发的领域事件
        """


class InMemoryEventListener:
    """内存事件监听器实现（MVP）

    维护事件类型到处理器函数的映射。事件分发时，调用该事件类型的所有处理器
    """

    def __init__(self) -> None:
        """初始化监听器，使用空的处理器注册表"""
        from collections import defaultdict

        self._handlers: dict[str, list[Callable[[DomainEvent], None]]] = defaultdict(list)

    def on_event(self, event_type: str, handler: Callable[[DomainEvent], None]) -> None:
        """注册特定事件类型的处理器

        Args:
            event_type: 要监听的事件类型
            handler: 接收领域事件的回调函数
        """
        self._handlers[event_type].append(handler)

    def dispatch(self, event: DomainEvent) -> None:
        """将事件分发给对应类型的所有已注册处理器

        每个处理器用 try/except 包裹，防止单个处理器失败阻塞后续处理器

        Args:
            event: 要分发的领域事件
        """
        errors: list[Exception] = []
        for handler in self._handlers.get(event.event_type, []):
            try:
                handler(event)
            except Exception as e:  # noqa: BLE001 - log and continue
                errors.append(e)
        if errors:
            raise ExceptionGroup(
                f"{len(errors)} handler(s) failed for event {event.event_type}",
                errors,
            )

    @property
    def registered_event_types(self) -> list[str]:
        """返回已注册处理器的事件类型列表

        Returns:
            已注册事件类型字符串列表
        """
        return list(self._handlers.keys())


# =============================================================================
# AC-5: EventListenerAsync - 异步事件处理器接口
# =============================================================================


class EventListenerAsync(Protocol):
    """抽象异步事件监听器接口

    用于异步事件消费场景（RabbitMQEventListener 实现）
    与同步 EventListener 接口独立，不继承以避免强制实现同步方法
    """

    async def async_handle(self, event: DomainEvent) -> None:
        """异步处理事件

        Args:
            event: 要处理的事件
        """


# =============================================================================
# DeadLetterQueue - 死信队列接口
# =============================================================================


class DeadLetterQueue(Protocol):
    """死信队列抽象接口"""

    def enqueue(self, event: DomainEvent, error: str, retry_count: int = 0) -> None:
        """入队失败事件

        Args:
            event: 领域事件
            error: 错误信息
            retry_count: 重试次数
        """

    def dequeue(self) -> tuple[DomainEvent, str, int] | None:
        """出队失败事件

        Returns:
            (event, error, retry_count) 或 None
        """

    def __len__(self) -> int:
        """队列长度"""


class InMemoryDeadLetterQueue:
    """内存死信队列 — MVP 阶段使用

    进程重启后丢失，仅用于测试和 MVP 占位
    """

    def __init__(self) -> None:
        import logging

        self._items: list[tuple[DomainEvent, str, int]] = []
        self._logger = logging.getLogger(__name__)

    def enqueue(self, event: DomainEvent, error: str, retry_count: int = 0) -> None:
        """入队失败事件"""
        self._items.append((event, error, retry_count))
        self._logger.warning(
            "Event %s enqueued to DLQ: %s (retry_count=%d)",
            event.event_id,
            error,
            retry_count,
        )

    def dequeue(self) -> tuple[DomainEvent, str, int] | None:
        """出队失败事件（FIFO）"""
        return self._items.pop(0) if self._items else None

    def __len__(self) -> int:
        return len(self._items)
