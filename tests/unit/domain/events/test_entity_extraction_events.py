"""实体抽取领域事件单元测试

验证 EntitiesExtracted 事件的构造、序列化、注册和继承链。
遵循六边形架构：领域层零外部依赖。
"""

from __future__ import annotations

import uuid

from src.domain.events.base import DomainEvent
from src.domain.events.entity_extraction_events import EntitiesExtracted


class TestEntitiesExtracted:
    """EntitiesExtracted 事件测试"""

    def test_inherits_domain_event(self) -> None:
        """验证继承 DomainEvent"""
        assert issubclass(EntitiesExtracted, DomainEvent)

    def test_event_type(self) -> None:
        """验证 event_type 默认值为 EntitiesExtracted"""
        event = EntitiesExtracted(
            memory_id=uuid.uuid4(),
            entity_count=5,
            relation_count=3,
            extraction_type="hybrid",
        )
        assert event.event_type == "EntitiesExtracted"

    def test_constructor_with_all_fields(self) -> None:
        """验证完整字段构造"""
        mem_id = uuid.uuid4()
        event = EntitiesExtracted(
            memory_id=mem_id,
            entity_count=5,
            relation_count=3,
            extraction_type="hybrid",
        )
        assert event.memory_id == mem_id
        assert event.entity_count == 5
        assert event.relation_count == 3
        assert event.extraction_type == "hybrid"

    def test_auto_registration(self) -> None:
        """验证事件自动注册到 _registry"""
        assert "EntitiesExtracted" in DomainEvent._registry
        assert DomainEvent._registry["EntitiesExtracted"] is EntitiesExtracted

    def test_post_init_sets_aggregate_id(self) -> None:
        """验证 __post_init__ 设置 aggregate_id = memory_id"""
        mem_id = uuid.uuid4()
        event = EntitiesExtracted(
            memory_id=mem_id,
            entity_count=10,
            relation_count=2,
            extraction_type="rule_only",
        )
        assert isinstance(event.aggregate_id, uuid.UUID)
        # aggregate_id 必须等于 memory_id（AC-2 规范：聚合溯源）
        assert event.aggregate_id == mem_id

    def test_post_init_sets_aggregate_type(self) -> None:
        """验证 __post_init__ 设置 aggregate_type"""
        event = EntitiesExtracted(
            memory_id=uuid.uuid4(),
            entity_count=10,
            relation_count=2,
            extraction_type="rule_only",
        )
        assert event.aggregate_type == "EntityExtraction"

    def test_frozen_dataclass(self) -> None:
        """验证 frozen=True 不可变"""
        event = EntitiesExtracted(
            memory_id=uuid.uuid4(),
            entity_count=5,
            relation_count=3,
            extraction_type="hybrid",
        )
        from dataclasses import FrozenInstanceError

        import pytest

        with pytest.raises(FrozenInstanceError):
            setattr(event, "memory_id", uuid.uuid4())

    def test_to_dict_serialization(self) -> None:
        """验证 to_dict() 序列化正确"""
        mem_id = uuid.uuid4()
        event = EntitiesExtracted(
            memory_id=mem_id,
            entity_count=5,
            relation_count=3,
            extraction_type="hybrid",
        )
        d = event.to_dict()
        assert d["event_type"] == "EntitiesExtracted"
        assert d["payload"]["memory_id"] == str(mem_id)
        assert d["payload"]["entity_count"] == 5
        assert d["payload"]["relation_count"] == 3
        assert d["payload"]["extraction_type"] == "hybrid"
        assert d["aggregate_id"] == str(event.aggregate_id)
        assert d["aggregate_type"] == "EntityExtraction"

    def test_from_dict_deserialization(self) -> None:
        """验证 from_dict() 反序列化正确（aggregate_id 为合法 UUID 字符串）"""
        original = EntitiesExtracted(
            memory_id=uuid.uuid4(),
            entity_count=5,
            relation_count=3,
            extraction_type="hybrid",
        )
        d = original.to_dict()
        # aggregate_id 是合法 UUID 字符串，from_dict 应能正确解析
        assert isinstance(d["aggregate_id"], str)
        restored = DomainEvent.from_dict(d)
        assert isinstance(restored, EntitiesExtracted)
        assert restored.memory_id == original.memory_id
        assert restored.entity_count == 5
        assert restored.relation_count == 3
        assert restored.extraction_type == "hybrid"
        assert restored.event_type == "EntitiesExtracted"
        assert isinstance(restored.aggregate_id, uuid.UUID)
        assert str(restored.aggregate_id) == d["aggregate_id"]

    def test_from_dict_without_optional_fields(self) -> None:
        """验证反序列化时可选字段正常"""
        mem_id = uuid.uuid4()
        d = {
            "event_id": str(uuid.uuid4()),
            "event_type": "EntitiesExtracted",
            "timestamp": "2026-08-09T12:00:00+00:00",
            "payload": {
                "memory_id": str(mem_id),
                "entity_count": 0,
                "relation_count": 0,
                "extraction_type": "rule_only",
            },
        }
        restored = DomainEvent.from_dict(d)
        assert isinstance(restored, EntitiesExtracted)
        assert restored.memory_id == mem_id
        assert restored.entity_count == 0
        assert restored.relation_count == 0
        assert restored.extraction_type == "rule_only"
