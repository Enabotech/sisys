"""Tests for event serialization (Story 1.2)."""

import json
import uuid

import pytest

from src.domain.events import DocumentProcessed
from src.domain.events.base import DomainEvent
from src.domain.events.checkpoint_events import CheckpointRecovered
from src.domain.events.enums import DeviationLevel, DeviationType, RecoveryMode
from src.domain.events.heartbeat_events import HeartbeatTriggered
from src.domain.events.isolation_events import (
    IsolationLevelSwitched,
)
from src.domain.events.planning_events import StrategicDeviationWarning
from src.domain.events.routing_events import RoutingDecided


class TestToDictSerialization:
    """Test to_dict() serialization for all 10 event types."""

    def test_document_processed_to_dict(self):
        """DocumentProcessed serializes to dict."""
        doc_id = uuid.uuid4()
        event = DocumentProcessed(
            document_id=doc_id,
            parse_result={"pages": 42},
            embedding=[0.1, 0.2],
        )
        d = event.to_dict()
        assert d["event_type"] == "DocumentProcessed"
        assert d["aggregate_id"] == str(doc_id)
        assert "event_id" in d
        assert "occurred_on" in d
        # Subclass-specific fields are in payload
        assert "document_id" in d["payload"]
        assert "parse_result" in d["payload"]
        assert "embedding" in d["payload"]

    def test_strategic_deviation_warning_to_dict(self):
        """StrategicDeviationWarning serializes to dict."""
        event = StrategicDeviationWarning(
            warning_id=uuid.uuid4(),
            deviation_type=DeviationType.SCOPE_CREEP,
            deviation_level=DeviationLevel.SEVERE,
            actual_value=200.0,
            planned_value=100.0,
        )
        d = event.to_dict()
        assert d["event_type"] == "StrategicDeviationWarning"
        assert "deviation_level" in d["payload"]

    def test_heartbeat_triggered_to_dict(self):
        """HeartbeatTriggered serializes to dict."""
        event = HeartbeatTriggered(
            heartbeat_id=uuid.uuid4(),
            wake_reason="scheduled_check",
            todo_items=["task1", "task2"],
        )
        d = event.to_dict()
        assert d["event_type"] == "HeartbeatTriggered"
        assert "wake_reason" in d["payload"]

    def test_isolation_level_switched_to_dict(self):
        """IsolationLevelSwitched serializes to dict."""
        event = IsolationLevelSwitched(
            agent_id=uuid.uuid4(),
            previous_level="L4",
            target_level="L2",
            trigger_reason="joint_task",
        )
        d = event.to_dict()
        assert d["event_type"] == "IsolationLevelSwitched"
        assert "agent_id" in d["payload"]

    def test_checkpoint_recovered_to_dict(self):
        """CheckpointRecovered serializes to dict."""
        event = CheckpointRecovered(
            checkpoint_id=uuid.uuid4(),
            recovery_mode=RecoveryMode.OVERRIDE,
            consistency_risk_level="high",
        )
        d = event.to_dict()
        assert d["event_type"] == "CheckpointRecovered"
        assert "recovery_mode" in d["payload"]

    def test_routing_decided_to_dict(self):
        """RoutingDecided serializes to dict."""
        event = RoutingDecided(
            task_id=uuid.uuid4(),
            selected_model="gpt-4",
            final_routing_score=0.92,
        )
        d = event.to_dict()
        assert d["event_type"] == "RoutingDecided"
        assert "task_id" in d["payload"]


class TestFromDictDeserialization:
    """Test from_dict() deserialization roundtrip."""

    def test_document_processed_roundtrip(self):
        """DocumentProcessed survives roundtrip with all fields."""
        doc_id = uuid.uuid4()
        original = DocumentProcessed(
            document_id=doc_id,
            parse_result={"pages": 10},
            embedding=[0.1, 0.2],
        )
        d = original.to_dict()
        restored = DomainEvent.from_dict(d)
        assert restored.event_id == original.event_id
        assert restored.event_type == original.event_type
        assert restored.aggregate_id == original.aggregate_id
        # 往返序列化后 payload 应与原始事件一致
        assert restored.payload == original.payload
        # 子类字段应通过属性访问，而非在 payload 中重复
        assert isinstance(restored, DocumentProcessed)
        assert str(restored.document_id) == str(original.document_id)
        assert restored.parse_result == original.parse_result

    def test_strategic_deviation_warning_roundtrip(self):
        """StrategicDeviationWarning survives roundtrip."""
        original = StrategicDeviationWarning(
            warning_id=uuid.uuid4(),
            deviation_level=DeviationLevel.MODERATE,
            actual_value=150.0,
        )
        d = original.to_dict()
        restored = DomainEvent.from_dict(d)
        assert restored.event_id == original.event_id
        assert restored.event_type == original.event_type

    def test_heartbeat_triggered_roundtrip(self):
        """HeartbeatTriggered survives roundtrip."""
        original = HeartbeatTriggered(
            heartbeat_id=uuid.uuid4(),
            wake_reason="budget_check",
        )
        d = original.to_dict()
        restored = DomainEvent.from_dict(d)
        assert restored.event_id == original.event_id
        assert restored.event_type == original.event_type

    def test_isolation_level_switched_roundtrip(self):
        """IsolationLevelSwitched survives roundtrip."""
        original = IsolationLevelSwitched(
            agent_id=uuid.uuid4(),
            trigger_reason="collaboration",
        )
        d = original.to_dict()
        restored = DomainEvent.from_dict(d)
        assert restored.event_id == original.event_id
        assert restored.event_type == original.event_type

    def test_checkpoint_recovered_roundtrip(self):
        """CheckpointRecovered survives roundtrip."""
        original = CheckpointRecovered(
            checkpoint_id=uuid.uuid4(),
            recovery_mode=RecoveryMode.REPLAY,
        )
        d = original.to_dict()
        restored = DomainEvent.from_dict(d)
        assert restored.event_id == original.event_id
        assert restored.event_type == original.event_type

    def test_routing_decided_roundtrip(self):
        """RoutingDecided survives roundtrip."""
        original = RoutingDecided(
            task_id=uuid.uuid4(),
            selected_model="claude-3",
        )
        d = original.to_dict()
        restored = DomainEvent.from_dict(d)
        assert restored.event_id == original.event_id
        assert restored.event_type == original.event_type


