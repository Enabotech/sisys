"""基础设施层内存事件监听器模块

从 domain 层迁移而来的 MVP 实现，仅用于测试和开发
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from src.domain.events.base import DomainEvent


class InMemoryEventListener:
    """内存事件监听器实现（MVP）

    维护事件类型到处理器函数的映射。事件分发时，调用该事件类型的所有处理器
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[DomainEvent], None]]] = defaultdict(list)

    def on_event(self, event_type: str, handler: Callable[[DomainEvent], None]) -> None:
        self._handlers[event_type].append(handler)

    def dispatch(self, event: DomainEvent) -> None:
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
        return list(self._handlers.keys())
