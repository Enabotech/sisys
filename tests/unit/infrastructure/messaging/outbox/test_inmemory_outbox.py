"""InMemoryOutboxRepository 单元测试

验证 InMemoryOutboxRepository 实现正确
Story 1.3: Event Bus Implementation

Reference: src/infrastructure/messaging/outbox/inmemory_outbox.py
"""

from __future__ import annotations

from dataclasses import field
from uuid import uuid4

import pytest

from src.domain.events.base import DomainEvent
from src.infrastructure.messaging.outbox.inmemory_outbox import InMemoryOutboxRepository


class _TestEventForOutbox(DomainEvent):
    """Test event for outbox testing."""

    event_type: str = field(default="TestEventForOutbox", init=False)


class TestInMemoryOutboxRepository:
    """验证 InMemoryOutboxRepository 实现"""

    @pytest.fixture
    def repository(self) -> InMemoryOutboxRepository:
        """创建 InMemoryOutboxRepository 实例"""
        return InMemoryOutboxRepository()

    async def test_save_adds_event_to_entities(self, repository: InMemoryOutboxRepository) -> None:
        """验证 save() 添加事件到实体列表"""
        DomainEvent.register("TestEventForOutbox", _TestEventForOutbox)
        event = DomainEvent(event_type="TestEventForOutbox", source="test")
        await repository.save(event)

        unpublished = await repository.get_unpublished(limit=10)
        assert len(unpublished) == 1
        assert unpublished[0].event_type == "TestEventForOutbox"

    async def test_get_unpublished_returns_pending_events(self, repository: InMemoryOutboxRepository) -> None:
        """验证 get_unpublished() 返回待处理事件"""
        DomainEvent.register("TestEventForOutbox", _TestEventForOutbox)
        event1 = DomainEvent(event_type="TestEventForOutbox", source="test")
        event2 = DomainEvent(event_type="TestEventForOutbox", source="test")
        await repository.save(event1)
        await repository.save(event2)

        unpublished = await repository.get_unpublished(limit=10)
        assert len(unpublished) == 2

    async def test_get_unpublished_respects_limit(self, repository: InMemoryOutboxRepository) -> None:
        """验证 get_unpublished() 遵守限制"""
        DomainEvent.register("TestEventForOutbox", _TestEventForOutbox)
        for i in range(5):
            event = DomainEvent(event_type="TestEventForOutbox", source="test")
            await repository.save(event)

        unpublished = await repository.get_unpublished(limit=2)
        assert len(unpublished) == 2

    async def test_get_unpublished_returns_empty_when_none(self, repository: InMemoryOutboxRepository) -> None:
        """验证没有待处理事件时返回空列表"""
        unpublished = await repository.get_unpublished(limit=10)
        assert unpublished == []

    async def test_mark_published_updates_status(self, repository: InMemoryOutboxRepository) -> None:
        """验证 mark_published() 更新状态"""
        DomainEvent.register("TestEventForOutbox", _TestEventForOutbox)
        event = DomainEvent(event_type="TestEventForOutbox", source="test")
        await repository.save(event)
        unpublished = await repository.get_unpublished(limit=10)
        event_id = unpublished[0].event_id

        await repository.mark_published(event_id)

        unpublished_after = await repository.get_unpublished(limit=10)
        assert len(unpublished_after) == 0

    async def test_mark_published_handles_unknown_id(self, repository: InMemoryOutboxRepository) -> None:
        """验证 mark_published() 处理未知 ID"""
        await repository.mark_published(uuid4())  # Should not raise

    async def test_mark_failed_updates_status(self, repository: InMemoryOutboxRepository) -> None:
        """验证 mark_failed() 更新状态"""
        DomainEvent.register("TestEventForOutbox", _TestEventForOutbox)
        event = DomainEvent(event_type="TestEventForOutbox", source="test")
        await repository.save(event)
        unpublished = await repository.get_unpublished(limit=10)
        event_id = unpublished[0].event_id

        await repository.mark_failed(event_id, "Test error")

        unpublished_after = await repository.get_unpublished(limit=10)
        assert len(unpublished_after) == 0

    async def test_mark_failed_handles_unknown_id(self, repository: InMemoryOutboxRepository) -> None:
        """验证 mark_failed() 处理未知 ID"""
        await repository.mark_failed(uuid4(), "Test error")  # Should not raise


