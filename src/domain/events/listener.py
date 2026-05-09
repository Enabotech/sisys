"""Event listener interface.

Defined in the domain layer, implemented in the infrastructure layer.
Supports registering handlers for specific event types.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from .base import DomainEvent


class EventListener(Protocol):
    """Abstract event listener interface.

    Subscribers register handlers for specific event types
    and receive events when they are published.
    """

    def on_event(self, event_type: str, handler: Callable[[DomainEvent], None]) -> None:
        """Register a handler for a specific event type.

        Args:
            event_type: The type of event to listen for.
            handler: Callback function that receives the domain event.
        """

    def dispatch(self, event: DomainEvent) -> None:
        """Dispatch an event to all registered handlers.

        Args:
            event: The domain event to dispatch.
        """


class InMemoryEventListener:
    """In-memory event listener implementation (MVP).

    Maintains a mapping of event types to handler functions.
    When an event is dispatched, all handlers for that event type are called.
    """

    def __init__(self) -> None:
        """Initialize the listener with an empty handler registry."""
        from collections import defaultdict

        self._handlers: dict[str, list[Callable[[DomainEvent], None]]] = defaultdict(list)

    def on_event(self, event_type: str, handler: Callable[[DomainEvent], None]) -> None:
        """Register a handler for a specific event type.

        Args:
            event_type: The type of event to listen for.
            handler: Callback function that receives the domain event.
        """
        self._handlers[event_type].append(handler)

    def dispatch(self, event: DomainEvent) -> None:
        """Dispatch an event to all registered handlers for its type.

        Each handler is wrapped in try/except to prevent one handler's
        failure from blocking subsequent handlers.

        Args:
            event: The domain event to dispatch.
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
        """Return list of event types that have registered handlers."""
        return list(self._handlers.keys())


# =============================================================================
# AC-5: EventListenerAsync - 异步事件处理器接口
# =============================================================================


class EventListenerAsync(Protocol):
    """Abstract async event listener interface.

    用于异步事件消费场景（RabbitMQEventListener 实现）。
    与同步 EventListener 接口独立，不继承以避免强制实现同步方法。
    """

    async def async_handle(self, event: DomainEvent) -> None:
        """异步处理事件。

        Args:
            event: 要处理的事件
        """


# =============================================================================
# DeadLetterQueue - 死信队列接口
# =============================================================================


class DeadLetterQueue(Protocol):
    """死信队列抽象接口。"""

    def enqueue(self, event: DomainEvent, error: str, retry_count: int = 0) -> None:
        """入队失败事件。

        Args:
            event: 领域事件
            error: 错误信息
            retry_count: 重试次数
        """

    def dequeue(self) -> tuple[DomainEvent, str, int] | None:
        """出队失败事件。

        Returns:
            (event, error, retry_count) 或 None
        """

    def __len__(self) -> int:
        """队列长度。"""


class InMemoryDeadLetterQueue:
    """内存死信队列 — MVP 阶段使用。

    进程重启后丢失，仅用于测试和 MVP 占位。
    """

    def __init__(self) -> None:
        import logging

        self._items: list[tuple[DomainEvent, str, int]] = []
        self._logger = logging.getLogger(__name__)

    def enqueue(self, event: DomainEvent, error: str, retry_count: int = 0) -> None:
        """入队失败事件。"""
        self._items.append((event, error, retry_count))
        self._logger.warning(
            "Event %s enqueued to DLQ: %s (retry_count=%d)",
            event.event_id,
            error,
            retry_count,
        )

    def dequeue(self) -> tuple[DomainEvent, str, int] | None:
        """出队失败事件（FIFO）。"""
        return self._items.pop(0) if self._items else None

    def __len__(self) -> int:
        return len(self._items)
