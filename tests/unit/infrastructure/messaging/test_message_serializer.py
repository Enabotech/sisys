"""InMemoryEventStore 单元测试

验证 InMemoryEventStore 正确实现事件存储接口
"""

from __future__ import annotations

import uuid

import pytest

from src.domain.events import DocumentProcessed
from src.infrastructure.messaging.message_serializer import InMemoryEventStore


class TestInMemoryEventStore:
    """测试 InMemoryEventStore 实现。"""

    @pytest.fixture
    def store(self) -> InMemoryEventStore:
        """创建空的事件存储。"""
        return InMemoryEventStore()

    def test_empty_store_returns_no_events(self, store: InMemoryEventStore) -> None:
        """空存储应返回空列表。"""
        agg_id = uuid.uuid4()
        events = store.get_events(agg_id)
        assert events == []

    def test_save_single_event(self, store: InMemoryEventStore) -> None:
        """保存单个事件。"""
        agg_id = uuid.uuid4()
        event = DocumentProcessed(document_id=agg_id)
        store.save_events([event])

        retrieved = store.get_events(agg_id)
        assert len(retrieved) == 1
        assert retrieved[0].event_type == "DocumentProcessed"

    def test_save_multiple_events_same_aggregate(self, store: InMemoryEventStore) -> None:
        """保存多个同一聚合的事件。"""
        agg_id = uuid.uuid4()
        events = [DocumentProcessed(document_id=agg_id) for _ in range(3)]
        store.save_events(events)

        retrieved = store.get_events(agg_id)
        assert len(retrieved) == 3

    def test_save_events_different_aggregates(self, store: InMemoryEventStore) -> None:
        """保存不同聚合的事件应隔离。"""
        agg1 = uuid.uuid4()
        agg2 = uuid.uuid4()

        events1 = [DocumentProcessed(document_id=agg1)]
        events2 = [DocumentProcessed(document_id=agg2)]

        store.save_events(events1)
        store.save_events(events2)

        assert len(store.get_events(agg1)) == 1
        assert len(store.get_events(agg2)) == 1

    def test_get_events_by_version_valid_range(self, store: InMemoryEventStore) -> None:
        """按版本范围查询事件。"""
        agg_id = uuid.uuid4()
        events = [DocumentProcessed(document_id=agg_id) for _ in range(5)]
        store.save_events(events)

        result = store.get_events_by_version(agg_id, from_version=2, to_version=4)
        assert len(result) == 3

    def test_get_events_by_version_single_event(self, store: InMemoryEventStore) -> None:
        """查询单个版本。"""
        agg_id = uuid.uuid4()
        event = DocumentProcessed(document_id=agg_id)
        store.save_events([event])

        result = store.get_events_by_version(agg_id, from_version=1, to_version=1)
        assert len(result) == 1

    def test_get_events_by_version_out_of_range(self, store: InMemoryEventStore) -> None:
        """查询超出范围应返回空列表。"""
        agg_id = uuid.uuid4()
        event = DocumentProcessed(document_id=agg_id)
        store.save_events([event])

        result = store.get_events_by_version(agg_id, from_version=5, to_version=10)
        assert len(result) == 0

    def test_get_events_by_version_invalid_range_raises(self, store: InMemoryEventStore) -> None:
        """from_version > to_version 应抛出 ValueError。"""
        agg_id = uuid.uuid4()
        with pytest.raises(ValueError, match="from_version .* must be <= to_version"):
            store.get_events_by_version(agg_id, from_version=5, to_version=2)

    def test_get_events_by_version_negative_version_raises(self, store: InMemoryEventStore) -> None:
        """负版本号应抛出 ValueError。"""
        agg_id = uuid.uuid4()
        with pytest.raises(ValueError, match="Version numbers must be >= 1"):
            store.get_events_by_version(agg_id, from_version=-1, to_version=5)

    def test_clear_removes_all_events(self, store: InMemoryEventStore) -> None:
        """clear() 应删除所有事件。"""
        agg_id = uuid.uuid4()
        store.save_events([DocumentProcessed(document_id=agg_id)])

        store.clear()
        assert len(store.get_events(agg_id)) == 0

    def test_events_maintain_order(self, store: InMemoryEventStore) -> None:
        """事件应保持插入顺序。"""
        agg_id = uuid.uuid4()
        events = [DocumentProcessed(document_id=agg_id) for _ in range(4)]
        store.save_events(events)

        retrieved = store.get_events(agg_id)
        assert retrieved[0].event_id == events[0].event_id
        assert retrieved[3].event_id == events[3].event_id

    def test_get_events_for_unknown_aggregate(self, store: InMemoryEventStore) -> None:
        """未知聚合 ID 应返回空列表。"""
        result = store.get_events(uuid.uuid4())
        assert result == []

    def test_get_events_returns_in_order(self, store: InMemoryEventStore) -> None:
        """返回的事件应按保存顺序排列。"""
        agg_id = uuid.uuid4()
        events = [DocumentProcessed(document_id=agg_id) for _ in range(5)]
        store.save_events(events)

        retrieved = store.get_events(agg_id)
        assert len(retrieved) == 5
        for i, event in enumerate(retrieved):
            assert event.event_id == events[i].event_id
