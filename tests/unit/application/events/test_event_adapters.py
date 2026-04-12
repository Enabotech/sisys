"""Tests for application layer event adapters."""

import json
import uuid

import pytest

from src.application.events.adapters import event_dict_to_json, json_to_event_dict
from src.domain.events.base import DomainEvent
from src.domain.events.plan_events import DocumentProcessed


class TestEventDictToJson:
    """Test event dict to JSON conversion."""

    def test_dict_to_json(self):
        """Can convert event dict to JSON string."""
        event = DocumentProcessed(document_id=uuid.uuid4())
        d = event.to_dict()
        json_str = event_dict_to_json(d)
        assert isinstance(json_str, str)
        assert "DocumentProcessed" in json_str

    def test_json_is_valid(self):
        """JSON output is valid."""
        event = DocumentProcessed(document_id=uuid.uuid4())
        d = event.to_dict()
        json_str = event_dict_to_json(d)
        parsed = json.loads(json_str)
        assert parsed["event_type"] == "DocumentProcessed"


class TestJsonToEventDict:
    """Test JSON to event dict conversion."""

    def test_json_to_dict(self):
        """Can convert JSON string to event dict."""
        event = DocumentProcessed(document_id=uuid.uuid4())
        d = event.to_dict()
        json_str = json.dumps(d)
        restored = json_to_event_dict(json_str)
        assert restored["event_type"] == "DocumentProcessed"
        assert restored["event_id"] == d["event_id"]

    def test_invalid_json_raises(self):
        """Invalid JSON raises ValueError."""
        with pytest.raises(ValueError, match="Invalid JSON string"):
            json_to_event_dict("not valid json{{{")

    def test_roundtrip_via_adapters(self):
        """Full roundtrip via application layer adapters."""
        original = DocumentProcessed(document_id=uuid.uuid4())
        d = original.to_dict()
        json_str = event_dict_to_json(d)
        restored_dict = json_to_event_dict(json_str)
        # DomainEvent.from_dict returns base class (correct behavior for application layer)
        restored = DomainEvent.from_dict(restored_dict)
        assert restored.event_id == original.event_id
        assert restored.event_type == original.event_type
        assert restored.aggregate_id == original.aggregate_id
