"""Tests for TriggerContext value object."""

from __future__ import annotations

import pytest

from src.domain.value_objects.trigger_context import TriggerContext


class TestTriggerContextCreation:
    """Test TriggerContext factory methods."""

    def test_from_domain_event_basic(self) -> None:
        """Verify basic domain event context extraction."""
        payload = {"session_id": "session-123", "agent_id": "agent-456", "task_type": "doc_processing"}
        context = TriggerContext.from_domain_event(
            event_type="DocumentProcessed",
            payload=payload,
            event_id="evt-001",
        )

        assert context.session_id == "session-123"
        assert context.trigger_type == "domain_event"
        assert context.agent_id == "agent-456"
        assert context.task_context["task_type"] == "doc_processing"
        assert context.source_event_type == "DocumentProcessed"
        assert context.source_event_id == "evt-001"

    def test_from_domain_event_nested_payload(self) -> None:
        """Verify nested payload extraction for session_id."""
        payload = {"payload": {"session_id": "nested-session", "priority": "high"}}
        context = TriggerContext.from_domain_event(
            event_type="ToolExecuted",
            payload=payload,
        )

        assert context.session_id == "nested-session"

    def test_from_domain_event_default_session(self) -> None:
        """Verify default session when none provided."""
        payload = {"tool_name": "web_search"}
        context = TriggerContext.from_domain_event(
            event_type="ToolExecuted",
            payload=payload,
        )

        assert context.session_id == "default"

    def test_from_heartbeat_basic(self) -> None:
        """Verify heartbeat context extraction."""
        context = TriggerContext.from_heartbeat(
            heartbeat_id="hb-001",
            wake_reason="scheduled",
            todo_items=("task1", "task2"),
            cost_budget=50.0,
        )

        assert context.session_id == "heartbeat-scheduler"
        assert context.trigger_type == "heartbeat"
        assert context.task_context["heartbeat_id"] == "hb-001"
        assert context.task_context["wake_reason"] == "scheduled"
        assert context.task_context["todo_items"] == ["task1", "task2"]
        assert context.task_context["cost_budget"] == 50.0
        assert context.source_event_type == "HeartbeatTriggered"

    def test_from_heartbeat_empty_todo_items(self) -> None:
        """Verify heartbeat with no todo items."""
        context = TriggerContext.from_heartbeat(
            heartbeat_id="hb-002",
            wake_reason="user_request",
        )

        assert context.task_context["todo_items"] == []
        assert context.task_context["cost_budget"] == 0.0


class TestTriggerContextTaskFields:
    """Test task context field extraction from domain events."""

    @pytest.mark.parametrize(
        "event_type,payload_keys,expected_fields",
        [
            (
                "DocumentProcessed",
                {"session_id": "s1", "task_type": "ocr", "priority": "high", "document_id": "doc1"},
                ["task_type", "priority"],
            ),
            (
                "ToolExecuted",
                {"session_id": "s2", "tool_name": "web_search", "priority": "low"},
                ["tool_name"],
            ),
            (
                "CheckpointReached",
                {"session_id": "s3", "checkpoint_id": "cp-001", "priority": "medium"},
                ["checkpoint_id"],
            ),
        ],
    )
    def test_task_context_extraction(
        self,
        event_type: str,
        payload_keys: dict[str, str],
        expected_fields: list[str],
    ) -> None:
        """Verify correct fields are extracted to task_context."""
        context = TriggerContext.from_domain_event(event_type=event_type, payload=payload_keys)

        for field in expected_fields:
            assert field in context.task_context, f"Expected {field} in task_context for {event_type}"