class TestJSONRoundTrip:
    """Test JSON serialization roundtrip (event → dict → JSON → dict → event)."""

    def test_json_roundtrip_document_processed(self):
        """DocumentProcessed survives JSON roundtrip."""
        doc_id = uuid.uuid4()
        event = DocumentProcessed(document_id=doc_id)
        d = event.to_dict()
        json_str = json.dumps(d)
        restored_dict = json.loads(json_str)
        restored = DomainEvent.from_dict(restored_dict)
        assert restored.event_id == event.event_id
        assert restored.event_type == event.event_type

    def test_json_roundtrip_strategic_deviation_warning(self):
        """StrategicDeviationWarning survives JSON roundtrip."""
        event = StrategicDeviationWarning(
            warning_id=uuid.uuid4(),
            deviation_level=DeviationLevel.SEVERE,
            actual_value=150.0,
            planned_value=100.0,
        )
        d = event.to_dict()
        json_str = json.dumps(d)
        restored_dict = json.loads(json_str)
        restored = DomainEvent.from_dict(restored_dict)
        assert restored.event_id == event.event_id
        assert restored.event_type == event.event_type

    def test_json_roundtrip_heartbeat_triggered(self):
        """HeartbeatTriggered survives JSON roundtrip."""
        event = HeartbeatTriggered(
            heartbeat_id=uuid.uuid4(),
            todo_items=["check_a", "check_b"],
            cost_budget=25.0,
        )
        d = event.to_dict()
        json_str = json.dumps(d)
        restored_dict = json.loads(json_str)
        restored = DomainEvent.from_dict(restored_dict)
        assert restored.event_id == event.event_id

    def test_json_roundtrip_isolation_level_switched(self):
        """IsolationLevelSwitched survives JSON roundtrip."""
        event = IsolationLevelSwitched(
            agent_id=uuid.uuid4(),
            approval_chain=["admin", "sys_agent"],
        )
        d = event.to_dict()
        json_str = json.dumps(d)
        restored_dict = json.loads(json_str)
        restored = DomainEvent.from_dict(restored_dict)
        assert restored.event_id == event.event_id

    def test_json_roundtrip_checkpoint_recovered(self):
        """CheckpointRecovered survives JSON roundtrip."""
        event = CheckpointRecovered(
            checkpoint_id=uuid.uuid4(),
            affected_checkpoints=["cp-1", "cp-2", "cp-3"],
        )
        d = event.to_dict()
        json_str = json.dumps(d)
        restored_dict = json.loads(json_str)
        restored = DomainEvent.from_dict(restored_dict)
        assert restored.event_id == event.event_id

    def test_json_roundtrip_routing_decided(self):
        """RoutingDecided survives JSON roundtrip."""
        event = RoutingDecided(
            task_id=uuid.uuid4(),
            l2_factor_scores={"semantic_match": 0.9, "cost_efficiency": 0.7},
            final_routing_score=0.85,
        )
        d = event.to_dict()
        json_str = json.dumps(d)
        restored_dict = json.loads(json_str)
        restored = DomainEvent.from_dict(restored_dict)
        assert restored.event_id == event.event_id


class TestDeserializationErrors:
    """Test deserialization error handling."""

    def test_from_dict_missing_event_id_raises(self):
        """Missing event_id raises ValueError."""
        with pytest.raises((KeyError, ValueError)):
            DomainEvent.from_dict({"event_type": "Test"})

    def test_from_dict_missing_event_type_raises(self):
        """Missing event_type raises ValueError."""
        with pytest.raises((KeyError, ValueError)):
            DomainEvent.from_dict({"event_id": str(uuid.uuid4())})

    def test_from_dict_invalid_uuid_raises(self):
        """Invalid UUID raises ValueError."""
        with pytest.raises(ValueError):
            DomainEvent.from_dict(
                {
                    "event_id": "not-a-uuid",
                    "event_type": "Test",
                    "occurred_on": "2026-01-01T00:00:00+00:00",
                }
            )

    def test_from_dict_invalid_datetime_raises(self):
        """Invalid datetime raises ValueError."""
        with pytest.raises(ValueError):
            DomainEvent.from_dict(
                {
                    "event_id": str(uuid.uuid4()),
                    "event_type": "Test",
                    "occurred_on": "not-a-datetime",
                }
            )
