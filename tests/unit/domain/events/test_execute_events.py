"""Tests for Executed domain event."""

import uuid

from src.domain.events.execute_events import Executed


class TestExecutedEvent:
    """TDD tests for Executed domain event."""

    def test_create_executed_event_with_required_fields(self) -> None:
        """RED: Executed event should be creatable with session_id."""
        session_id = "test-session-123"
        event = Executed(session_id=session_id)

        assert event.session_id == session_id
        assert event.event_type == "Executed"
        assert event.event_id is not None
        assert isinstance(event.event_id, uuid.UUID)

    def test_executed_event_has_business_event_type(self) -> None:
        """RED: Executed event should have business_event_type field."""
        event = Executed(
            session_id="test-session",
            business_event_type="ToolExecuted",
        )

        assert event.business_event_type == "ToolExecuted"

    def test_executed_event_carries_task_context(self) -> None:
        """RED: Executed event should carry task_context dict."""
        task_context = {"task_id": "task-1", "code": "print('hello')", "priority": "high"}
        event = Executed(
            session_id="test-session",
            task_context=task_context,
        )

        assert event.task_context == task_context
        assert event.task_context["task_id"] == "task-1"

    def test_executed_event_carries_execution_result(self) -> None:
        """RED: Executed event should carry execution_result dict."""
        result = {"status": "completed", "output": "hello world", "error": None}
        event = Executed(
            session_id="test-session",
            execution_result=result,
        )

        assert event.execution_result == result
        assert event.execution_result["status"] == "completed"

    def test_executed_event_tracks_cost_and_latency(self) -> None:
        """RED: Executed event should track cost_estimate and latency_ms."""
        event = Executed(
            session_id="test-session",
            cost_estimate=0.05,
            latency_ms=150.5,
        )

        assert event.cost_estimate == 0.05
        assert event.latency_ms == 150.5

    def test_executed_event_carries_route_info(self) -> None:
        """RED: Executed event should carry route_target and route_score."""
        event = Executed(
            session_id="test-session",
            route_target="ceo-agent",
            route_score=0.95,
        )

        assert event.route_target == "ceo-agent"
        assert event.route_score == 0.95

    def test_executed_event_serialization(self) -> None:
        """RED: Executed event should serialize to dict correctly."""
        event = Executed(
            session_id="test-session",
            task_context={"task": "test"},
            execution_result={"status": "ok"},
            cost_estimate=0.01,
            latency_ms=50.0,
            business_event_type="ToolExecuted",
            route_target="tool-1",
            route_score=0.9,
        )

        data = event.to_dict()

        assert data["event_type"] == "Executed"
        assert data["payload"]["session_id"] == "test-session"
        assert data["payload"]["business_event_type"] == "ToolExecuted"
        assert data["payload"]["route_target"] == "tool-1"
