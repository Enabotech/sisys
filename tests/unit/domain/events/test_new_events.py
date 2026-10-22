"""Tests for new domain events (Story 1.2)."""

import uuid

import pytest

from src.domain.events.checkpoint_events import CheckpointRecovered
from src.domain.events.enums import DeviationLevel, DeviationType, IsolationLevel, RecoveryMode
from src.domain.events.heartbeat_events import HeartbeatTriggered
from src.domain.events.isolation_events import (
    IsolationLevelSwitched,
)
from src.domain.events.planning_events import StrategicDeviationWarning
from src.domain.events.routing_events import RoutingDecided


class TestStrategicDeviationWarning:
    """Test StrategicDeviationWarning event."""

    def test_create_event(self):
        """Can create StrategicDeviationWarning event."""
        warning_id = uuid.uuid4()
        event = StrategicDeviationWarning(
            warning_id=warning_id,
            deviation_type=DeviationType.BUDGET_OVERUN,
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
    """Test IsolationLevelSwitched event.

    Story 5-4 纪律收紧（DC-6）: agent_id/previous_level/target_level/trigger_reason
    四核心字段 kw_only 必填（切换事件核心语义必填——空 reason 是无意义的切换事件）；
    approval_chain/switch_timestamp 保留默认（MVP 用户请求无审批链）。
    """

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

    def test_optional_fields_keep_defaults(self):
        """可选字段保留默认: approval_chain 空清单 + switch_timestamp 自动 now(UTC)。"""
        event = IsolationLevelSwitched(
            agent_id=uuid.uuid4(),
            previous_level=IsolationLevel.L4_HARD,
            target_level=IsolationLevel.L3_SOFT,
            trigger_reason="任务需要软隔离",
        )
        assert event.approval_chain == []
        assert event.switch_timestamp.tzinfo is not None

    def test_required_fields_kw_only_missing_raises(self):
        """四核心必填字段缺任一 → TypeError（kw_only 必填——5-2 纪律先例）。"""
        from typing import Any

        full_kwargs: dict[str, Any] = {
            "agent_id": uuid.uuid4(),
            "previous_level": IsolationLevel.L4_HARD,
            "target_level": IsolationLevel.L3_SOFT,
            "trigger_reason": "缺参探测",
        }
        for missing in ("agent_id", "previous_level", "target_level", "trigger_reason"):
            partial = {key: value for key, value in full_kwargs.items() if key != missing}
            with pytest.raises(TypeError):
                IsolationLevelSwitched(**partial)

    def test_serialization(self):
        """IsolationLevelSwitched serializes correctly."""
        event = IsolationLevelSwitched(
            agent_id=uuid.uuid4(),
            previous_level=IsolationLevel.L4_HARD,
            target_level=IsolationLevel.L2_COLLAB,
            trigger_reason="joint_task_assigned",
        )
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
