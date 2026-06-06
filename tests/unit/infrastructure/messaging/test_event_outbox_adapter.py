"""Task 3 TDD Tests — EventOutboxAdapter conversion tests."""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.domain.events import (
    AgentDecided,
    DocumentProcessed,
    ToolExecuted,
)
from src.domain.events.base import DomainEvent
from src.domain.exceptions import ConfigurationError
from src.infrastructure.messaging.adapters.event_outbox_adapter import EventOutboxAdapter
from src.infrastructure.messaging.outbox.outbox import OutboxEntity


class TestEventOutboxAdapterConversion:
    """EventOutboxAdapter roundtrip conversion tests."""

    def test_document_processed_roundtrip(self):
        """DocumentProcessed → OutboxEntity → DomainEvent (fields preserved in payload)."""
        event = DocumentProcessed(
            document_id=uuid4(),
            parse_result={"pages": 10, "tables": 2},
            embedding=[0.1] * 1024,
        )
        entity = EventOutboxAdapter.from_domain_event(event)
        restored = EventOutboxAdapter.to_domain_event(entity)

        assert restored.event_id == event.event_id
        assert restored.event_type == event.event_type
        # Fields preserved in payload (UUIDs are serialized as strings)
        assert str(restored.payload.get("document_id")) == str(event.document_id)
        assert restored.payload.get("parse_result") == event.parse_result

    def test_tool_executed_roundtrip(self):
        """ToolExecuted → OutboxEntity → DomainEvent."""
        from uuid import uuid4

        tool_id = uuid4()
        event = ToolExecuted(
            tool_id=tool_id,
            execution_result={"status": "success"},
            cost_audit={"tokens": 1000, "cost": 0.01},
        )
        entity = EventOutboxAdapter.from_domain_event(event)
        restored = EventOutboxAdapter.to_domain_event(entity)

        assert restored.event_type == event.event_type
        assert str(restored.payload.get("tool_id")) == str(event.tool_id)

    def test_agent_decided_roundtrip(self):
        """AgentDecided → OutboxEntity → DomainEvent."""
        from uuid import uuid4

        agent_id = uuid4()
        event = AgentDecided(
            agent_id=agent_id,
            decision_result={"strategy": "growth"},
            confidence=0.85,
        )
        entity = EventOutboxAdapter.from_domain_event(event)
        restored = EventOutboxAdapter.to_domain_event(entity)

        assert restored.event_type == event.event_type
        assert str(restored.payload.get("agent_id")) == str(event.agent_id)
        assert restored.payload.get("confidence") == event.confidence

    def test_all_event_types_registered(self):
        """All 10 event types should be registered in DomainEvent._registry."""
        expected_types = [
            "DocumentProcessed",
            "ToolExecuted",
            "AgentDecided",
            "CheckpointReached",
            "CorrectionApproved",
            "StrategicDeviationWarning",
            "HeartbeatTriggered",
            "IsolationLevelSwitched",
            "CheckpointRecovered",
            "RoutingDecided",
        ]
        for event_type in expected_types:
            event_class = DomainEvent._registry.get(event_type)
            assert event_class is not None, f"{event_type} not registered"

    def test_unknown_event_type_raises_error(self):
        """Should raise ValueError for unknown event type."""
        entity = OutboxEntity()
        entity.event_type = "NonExistentEvent"
        entity.payload = {}

        with pytest.raises(ConfigurationError, match="Unknown event_type"):
            EventOutboxAdapter.to_domain_event(entity)


class TestEventRegistry:
    """DomainEvent._registry 注册表行为测试"""

    @pytest.fixture(autouse=True)
    def _preserve_registry(self):
        """每个测试前后保存/恢复 registry，防止测试间污染"""
        saved = dict(DomainEvent._registry)
        yield
        DomainEvent._registry.clear()
        DomainEvent._registry.update(saved)

    def test_reset_clears_registry(self) -> None:
        """reset_registry 应清空注册表"""
        # 先验证有注册内容
        assert len(DomainEvent._registry) > 0

        DomainEvent.reset_registry()
        assert len(DomainEvent._registry) == 0

    def test_rebuild_after_reset(self) -> None:
        """reset_registry 后手动注册可恢复事件"""
        DomainEvent.reset_registry()
        assert len(DomainEvent._registry) == 0

        # 手动注册后可用
        DomainEvent.register("DocumentProcessed", DocumentProcessed)
        event_class = DomainEvent._registry.get("DocumentProcessed")
        assert event_class is not None

    def test_register_manual_event_type(self) -> None:
        """应支持手动注册自定义事件类型"""
        DomainEvent.reset_registry()

        # 注册已有事件类型（安全的手动注册测试）
        DomainEvent.register("DocumentProcessed", DocumentProcessed)
        result = DomainEvent._registry.get("DocumentProcessed")
        assert result is DocumentProcessed

    def test_get_returns_correct_subclass(self) -> None:
        """_registry.get 应返回正确的事件子类"""
        cls = DomainEvent._registry.get("ToolExecuted")
        assert cls is ToolExecuted

        cls = DomainEvent._registry.get("AgentDecided")
        assert cls is AgentDecided

    def test_registry_contains_all_subclasses(self) -> None:
        """注册表应包含所有通过 __init_subclass__ 注册的子类"""
        # 所有通过 __init_subclass__ 注册的事件类型应存在于注册表
        for subclass in DomainEvent.__subclasses__():
            # 检查子类是否有 event_type field defined with init=False
            if hasattr(subclass, "__dataclass_fields__"):
                et_field = subclass.__dataclass_fields__.get("event_type")
                if et_field is not None and not et_field.init:
                    # event_type should be in registry
                    if et_field.default:
                        assert et_field.default in DomainEvent._registry


class TestEventOutboxAdapterFromDomainEvent:
    """from_domain_event 转换细节测试"""

    def test_entity_fields_populated(self) -> None:
        """OutboxEntity 应正确填充所有字段"""
        event = DocumentProcessed(
            document_id=uuid4(),
            parse_result={"pages": 5},
            embedding=[0.1] * 1024,
        )
        entity = EventOutboxAdapter.from_domain_event(event)

        assert entity.event_id == event.event_id
        assert entity.event_type == event.event_type
        assert entity.status == "pending"
        assert entity.created_at == event.timestamp
        assert isinstance(entity.payload, dict)

    def test_entity_payload_contains_event_data(self) -> None:
        """payload 应包含事件的序列化数据"""
        doc_id = uuid4()
        event = DocumentProcessed(
            document_id=doc_id,
            parse_result={"pages": 3},
            embedding=[0.1] * 1024,
        )
        entity = EventOutboxAdapter.from_domain_event(event)
        payload = entity.payload

        assert "event_id" in payload
        assert "event_type" in payload
        assert payload["event_type"] == "DocumentProcessed"
