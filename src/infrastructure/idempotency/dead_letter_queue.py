"""DeadLetterQueue — 基础设施层实现。

MVP 阶段使用内存列表存储。
正式版（Story 1.5）将使用文件持久化或 RabbitMQ DLX。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from src.domain.events.base import DomainEvent

logger = logging.getLogger(__name__)


class DeadLetterQueue(ABC):
    """死信队列抽象基类。"""

    @abstractmethod
    def enqueue(self, event: DomainEvent, error: str, retry_count: int = 0) -> None:
        """入队失败事件。"""

    @abstractmethod
    def dequeue(self) -> tuple[DomainEvent, str, int] | None:
        """出队失败事件。

        Returns:
            (event, error, retry_count) 或 None
        """

    @abstractmethod
    def __len__(self) -> int:
        """队列长度。"""


class InMemoryDeadLetterQueue(DeadLetterQueue):
    """内存死信队列 — MVP 阶段使用。

    进程重启后丢失，仅用于测试和 MVP 占位。
    """

    def __init__(self):
        self._items: list[tuple[DomainEvent, str, int]] = []

    def enqueue(self, event: DomainEvent, error: str, retry_count: int = 0) -> None:
        """入队失败事件。"""
        self._items.append((event, error, retry_count))
        logger.warning(
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
