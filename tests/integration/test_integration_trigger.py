"""Integration tests for trigger mechanism end-to-end flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.domain.events.auto_trigger_events import AutoTriggered
from src.domain.events.base import DomainEvent
from src.domain.events.heartbeat_events import HeartbeatTriggered
from src.domain.services.auto_trigger_service import AutoTriggerService
from src.domain.value_objects.auto_trigger_context import AutoTriggerContext
from src.infrastructure.config.redis import RedisConfig
from src.infrastructure.scheduler.heartbeat_scheduler import HeartbeatScheduler


class TestTriggerIntegration:
    """End-to-end integration tests for trigger mechanism."""

    @pytest.fixture
    def mock_publisher(self) -> AsyncMock:
        """Create mock event publisher."""
        return AsyncMock()

    @pytest.fixture
    def trigger_service(self, mock_publisher: AsyncMock) -> AutoTriggerService:
        """Create AutoTriggerService with mock publisher."""
        return AutoTriggerService(publisher=mock_publisher)

    @pytest.mark.asyncio
    async def test_domain_event_to_triggered_flow(
        self,
        trigger_service: AutoTriggerService,
        mock_publisher: AsyncMock,
    ) -> None:
        """Verify domain event flows through AutoTriggerService to AutoTriggered event."""
        # Create a domain event
        domain_event = DomainEvent(
            event_type="DocumentProcessed",
            payload={
                "session_id": "session-integration-test",
                "agent_id": "agent-001",
                "task_type": "document_ocr",
                "priority": "high",
            },
        )

        # Process through trigger service
        triggered = await trigger_service.on_domain_event(domain_event)

        # Verify AutoTriggered event was created and published
        assert triggered is not None
        assert isinstance(triggered, AutoTriggered)
        assert triggered.trigger_type == "domain_event"
        assert triggered.session_id == "session-integration-test"
        assert triggered.source_event_type == "DocumentProcessed"

        # Verify published to mock
        mock_publisher.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_heartbeat_to_triggered_flow(
        self,
        trigger_service: AutoTriggerService,
        mock_publisher: AsyncMock,
    ) -> None:
        """Verify heartbeat event flows through AutoTriggerService to AutoTriggered event."""
        import uuid

        # Create heartbeat event
        heartbeat_event = HeartbeatTriggered(
            heartbeat_id=uuid.uuid4(),
            wake_reason="scheduled",
            todo_items=("task1", "task2"),
            cost_budget=100.0,
        )

        # Process through trigger service
        triggered = await trigger_service.on_heartbeat_event(heartbeat_event)

        # Verify AutoTriggered event was created
        assert triggered is not None
        assert isinstance(triggered, AutoTriggered)
        assert triggered.trigger_type == "heartbeat"
        assert triggered.session_id == "heartbeat-scheduler"

        # Verify published to mock
        mock_publisher.publish.assert_called_once()

    def test_trigger_context_extraction_from_domain_event(self) -> None:
        """Verify AutoTriggerContext correctly extracts from domain event payload."""
        payload = {
            "session_id": "session-123",
            "agent_id": "agent-456",
            "task_type": "tool_execution",
            "priority": "medium",
            "tool_name": "web_search",
        }

        context = AutoTriggerContext.from_domain_event(
            event_type="ToolExecuted",
            payload=payload,
            event_id="test-event-id",
        )

        assert context.session_id == "session-123"
        assert context.agent_id == "agent-456"
        assert context.trigger_type == "domain_event"
        assert context.task_context["task_type"] == "tool_execution"
        assert context.task_context["priority"] == "medium"
        assert context.task_context["tool_name"] == "web_search"

    def test_trigger_context_extraction_from_heartbeat(self) -> None:
        """Verify AutoTriggerContext correctly extracts from heartbeat event."""
        context = AutoTriggerContext.from_heartbeat(
            heartbeat_id="hb-123",
            wake_reason="user_request",
            todo_items=("task_a", "task_b", "task_c"),
            cost_budget=250.0,
        )

        assert context.session_id == "heartbeat-scheduler"
        assert context.trigger_type == "heartbeat"
        assert context.task_context["heartbeat_id"] == "hb-123"
        assert context.task_context["wake_reason"] == "user_request"
        assert context.task_context["todo_items"] == ["task_a", "task_b", "task_c"]
        assert context.task_context["cost_budget"] == 250.0

    @pytest.mark.asyncio
    async def test_heartbeat_scheduler_lifecycle(self) -> None:
        """Verify HeartbeatScheduler start/stop lifecycle."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(
            redis_config=config,
            interval_seconds=60,
            publisher=None,  # No publisher for this test
        )

        # Start scheduler
        await scheduler.start()
        assert scheduler._running is True

        # Stop scheduler
        await scheduler.stop()
        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_triggered_event_serialization_roundtrip(self) -> None:
        """Verify AutoTriggered event can serialize and deserialize correctly."""
        import uuid

        original = AutoTriggered(
            trigger_type="domain_event",
            session_id="session-roundtrip-test",
            agent_id="agent-789",
            task_context={
                "task_type": "checkpoint_reached",
                "checkpoint_id": "cp-001",
                "priority": "high",
            },
            source_event_type="CheckpointReached",
            source_event_id=str(uuid.uuid4()),
        )

        # Serialize
        serialized = original.to_dict()
        assert serialized["event_type"] == "AutoTriggered"
        assert serialized["payload"]["trigger_type"] == "domain_event"
        assert serialized["payload"]["session_id"] == "session-roundtrip-test"

        # Deserialize
        restored = AutoTriggered.from_dict(serialized)
        assert restored.event_type == "AutoTriggered"
        assert getattr(restored, "trigger_type") == "domain_event"
        assert getattr(restored, "session_id") == "session-roundtrip-test"
        assert getattr(restored, "agent_id") == "agent-789"
        assert getattr(restored, "task_context")["task_type"] == "checkpoint_reached"
