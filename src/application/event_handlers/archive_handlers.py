"""应用层档案事件处理器模块

处理 ValidityPeriodSet / FactBecameStale 领域事件。
遵循 InMemoryEventListener.on_event() + register_handlers() 模式。
"""

from __future__ import annotations

import logging
from typing import Callable

from src.domain.events.archive_events import FactBecameStale, ValidityPeriodSet
from src.domain.events.base import DomainEvent
from src.domain.ports.event_listener import EventListener

logger = logging.getLogger(__name__)


class ArchiveValidityHandler:
    """档案有效期事件处理器

    处理 ValidityPeriodSet 和 FactBecameStale 事件。
    当前实现记录日志，预留 L3/L5 同步钩子（TODO: Story 3.12）。
    """

    def __init__(
        self,
        event_listener: EventListener,
    ) -> None:
        """初始化档案有效期事件处理器

        Args:
            event_listener: 事件监听器端口
        """
        self._event_listener = event_listener

    def register_handlers(self) -> None:
        """注册事件处理器到事件监听器

        注册 ValidityPeriodSet 和 FactBecameStale 事件的处理回调。
        """
        self._event_listener.on_event("ValidityPeriodSet", self._wrap_handler("validity_set"))
        self._event_listener.on_event("FactBecameStale", self._wrap_handler("fact_stale"))

    def _wrap_handler(self, handler_type: str) -> Callable[[DomainEvent], None]:
        """包装异步 handler 为同步回调

        Args:
            handler_type: 处理器类型标识

        Returns:
            同步回调闭包
        """

        def _handle(event: DomainEvent) -> None:
            try:
                if isinstance(event, ValidityPeriodSet):
                    self._handle_validity_period_set(event)
                elif isinstance(event, FactBecameStale):
                    self._handle_fact_became_stale(event)
                else:
                    logger.warning("Unknown event type received: %s", type(event).__name__)
            except Exception:
                logger.exception("Error handling event %s", event.event_type)

        return _handle

    def _handle_validity_period_set(self, event: ValidityPeriodSet) -> None:
        """处理 ValidityPeriodSet 事件

        记录有效期变更日志。
        预留 L3/L5 同步钩子（TODO: Story 3.12 - sync valid_from/valid_until to L3/L5 payload）。

        Args:
            event: ValidityPeriodSet 事件
        """
        logger.info(
            "Validity period set for archive %s: [%s, %s]",
            event.archive_id,
            event.valid_from.isoformat() if event.valid_from else "None",
            event.valid_until.isoformat() if event.valid_until else "None",
        )
        # TODO: Story 3.12 - sync valid_from/valid_until to L3/L5 payload

    def _handle_fact_became_stale(self, event: FactBecameStale) -> None:
        """处理 FactBecameStale 事件

        记录陈旧标记日志。
        后续可扩展为触发降权处理、通知前端等。

        Args:
            event: FactBecameStale 事件
        """
        logger.info(
            "Fact became stale for archive %s: reason=%s, stale_since=%s",
            event.archive_id,
            event.stale_reason,
            event.stale_since.isoformat(),
        )
        # TODO: Story 3.12 - 触发降权处理、通知前端等


__all__ = [
    "ArchiveValidityHandler",
]
