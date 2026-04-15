"""SQLAlchemyEventOutboxAdapter 单元测试。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from src.domain.events.base import DomainEvent
from src.domain.events.document_events import DocumentProcessed
from src.infrastructure.adapters.sqlalchemy_event_outbox_adapter import SQLAlchemyEventOutboxAdapter
from src.infrastructure.storage.postgresql.models import OutboxModel


class TestSQLAlchemyEventOutboxAdapter:
    """SQLAlchemyEventOutboxAdapter 测试。"""

    def test_from_domain_event(self):
        """测试 DomainEvent → OutboxModel 转换。"""
        event = DomainEvent(
            event_id=uuid4(),
            event_type="TestEvent",
            timestamp=datetime.now(UTC),
            source="test",
            payload={"key": "value"},
        )

        model = SQLAlchemyEventOutboxAdapter.from_domain_event(event)

        assert isinstance(model, OutboxModel)
        assert model.event_id == event.event_id
        assert model.event_type == "TestEvent"
        assert model.status == "pending"
        assert model.payload["event_type"] == "TestEvent"
        assert model.created_at == event.timestamp

    def test_to_domain_event(self):
        """测试 OutboxModel → DomainEvent 转换。"""
        event_id = uuid4()
        model = OutboxModel(
            event_id=event_id,
            event_type="DocumentProcessed",
            payload={
                "event_id": str(event_id),
                "event_type": "DocumentProcessed",
                "timestamp": datetime.now(UTC).isoformat(),
                "source": "test",
                "payload": {"doc_id": "123"},
            },
            created_at=datetime.now(UTC),
        )

        event = SQLAlchemyEventOutboxAdapter.to_domain_event(model)

        assert isinstance(event, DomainEvent)
        assert event.event_type == "DocumentProcessed"

    def test_roundtrip(self):
        """测试双向转换。"""
        original_event = DocumentProcessed(
            document_id=uuid4(),
        )

        model = SQLAlchemyEventOutboxAdapter.from_domain_event(original_event)
        restored_event = SQLAlchemyEventOutboxAdapter.to_domain_event(model)

        assert restored_event.event_type == original_event.event_type
        assert restored_event.event_id == original_event.event_id