class TestInMemoryOutboxRepositoryInternalMethods:
    """验证 InMemoryOutboxRepository 内部方法（异步）"""

    @pytest.fixture
    def repository(self) -> InMemoryOutboxRepository:
        """创建 InMemoryOutboxRepository 实例"""
        return InMemoryOutboxRepository()

    async def test_get_unpublished_entities(self, repository: InMemoryOutboxRepository) -> None:
        """验证 _get_unpublished_entities() 内部方法"""
        event = DomainEvent(event_type="TestEventForOutbox", source="test")
        await repository.save(event)

        entities = await repository._get_unpublished_entities(limit=10)
        assert len(entities) == 1
        assert entities[0].event_type == "TestEventForOutbox"

    async def test_mark_published_entity(self, repository: InMemoryOutboxRepository) -> None:
        """验证 _mark_published_entity() 内部方法"""
        event = DomainEvent(event_type="TestEventForOutbox", source="test")
        await repository.save(event)
        entities = await repository._get_unpublished_entities(limit=10)
        entity = entities[0]

        await repository._mark_published_entity(entity)

        entities_after = await repository._get_unpublished_entities(limit=10)
        assert len(entities_after) == 0

    async def test_mark_failed_entity(self, repository: InMemoryOutboxRepository) -> None:
        """验证 _mark_failed_entity() 内部方法"""
        event = DomainEvent(event_type="TestEventForOutbox", source="test")
        await repository.save(event)
        entities = await repository._get_unpublished_entities(limit=10)
        entity = entities[0]

        await repository._mark_failed_entity(entity, "Test error")

        entities_after = await repository._get_unpublished_entities(limit=10)
        assert len(entities_after) == 0

    async def test_entities_initially_empty(self, repository: InMemoryOutboxRepository) -> None:
        """验证实体列表初始为空"""
        unpublished = await repository.get_unpublished(limit=10)
        assert unpublished == []


class TestInMemoryOutboxRepositoryFIFO:
    """验证 FIFO 排序"""

    @pytest.fixture
    def repository(self) -> InMemoryOutboxRepository:
        """创建 InMemoryOutboxRepository 实例"""
        return InMemoryOutboxRepository()

    async def test_fifo_ordering(self, repository: InMemoryOutboxRepository) -> None:
        """验证 FIFO 顺序：先创建的事件先返回"""
        import time

        DomainEvent.register("TestEventForOutbox", _TestEventForOutbox)

        # 创建 3 个事件，每个间隔一小段时间确保 timestamp 不同
        ids = []
        for i in range(3):
            event = DomainEvent(event_type="TestEventForOutbox", source="test")
            await repository.save(event)
            ids.append(event.event_id)
            if i < 2:
                time.sleep(0.01)  # 确保 timestamp 不同

        unpublished = await repository.get_unpublished(limit=10)
        assert len(unpublished) == 3
        # FIFO: 验证事件按创建顺序返回（通过 event_id 验证）
        assert unpublished[0].event_id == ids[0]
        assert unpublished[1].event_id == ids[1]
        assert unpublished[2].event_id == ids[2]

    async def test_fifo_after_mark_published(self, repository: InMemoryOutboxRepository) -> None:
        """验证 mark_published 后的 FIFO 顺序"""
        DomainEvent.register("TestEventForOutbox", _TestEventForOutbox)
        for i in range(3):
            event = DomainEvent(event_type="TestEventForOutbox", source="test")
            await repository.save(event)

        # Mark first event as published
        unpublished = await repository.get_unpublished(limit=10)
        await repository.mark_published(unpublished[0].event_id)

        # Add new event
        new_event = DomainEvent(event_type="TestEventForOutbox", source="test")
        await repository.save(new_event)

        unpublished = await repository.get_unpublished(limit=10)
        assert len(unpublished) == 3


