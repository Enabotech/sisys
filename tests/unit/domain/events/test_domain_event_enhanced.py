"""Task 4 TDD Tests — DomainEvent Enhancement (AC-4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from src.domain.events.base import DomainEvent


class TestDomainEventEnhancement:
    """Test DomainEvent enhancement with correlation_id, causation_id, metadata."""

    def test_domain_event_has_correlation_id_field(self) -> None:
        """DomainEvent should have correlation_id field as UUID | None."""
        event = DomainEvent(event_type="TestEvent")
        assert hasattr(event, "correlation_id")
        assert event.correlation_id is None

    def test_domain_event_has_causation_id_field(self) -> None:
        """DomainEvent should have causation_id field as UUID | None."""
        event = DomainEvent(event_type="TestEvent")
        assert hasattr(event, "causation_id")
        assert event.causation_id is None

    def test_domain_event_has_metadata_field(self) -> None:
        """DomainEvent should have metadata field as dict[str, Any]."""
        event = DomainEvent(event_type="TestEvent")
        assert hasattr(event, "metadata")
        assert isinstance(event.metadata, dict)
        assert event.metadata == {}

    def test_domain_event_accepts_correlation_id(self) -> None:
        """DomainEvent should accept correlation_id in constructor."""
        corr_id = uuid4()
        event = DomainEvent(event_type="TestEvent", correlation_id=corr_id)
        assert event.correlation_id == corr_id

    def test_domain_event_accepts_causation_id(self) -> None:
        """DomainEvent should accept causation_id in constructor."""
        caus_id = uuid4()
        event = DomainEvent(event_type="TestEvent", causation_id=caus_id)
        assert event.causation_id == caus_id

    def test_domain_event_accepts_metadata(self) -> None:
        """DomainEvent should accept metadata in constructor."""
        meta = {"user": "test", "session": "abc"}
        event = DomainEvent(event_type="TestEvent", metadata=meta)
        assert event.metadata == meta

    def test_to_dict_includes_new_fields(self) -> None:
        """to_dict() should include correlation_id, causation_id, metadata at top level."""
        corr_id = uuid4()
        caus_id = uuid4()
        meta = {"key": "value"}
        event = DomainEvent(
            event_type="TestEvent",
            correlation_id=corr_id,
            causation_id=caus_id,
            metadata=meta,
        )
        result = event.to_dict()
        assert "correlation_id" in result
        assert result["correlation_id"] == str(corr_id)
        assert "causation_id" in result
        assert result["causation_id"] == str(caus_id)
        assert "metadata" in result
        assert result["metadata"] == meta

    def test_to_dict_excludes_none_values_for_traceability_fields(self) -> None:
        """to_dict() should not include correlation_id/causation_id when None."""
        event = DomainEvent(event_type="TestEvent")
        result = event.to_dict()
        assert "correlation_id" not in result
        assert "causation_id" not in result

    def test_from_dict_restores_correlation_id(self) -> None:
        """from_dict() should restore correlation_id field."""
        corr_id = uuid4()
        data = {
            "event_id": str(uuid4()),
            "event_type": "TestEvent",
            "timestamp": datetime.now(UTC).isoformat(),
            "correlation_id": str(corr_id),
        }
        event = DomainEvent.from_dict(data)
        assert event.correlation_id == corr_id

    def test_from_dict_restores_causation_id(self) -> None:
        """from_dict() should restore causation_id field."""
        caus_id = uuid4()
        data = {
            "event_id": str(uuid4()),
            "event_type": "TestEvent",
            "timestamp": datetime.now(UTC).isoformat(),
            "causation_id": str(caus_id),
        }
        event = DomainEvent.from_dict(data)
        assert event.causation_id == caus_id

    def test_from_dict_restores_metadata(self) -> None:
        """from_dict() should restore metadata field."""
        meta = {"user": "test"}
        data = {
            "event_id": str(uuid4()),
            "event_type": "TestEvent",
            "timestamp": datetime.now(UTC).isoformat(),
            "metadata": meta,
        }
        event = DomainEvent.from_dict(data)
        assert event.metadata == meta

    def test_backward_compatibility_existing_subclass(self) -> None:
        """Existing subclasses should remain compatible without changes."""

        @dataclass(frozen=True)
        class TestEvent(DomainEvent):
            event_type: str = field(default="TestEvent", init=False)
            document_id: str = "default-doc"

        event = TestEvent(document_id="doc-123")
        assert event.event_type == "TestEvent"
        assert event.document_id == "doc-123"
        # New fields should have defaults
        assert event.correlation_id is None
        assert event.causation_id is None
        assert event.metadata == {}

    def test_backward_compatibility_to_dict(self) -> None:
        """Existing subclass to_dict() should still work correctly."""

        @dataclass(frozen=True)
        class TestEvent(DomainEvent):
            event_type: str = field(default="TestEvent", init=False)
            value: int = 42

        event = TestEvent()
        result = event.to_dict()
        assert result["event_type"] == "TestEvent"
        assert result["payload"]["value"] == 42

    def test_backward_compatibility_from_dict_without_new_fields(self) -> None:
        """from_dict() should work without correlation_id/causation_id/metadata fields."""
        # This tests backward compatibility: old serialized events without the new
        # fields should deserialize correctly
        data = {
            "event_id": str(uuid4()),
            "event_type": "TestEvent",
            "timestamp": datetime.now(UTC).isoformat(),
            "payload": {"key": "value"},
        }
        event = DomainEvent.from_dict(data)
        assert event.event_type == "TestEvent"
        assert event.correlation_id is None
        assert event.causation_id is None
        assert event.metadata == {}
