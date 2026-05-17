"""基础设施层死信队列模块。

定义死信队列抽象基类和内存实现，用于存储处理失败的事件。
正式版将使用文件持久化或 RabbitMQ DLX

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
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
        """入队失败事件。

        Args:
            event: 失败的领域事件。
            error: 错误信息。
            retry_count: 已重试次数。
        """

    @abstractmethod
    def dequeue(self) -> tuple[DomainEvent, str, int] | None:
        """出队失败事件。

        Returns:
            (event, error, retry_count) 元组，队列为空时返回 None。
        """

    @abstractmethod
    def __len__(self) -> int:
        """返回队列长度。

        Returns:
            队列中的事件数量。
        """


class InMemoryDeadLetterQueue(DeadLetterQueue):
    """内存死信队列实现。

    进程重启后数据丢失，仅用于测试和 MVP 阶段。
    """

    def __init__(self) -> None:
        """初始化空死信队列。"""
        self._items: list[tuple[DomainEvent, str, int]] = []

    def enqueue(self, event: DomainEvent, error: str, retry_count: int = 0) -> None:
        """入队失败事件。

        Args:
            event: 失败的领域事件。
            error: 错误信息。
            retry_count: 已重试次数。
        """
        self._items.append((event, error, retry_count))
        logger.warning(
            "Event %s enqueued to DLQ: %s (retry_count=%d)",
            event.event_id,
            error,
            retry_count,
        )

    def dequeue(self) -> tuple[DomainEvent, str, int] | None:
        """出队失败事件（FIFO 顺序）。

        Returns:
            (event, error, retry_count) 元组，队列为空时返回 None。
        """
        return self._items.pop(0) if self._items else None

    def __len__(self) -> int:
        """返回队列长度。

        Returns:
            队列中的事件数量。
        """
        return len(self._items)