class TestInMemoryOutboxRepositoryMarkPending:
    """验证 mark_pending()（失败事件恢复为待发布）"""

    @pytest.fixture
    def repository(self) -> InMemoryOutboxRepository:
        """创建 InMemoryOutboxRepository 实例"""
        return InMemoryOutboxRepository()

    @pytest.fixture
    def saved_event_id(self, repository: InMemoryOutboxRepository) -> str:
        """保存一个事件并返回其 event_id（str 形态）"""

        async def _save() -> str:
            DomainEvent.register("TestEventForOutbox", _TestEventForOutbox)
            event = DomainEvent(event_type="TestEventForOutbox", source="test")
            await repository.save(event)
            unpublished = await repository.get_unpublished(limit=10)
            return str(unpublished[0].event_id)

        import asyncio

        return asyncio.get_event_loop().run_until_complete(_save())

    async def test_mark_pending_restores_failed_event(self, repository: InMemoryOutboxRepository, saved_event_id: str) -> None:
        """失败事件调用 mark_pending() 后应恢复为待发布状态"""
        import uuid

        await repository.mark_failed(uuid.UUID(saved_event_id), "error message")

        unpublished_after_failed = await repository.get_unpublished(limit=10)
        assert len(unpublished_after_failed) == 0

        await repository.mark_pending(uuid.UUID(saved_event_id))

        unpublished_after_pending = await repository.get_unpublished(limit=10)
        assert len(unpublished_after_pending) == 1
        assert unpublished_after_pending[0].event_id == uuid.UUID(saved_event_id)

    async def test_mark_pending_handles_unknown_id(self, repository: InMemoryOutboxRepository) -> None:
        """mark_pending() 处理未知 ID 不应抛出异常"""
        await repository.mark_pending(uuid4())  # Should not raise

    async def test_mark_pending_on_unfailed_event_is_noop(
        self, repository: InMemoryOutboxRepository, saved_event_id: str
    ) -> None:
        """对未失败事件调用 mark_pending() 因状态机限制不会使其变为 pending"""
        import uuid

        # 状态为 pending 的事件调用 mark_pending() 会触发状态机异常，此处验证不将异常吞掉
        with pytest.raises(Exception):
            await repository.mark_pending(uuid.UUID(saved_event_id))


class TestInMemoryOutboxRepositoryCleanup:
    """验证 cleanup_old_published_records()（清理过期已发布记录）"""

    @pytest.fixture
    def repository(self) -> InMemoryOutboxRepository:
        """创建 InMemoryOutboxRepository 实例"""
        return InMemoryOutboxRepository()

    async def test_cleanup_removes_old_published_records(self, repository: InMemoryOutboxRepository) -> None:
        """超过保留期的已发布记录应被清理"""
        DomainEvent.register("TestEventForOutbox", _TestEventForOutbox)
        event = DomainEvent(event_type="TestEventForOutbox", source="test")
        await repository.save(event)
        unpublished = await repository.get_unpublished(limit=10)
        event_id = unpublished[0].event_id

        await repository.mark_published(event_id)

        # 将 published_at 回拨到保留期之前
        from datetime import UTC, datetime, timedelta

        entity = repository._entities[0]
        entity.published_at = datetime.now(UTC) - timedelta(days=31)
        # 确保状态为 published
        assert entity.status == "published"

        removed = await repository.cleanup_old_published_records(older_than_days=30)

        assert removed == 1
        assert repository._entities == []

    async def test_cleanup_keeps_recent_published_records(self, repository: InMemoryOutboxRepository) -> None:
        """保留期内的已发布记录不应被清理"""
        DomainEvent.register("TestEventForOutbox", _TestEventForOutbox)
        event = DomainEvent(event_type="TestEventForOutbox", source="test")
        await repository.save(event)
        unpublished = await repository.get_unpublished(limit=10)
        event_id = unpublished[0].event_id
        await repository.mark_published(event_id)

        removed = await repository.cleanup_old_published_records(older_than_days=30)

        assert removed == 0
        assert len(repository._entities) == 1

    async def test_cleanup_ignores_pending_records(self, repository: InMemoryOutboxRepository) -> None:
        """未发布（pending）记录即使创建时间较早也不应被清理"""
        DomainEvent.register("TestEventForOutbox", _TestEventForOutbox)
        event = DomainEvent(event_type="TestEventForOutbox", source="test")
        await repository.save(event)

        from datetime import UTC, datetime, timedelta

        entity = repository._entities[0]
        entity.created_at = datetime.now(UTC) - timedelta(days=60)
        assert entity.status == "pending"

        removed = await repository.cleanup_old_published_records(older_than_days=30)

        assert removed == 0
        assert len(repository._entities) == 1
