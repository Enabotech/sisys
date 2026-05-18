"""Task 3 TDD Tests — OutboxEntity and EventOutboxAdapter."""

from __future__ import annotations

from dataclasses import asdict, field
from datetime import datetime
from uuid import uuid4

import pytest

from src.domain.events import DocumentProcessed
from src.domain.events.base import DomainEvent
from src.infrastructure.messaging.adapters.event_outbox_adapter import EventOutboxAdapter
from src.infrastructure.messaging.outbox.outbox import InvalidStateTransitionError, OutboxEntity


class _MockEventForTest(DomainEvent):
    """Mock event class for testing DomainEvent._registry."""

    event_type: str = field(default="MockEventForTest", init=False)


def _make_event() -> DocumentProcessed:
    return DocumentProcessed(
        document_id=uuid4(),
        parse_result={"pages": 10},
        embedding=[0.1] * 1024,
    )


class TestOutboxEntity:
    """OutboxEntity tests."""

    def test_default_values(self):
        """OutboxEntity should have sensible defaults."""
        entity = OutboxEntity()
        assert entity.status == "pending"
        assert entity.retry_count == 0
        assert entity.max_retries == 3
        assert entity.error_message is None
        assert entity.published_at is None
        assert entity.id == 0
        assert entity.payload == {}

    def test_custom_values(self):
        """OutboxEntity should accept custom values."""
        eid = uuid4()
        entity = OutboxEntity(
            event_id=eid,
            event_type="DocumentProcessed",
            payload={"test": "data"},
            status="pending",
            retry_count=2,
            max_retries=5,
        )
        assert entity.event_id == eid
        assert entity.retry_count == 2
        assert entity.max_retries == 5

    def test_asdict_serialization(self):
        """OutboxEntity should be serializable via dataclasses.asdict."""
        entity = OutboxEntity()
        entity.event_type = "TestEvent"
        entity.payload = {"key": "value"}

        d = asdict(entity)
        assert d["event_type"] == "TestEvent"
        assert d["payload"] == {"key": "value"}
        assert d["status"] == "pending"

    def test_mark_published(self):
        """Should transition from pending to published."""
        entity = OutboxEntity()
        entity.mark_published()
        assert entity.status == "published"
        assert entity.published_at is not None
        assert isinstance(entity.published_at, datetime)

    def test_mark_published_from_wrong_status(self):
        """Should raise InvalidStateTransitionError from wrong status."""
        entity = OutboxEntity()
        entity.mark_published()
        with pytest.raises(InvalidStateTransitionError):
            entity.mark_published()

    def test_mark_failed(self):
        """Should transition to failed and increment retry_count."""
        entity = OutboxEntity()
        entity.mark_failed("connection error")
        assert entity.status == "failed"
        assert entity.retry_count == 1
        assert entity.error_message == "connection error"

    def test_mark_pending_retry(self):
        """Should transition from failed to pending if retries remaining."""
        entity = OutboxEntity()
        entity.max_retries = 3
        entity.mark_failed("error")
        entity.mark_pending()
        assert entity.status == "pending"
        assert entity.error_message is None

    def test_mark_pending_exceeds_max_retries(self):
        """Should raise if retry_count >= max_retries."""
        entity = OutboxEntity()
        entity.max_retries = 3
        entity.retry_count = 3
        entity.status = "failed"
        with pytest.raises(InvalidStateTransitionError):
            entity.mark_pending()

    def test_mark_archived(self):
        """Should transition from failed to archived."""
        entity = OutboxEntity()
        entity.status = "failed"
        entity.mark_archived()
        assert entity.status == "archived"

    def test_mark_archived_from_wrong_status(self):
        """Should raise if not from failed status."""
        entity = OutboxEntity()
        with pytest.raises(InvalidStateTransitionError):
            entity.mark_archived()


class TestEventOutboxAdapter:
    """EventOutboxAdapter tests."""

    @pytest.fixture(autouse=True)
    def _preserve_registry(self):
        """每个测试前后保存/恢复 registry，防止测试间污染"""
        saved = dict(DomainEvent._registry)
        yield
        DomainEvent._registry.clear()
        DomainEvent._registry.update(saved)

    def test_from_domain_event(self):
        """Should convert DomainEvent to OutboxEntity."""
        event = _make_event()
        entity = EventOutboxAdapter.from_domain_event(event)

        assert entity.event_id == event.event_id
        assert entity.event_type == event.event_type
        assert entity.status == "pending"
        assert entity.payload == event.to_dict()

    def test_to_domain_event(self):
        """Should convert OutboxEntity back to DomainEvent."""
        event = _make_event()
        entity = EventOutboxAdapter.from_domain_event(event)
        restored = EventOutboxAdapter.to_domain_event(entity)

        assert restored.event_id == event.event_id
        assert restored.event_type == event.event_type
        # DomainEvent.from_dict returns DomainEvent with subclass fields in payload
        assert "document_id" in restored.payload

    def test_roundtrip(self):
        """DomainEvent → OutboxEntity → DomainEvent should preserve data."""
        event = _make_event()
        entity = EventOutboxAdapter.from_domain_event(event)
        restored = EventOutboxAdapter.to_domain_event(entity)

        assert restored.event_id == event.event_id
        assert restored.event_type == event.event_type
        # Subclass fields are preserved in payload (UUIDs as strings)
        assert str(restored.payload.get("document_id")) == str(event.document_id)
        assert restored.payload.get("parse_result") == event.parse_result

    def test_to_domain_event_unknown_type(self):
        """Should raise ValueError for unknown event_type."""
        entity = OutboxEntity()
        entity.event_type = "UnknownEvent"
        entity.payload = {}

        with pytest.raises(ValueError, match="Unknown event_type"):
            EventOutboxAdapter.to_domain_event(entity)

    def test_registry_manual_register(self) -> None:
        """DomainEvent.register should support manual registration."""

        DomainEvent.register("MockEventForTest", _MockEventForTest)
        event_class = DomainEvent._registry.get("MockEventForTest")
        assert event_class == _MockEventForTest

    def test_registry_reset(self) -> None:
        """DomainEvent.reset_registry should clear the registry."""
        DomainEvent.reset_registry()
        # 手动注册恢复
        DomainEvent.register("DocumentProcessed", DocumentProcessed)
        event_class = DomainEvent._registry.get("DocumentProcessed")
        assert event_class is not None
