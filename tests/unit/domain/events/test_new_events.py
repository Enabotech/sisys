"""Tests for new domain events (Story 1.2)."""

import uuid

from src.domain.events.deviation_events import (
    HeartbeatTriggered,
    StrategicDeviationWarning,
)
from src.domain.events.enums import DeviationLevel, IsolationLevel, RecoveryMode
from src.domain.events.isolation_events import (
    CheckpointRecovered,
    IsolationLevelSwitched,
)
from src.domain.events.routing_events import RoutingDecided


class TestStrategicDeviationWarning:
    """Test StrategicDeviationWarning event."""

    def test_create_event(self):
        """Can create StrategicDeviationWarning event."""
        warning_id = uuid.uuid4()
        event = StrategicDeviationWarning(
            warning_id=warning_id,
            deviation_type="budget_overrun",
            deviation_level=DeviationLevel.SEVERE,
            actual_value=150000.0,
            planned_value=100000.0,
            threshold=10.0,
        )
        assert event.event_type == "StrategicDeviationWarning"
        assert event.aggregate_id == warning_id
        assert event.deviation_level == DeviationLevel.SEVERE
        assert event.actual_value == 150000.0

    def test_default_values(self):
        """Event has sensible defaults."""
        event = StrategicDeviationWarning(warning_id=uuid.uuid4())
        assert event.deviation_level == DeviationLevel.MINOR
        assert event.actual_value == 0.0
        assert event.planned_value == 0.0

    def test_serialization(self):
        """StrategicDeviationWarning serializes correctly."""
        event = StrategicDeviationWarning(warning_id=uuid.uuid4())
        d = event.to_dict()
        assert d["event_type"] == "StrategicDeviationWarning"


class TestHeartbeatTriggered:
    """Test HeartbeatTriggered event."""

    def test_create_event(self):
        """Can create HeartbeatTriggered event."""
        heartbeat_id = uuid.uuid4()
        event = HeartbeatTriggered(
            heartbeat_id=heartbeat_id,
            wake_reason="periodic_check",
            todo_items=["check_budget", "check_timeline"],
            cost_budget=50.0,
        )
        assert event.event_type == "HeartbeatTriggered"
        assert event.aggregate_id == heartbeat_id
        assert event.wake_reason == "periodic_check"
        assert len(event.todo_items) == 2

    def test_default_values(self):
        """Event has sensible defaults."""
        event = HeartbeatTriggered(heartbeat_id=uuid.uuid4())
        assert event.wake_reason == ""
        assert event.todo_items == ()  # tuple default for immutability
        assert event.cost_budget == 0.0

    def test_serialization(self):
        """HeartbeatTriggered serializes correctly."""
        event = HeartbeatTriggered(heartbeat_id=uuid.uuid4())
        d = event.to_dict()
        assert d["event_type"] == "HeartbeatTriggered"


class TestIsolationLevelSwitched:
    """Test IsolationLevelSwitched event."""

    def test_create_event(self):
        """Can create IsolationLevelSwitched event."""
        agent_id = uuid.uuid4()
        event = IsolationLevelSwitched(
            agent_id=agent_id,
            previous_level=IsolationLevel.L4_HARD,
            target_level=IsolationLevel.L2_COLLAB,
            trigger_reason="joint_task_assigned",
            approval_chain=["sys_agent"],
        )
        assert event.event_type == "IsolationLevelSwitched"
        assert event.aggregate_id == agent_id
        assert event.target_level == IsolationLevel.L2_COLLAB
        assert event.switch_timestamp.tzinfo is not None

    def test_default_values(self):
        """Event has sensible defaults."""
        event = IsolationLevelSwitched(agent_id=uuid.uuid4())
        assert event.previous_level == IsolationLevel.L4_HARD
        assert event.target_level == IsolationLevel.L4_HARD
        assert event.trigger_reason == ""

    def test_serialization(self):
        """IsolationLevelSwitched serializes correctly."""
        event = IsolationLevelSwitched(agent_id=uuid.uuid4())
        d = event.to_dict()
        assert d["event_type"] == "IsolationLevelSwitched"


class TestCheckpointRecovered:
    """Test CheckpointRecovered event."""

    def test_create_event_replay(self):
        """Can create CheckpointRecovered event in Replay mode."""
        cp_id = uuid.uuid4()
        event = CheckpointRecovered(
            checkpoint_id=cp_id,
            recovery_mode=RecoveryMode.REPLAY,
            modification_content={"assumption": "changed"},
            affected_checkpoints=["cp-2", "cp-3"],
            consistency_risk_level="medium",
            execution_delay_ms=1500.0,
            cost=0.05,
        )
        assert event.event_type == "CheckpointRecovered"
        assert event.aggregate_id == cp_id
        assert event.recovery_mode == RecoveryMode.REPLAY
        assert len(event.affected_checkpoints) == 2

    def test_create_event_override(self):
        """Can create CheckpointRecovered event in Override mode."""
        cp_id = uuid.uuid4()
        event = CheckpointRecovered(
            checkpoint_id=cp_id,
            recovery_mode=RecoveryMode.OVERRIDE,
            consistency_risk_level="high",
        )
        assert event.recovery_mode == RecoveryMode.OVERRIDE

    def test_default_values(self):
        """Event has sensible defaults."""
        event = CheckpointRecovered(checkpoint_id=uuid.uuid4())
        assert event.recovery_mode == RecoveryMode.REPLAY
        assert event.modification_content == {}
        assert event.consistency_risk_level == "low"

    def test_serialization(self):
        """CheckpointRecovered serializes correctly."""
        event = CheckpointRecovered(checkpoint_id=uuid.uuid4())
        d = event.to_dict()
        assert d["event_type"] == "CheckpointRecovered"


class TestRoutingDecided:
    """Test RoutingDecided event."""

    def test_create_event(self):
        """Can create RoutingDecided event."""
        task_id = uuid.uuid4()
        event = RoutingDecided(
            task_id=task_id,
            l1_compliance_result={"allowed": True, "data_sovereign": True},
            l2_factor_scores={
                "semantic_match": 0.9,
                "historical_success": 0.85,
                "cost_efficiency": 0.7,
                "task_complexity": 0.6,
            },
            final_routing_score=0.82,
            selected_model="local-llm-v2",
            estimated_cost=0.03,
        )
        assert event.event_type == "RoutingDecided"
        assert event.aggregate_id == task_id
        assert event.selected_model == "local-llm-v2"
        assert event.final_routing_score == 0.82

    def test_default_values(self):
        """Event has sensible defaults."""
        event = RoutingDecided(task_id=uuid.uuid4())
        assert event.l1_compliance_result == {}
        assert event.l2_factor_scores == {}
        assert event.final_routing_score == 0.0
        assert event.selected_model == ""

    def test_serialization(self):
        """RoutingDecided serializes correctly."""
        event = RoutingDecided(task_id=uuid.uuid4())
        d = event.to_dict()
        assert d["event_type"] == "RoutingDecided"
