"""Event listener interface.

Defined in the domain layer, implemented in the infrastructure layer.
Supports registering handlers for specific event types.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable

from .base import DomainEvent


class EventListener(ABC):
    """Abstract event listener interface.

    Subscribers register handlers for specific event types
    and receive events when they are published.
    """

    @abstractmethod
    def on_event(self, event_type: str, handler: Callable[[DomainEvent], None]) -> None:
        """Register a handler for a specific event type.

        Args:
            event_type: The type of event to listen for.
            handler: Callback function that receives the domain event.

        Raises:
            NotImplementedError: Always, since this is an abstract interface.
        """

    @abstractmethod
    def dispatch(self, event: DomainEvent) -> None:
        """Dispatch an event to all registered handlers.

        Args:
            event: The domain event to dispatch.

        Raises:
            NotImplementedError: Always, since this is an abstract interface.
        """


class InMemoryEventListener(EventListener):
    """In-memory event listener implementation (MVP).

    Maintains a mapping of event types to handler functions.
    When an event is dispatched, all handlers for that event type are called.
    """

    def __init__(self) -> None:
        """Initialize the listener with an empty handler registry."""
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


class EventListenerAsync(ABC):
    """Abstract async event listener interface.

    用于异步事件消费场景（RabbitMQEventListener 实现）。
    与同步 EventListener 接口独立，不继承以避免强制实现同步方法。
    """

    @abstractmethod
    async def async_handle(self, event: DomainEvent) -> None:
        """异步处理事件。

        Args:
            event: 要处理的事件

        Raises:
            NotImplementedError: Always, since this is an abstract interface.
        """
