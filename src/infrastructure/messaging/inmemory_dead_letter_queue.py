"""基础设施层内存死信队列模块

从 domain 层迁移而来的 MVP 实现，仅用于测试和开发
"""

from __future__ import annotations

import asyncio
import logging

from src.domain.events.base import DomainEvent


class InMemoryDeadLetterQueue:
    """内存死信队列 — MVP 阶段使用

    进程重启后丢失，仅用于测试和 MVP 占位
    实现 DeadLetterQueue Protocol（async 签名）
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[tuple[DomainEvent, str, int]] = asyncio.Queue()
        self._logger = logging.getLogger(__name__)

    async def enqueue(self, event: DomainEvent, error: str, retry_count: int = 0) -> None:
        await self._queue.put((event, error, retry_count))
        self._logger.warning(
            "Event %s enqueued to DLQ: %s (retry_count=%d)",
            event.event_id,
            error,
            retry_count,
        )

    async def dequeue(self) -> tuple[DomainEvent, str, int] | None:
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    def __len__(self) -> int:
        return self._queue.qsize()
