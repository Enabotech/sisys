"""Dead Letter Queue Re-Export 测试

验证 src/infrastructure/messaging/outbox/dead_letter_queue.py 的 re-export 路径
测试 InMemoryDeadLetterQueue 的基本行为

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.
"""

from __future__ import annotations

import pytest

from src.domain.events.base import DomainEvent
from src.infrastructure.messaging.outbox.dead_letter_queue import (
    DeadLetterQueue,
    InMemoryDeadLetterQueue,
)


class TestDeadLetterQueueReExport:
    """DeadLetterQueue re-export 路径测试"""

    def test_dead_letter_queue_can_be_imported_from_re_export_path(self) -> None:
        """应能从 re-export 路径导入 DeadLetterQueue"""
        assert DeadLetterQueue is not None

    def test_inmemory_dead_letter_queue_can_be_imported_from_re_export_path(self) -> None:
        """应能从 re-export 路径导入 InMemoryDeadLetterQueue"""
        assert InMemoryDeadLetterQueue is not None

    def test_inmemory_dead_letter_queue_is_same_as_domain_import(self) -> None:
        """re-export 的 InMemoryDeadLetterQueue 应与直接导入一致"""
        from src.infrastructure.messaging.inmemory_dead_letter_queue import (
            InMemoryDeadLetterQueue as DirectImport,
        )

        assert InMemoryDeadLetterQueue is DirectImport


class TestInMemoryDeadLetterQueueBehavior:
    """InMemoryDeadLetterQueue 行为测试"""

    @pytest.fixture
    def dlq(self) -> InMemoryDeadLetterQueue:
        """创建干净的 DLQ 实例"""
        return InMemoryDeadLetterQueue()

    @pytest.fixture
    def sample_event(self) -> DomainEvent:
        """创建示例 DomainEvent"""
        from uuid import uuid4

        from src.domain.events.base import DomainEvent

        class TestEvent(DomainEvent):
            event_type = "TestEvent"

        return TestEvent(event_id=uuid4(), source="test")

    @pytest.mark.asyncio
    async def test_enqueue_adds_event_to_queue(self, dlq: InMemoryDeadLetterQueue, sample_event: DomainEvent) -> None:
        """enqueue 应将事件添加到队列"""
        assert len(dlq) == 0
        await dlq.enqueue(sample_event, "test error", retry_count=1)
        assert len(dlq) == 1

    @pytest.mark.asyncio
    async def test_dequeue_returns_enqueued_event(self, dlq: InMemoryDeadLetterQueue, sample_event: DomainEvent) -> None:
        """dequeue 应返回之前 enqueue 的事件"""
        await dlq.enqueue(sample_event, "test error", retry_count=1)
        result = await dlq.dequeue()
        assert result is not None
        event, error, retry_count = result
        assert event.event_id == sample_event.event_id
        assert error == "test error"
        assert retry_count == 1

    @pytest.mark.asyncio
    async def test_dequeue_on_empty_returns_none(self, dlq: InMemoryDeadLetterQueue) -> None:
        """dequeue 在队列为空时应返回 None"""
        result = await dlq.dequeue()
        assert result is None

    @pytest.mark.asyncio
    async def test_len_returns_queue_size(self, dlq: InMemoryDeadLetterQueue, sample_event: DomainEvent) -> None:
        """len() 应返回队列当前大小"""
        assert len(dlq) == 0
        await dlq.enqueue(sample_event, "error 1")
        assert len(dlq) == 1
        await dlq.enqueue(sample_event, "error 2")
        assert len(dlq) == 2
        await dlq.dequeue()
        assert len(dlq) == 1

    @pytest.mark.asyncio
    async def test_dequeue_returns_fifo_order(self, dlq: InMemoryDeadLetterQueue) -> None:
        """dequeue 应按 FIFO 顺序返回事件"""
        from uuid import uuid4

        from src.domain.events.base import DomainEvent

        class TestEvent(DomainEvent):
            event_type = "TestEvent"

        events = [TestEvent(event_id=uuid4(), source="test") for _ in range(3)]
        for i, event in enumerate(events):
            await dlq.enqueue(event, f"error {i}")

        first_dequeue = await dlq.dequeue()
        second_dequeue = await dlq.dequeue()
        third_dequeue = await dlq.dequeue()

        assert first_dequeue is not None
        assert second_dequeue is not None
        assert third_dequeue is not None
        assert first_dequeue[0].event_id == events[0].event_id
        assert second_dequeue[0].event_id == events[1].event_id
        assert third_dequeue[0].event_id == events[2].event_id

    @pytest.mark.asyncio
    async def test_multiple_enqueue_dequeue_cycles(self, dlq: InMemoryDeadLetterQueue, sample_event: DomainEvent) -> None:
        """测试多次 enqueue/dequeue 循环"""
        for i in range(5):
            await dlq.enqueue(sample_event, f"error {i}")
            assert len(dlq) == i + 1

        for i in range(5):
            result = await dlq.dequeue()
            assert result is not None
            assert result[1] == f"error {i}"
