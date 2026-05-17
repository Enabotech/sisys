"""InMemoryOutboxRepository 单元测试

验证 InMemoryOutboxRepository 实现正确
Story 1.3: Event Bus Implementation

Reference: src/infrastructure/messaging/outbox/inmemory_outbox.py
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.domain.events.base import DomainEvent
from src.infrastructure.messaging.adapters.event_outbox_adapter import EventRegistry
from src.infrastructure.messaging.outbox.inmemory_outbox import InMemoryOutboxRepository


class _TestEventForOutbox(DomainEvent):
    """Test event for outbox testing."""

    event_type: str = "TestEvent"


class TestInMemoryOutboxRepository:
    """验证 InMemoryOutboxRepository 实现"""

    @pytest.fixture
    def repository(self) -> InMemoryOutboxRepository:
        """创建 InMemoryOutboxRepository 实例"""
        return InMemoryOutboxRepository()

    def test_save_adds_event_to_entities(self, repository: InMemoryOutboxRepository) -> None:
        """验证 save() 添加事件到实体列表"""
        EventRegistry.register("TestEvent", _TestEventForOutbox)
        event = DomainEvent(event_type="TestEvent", source="test")
        repository.save(event)

        unpublished = repository.get_unpublished(limit=10)
        assert len(unpublished) == 1
        assert unpublished[0].event_type == "TestEvent"

    def test_get_unpublished_returns_pending_events(self, repository: InMemoryOutboxRepository) -> None:
        """验证 get_unpublished() 返回待处理事件"""
        EventRegistry.register("TestEvent", _TestEventForOutbox)
        event1 = DomainEvent(event_type="TestEvent", source="test")
        event2 = DomainEvent(event_type="TestEvent", source="test")
        repository.save(event1)
        repository.save(event2)

        unpublished = repository.get_unpublished(limit=10)
        assert len(unpublished) == 2

    def test_get_unpublished_respects_limit(self, repository: InMemoryOutboxRepository) -> None:
        """验证 get_unpublished() 遵守限制"""
        EventRegistry.register("TestEvent", _TestEventForOutbox)
        for i in range(5):
            event = DomainEvent(event_type="TestEvent", source="test")
            repository.save(event)

        unpublished = repository.get_unpublished(limit=2)
        assert len(unpublished) == 2

    def test_get_unpublished_returns_empty_when_none(self, repository: InMemoryOutboxRepository) -> None:
        """验证没有待处理事件时返回空列表"""
        unpublished = repository.get_unpublished(limit=10)
        assert unpublished == []

    def test_mark_published_updates_status(self, repository: InMemoryOutboxRepository) -> None:
        """验证 mark_published() 更新状态"""
        EventRegistry.register("TestEvent", _TestEventForOutbox)
        event = DomainEvent(event_type="TestEvent", source="test")
        repository.save(event)
        unpublished = repository.get_unpublished(limit=10)
        event_id = unpublished[0].event_id

        repository.mark_published(event_id)

        unpublished_after = repository.get_unpublished(limit=10)
        assert len(unpublished_after) == 0

    def test_mark_published_handles_unknown_id(self, repository: InMemoryOutboxRepository) -> None:
        """验证 mark_published() 处理未知 ID"""
        repository.mark_published(uuid4())  # Should not raise

    def test_mark_failed_updates_status(self, repository: InMemoryOutboxRepository) -> None:
        """验证 mark_failed() 更新状态"""
        EventRegistry.register("TestEvent", _TestEventForOutbox)
        event = DomainEvent(event_type="TestEvent", source="test")
        repository.save(event)
        unpublished = repository.get_unpublished(limit=10)
        event_id = unpublished[0].event_id

        repository.mark_failed(event_id, "Test error")

        unpublished_after = repository.get_unpublished(limit=10)
        assert len(unpublished_after) == 0

    def test_mark_failed_handles_unknown_id(self, repository: InMemoryOutboxRepository) -> None:
        """验证 mark_failed() 处理未知 ID"""
        repository.mark_failed(uuid4(), "Test error")  # Should not raise


class TestInMemoryOutboxRepositoryInternalMethods:
    """验证 InMemoryOutboxRepository 内部方法（异步）"""

    @pytest.fixture
    def repository(self) -> InMemoryOutboxRepository:
        """创建 InMemoryOutboxRepository 实例"""
        return InMemoryOutboxRepository()

    @pytest.mark.asyncio
    async def test_get_unpublished_entities(self, repository: InMemoryOutboxRepository) -> None:
        """验证 _get_unpublished_entities() 内部方法"""
        event = DomainEvent(event_type="TestEvent", source="test")
        repository.save(event)

        entities = await repository._get_unpublished_entities(limit=10)
        assert len(entities) == 1
        assert entities[0].event_type == "TestEvent"

    @pytest.mark.asyncio
    async def test_mark_published_entity(self, repository: InMemoryOutboxRepository) -> None:
        """验证 _mark_published_entity() 内部方法"""
        event = DomainEvent(event_type="TestEvent", source="test")
        repository.save(event)
        entities = await repository._get_unpublished_entities(limit=10)
        entity = entities[0]

        await repository._mark_published_entity(entity)

        entities_after = await repository._get_unpublished_entities(limit=10)
        assert len(entities_after) == 0

    @pytest.mark.asyncio
    async def test_mark_failed_entity(self, repository: InMemoryOutboxRepository) -> None:
        """验证 _mark_failed_entity() 内部方法"""
        event = DomainEvent(event_type="TestEvent", source="test")
        repository.save(event)
        entities = await repository._get_unpublished_entities(limit=10)
        entity = entities[0]

        await repository._mark_failed_entity(entity, "Test error")

        entities_after = await repository._get_unpublished_entities(limit=10)
        assert len(entities_after) == 0

    def test_entities_initially_empty(self, repository: InMemoryOutboxRepository) -> None:
        """验证实体列表初始为空"""
        unpublished = repository.get_unpublished(limit=10)
        assert unpublished == []


class TestInMemoryOutboxRepositoryFIFO:
    """验证 FIFO 排序"""

    @pytest.fixture
    def repository(self) -> InMemoryOutboxRepository:
        """创建 InMemoryOutboxRepository 实例"""
        return InMemoryOutboxRepository()

    def test_fifo_ordering(self, repository: InMemoryOutboxRepository) -> None:
        """验证 FIFO 顺序：先创建的事件先返回"""
        import time

        EventRegistry.register("TestEvent", _TestEventForOutbox)

        # 创建 3 个事件，每个间隔一小段时间确保 timestamp 不同
        ids = []
        for i in range(3):
            event = DomainEvent(event_type="TestEvent", source="test")
            repository.save(event)
            ids.append(event.event_id)
            if i < 2:
                time.sleep(0.01)  # 确保 timestamp 不同

        unpublished = repository.get_unpublished(limit=10)
        assert len(unpublished) == 3
        # FIFO: 验证事件按创建顺序返回（通过 event_id 验证）
        assert unpublished[0].event_id == ids[0]
        assert unpublished[1].event_id == ids[1]
        assert unpublished[2].event_id == ids[2]

    def test_fifo_after_mark_published(self, repository: InMemoryOutboxRepository) -> None:
        """验证 mark_published 后的 FIFO 顺序"""
        EventRegistry.register("TestEvent", _TestEventForOutbox)
        for i in range(3):
            event = DomainEvent(event_type="TestEvent", source="test")
            repository.save(event)

        # Mark first event as published
        unpublished = repository.get_unpublished(limit=10)
        repository.mark_published(unpublished[0].event_id)

        # Add new event
        new_event = DomainEvent(event_type="TestEvent", source="test")
        repository.save(new_event)

        unpublished = repository.get_unpublished(limit=10)
        assert len(unpublished) == 3
