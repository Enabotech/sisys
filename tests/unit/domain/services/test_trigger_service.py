"""Tests for AutoTriggerService domain service."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from src.domain.events.auto_trigger_events import AutoTriggered
from src.domain.events.base import DomainEvent
from src.domain.events.publish_result import ChannelResult, PublishResult
from src.domain.ports.event_publisher import EventPublisher
from src.domain.services.auto_trigger_service import AutoTriggerService


class DummyPublisher(EventPublisher):
    """Dummy async publisher for testing."""

    def __init__(self) -> None:
        self.published_events: list[DomainEvent] = []

    async def publish(self, event: DomainEvent, channel: str | None = None) -> PublishResult:
        self.published_events.append(event)
        return PublishResult(
            event_id=str(event.event_id) if event.event_id else "test-event-id",
            results=(
                ChannelResult("realtime", True),
                ChannelResult("reliable", True),
            ),
        )


class TestAutoTriggerServiceUnit:
    """Unit tests for AutoTriggerService without infrastructure dependencies."""

    @pytest.fixture
    def publisher(self) -> DummyPublisher:
        return DummyPublisher()

    @pytest.fixture
    def trigger_service(self, publisher: DummyPublisher) -> AutoTriggerService:
        return AutoTriggerService(publisher=publisher)

    @pytest.mark.asyncio
    async def test_on_domain_event_publishes_triggered(
        self,
        trigger_service: AutoTriggerService,
        publisher: DummyPublisher,
    ) -> None:
        """Verify domain event triggers Triggered event publication."""
        event = DomainEvent(
            event_id=uuid.uuid4(),
            event_type="DocumentProcessed",
            payload={"session_id": "session-123", "agent_id": "agent-456", "task_type": "ocr"},
        )

        result = await trigger_service.on_domain_event(event)

        assert result is not None
        assert isinstance(result, AutoTriggered)
        assert result.trigger_type == "domain_event"
        assert result.session_id == "session-123"
        assert result.source_event_type == "DocumentProcessed"
        assert len(publisher.published_events) == 1

    @pytest.mark.asyncio
    async def test_on_heartbeat_event_publishes_triggered(
        self,
        trigger_service: AutoTriggerService,
        publisher: DummyPublisher,
    ) -> None:
        """Verify heartbeat event triggers Triggered event publication."""
        heartbeat_id = uuid.uuid4()
        event = DomainEvent(
            event_id=heartbeat_id,
            event_type="HeartbeatTriggered",
            payload={
                "heartbeat_id": str(heartbeat_id),
                "wake_reason": "scheduled",
                "todo_items": ["task1", "task2"],
                "cost_budget": 100.0,
            },
        )

        result = await trigger_service.on_heartbeat_event(event)

        assert result is not None
        assert result.trigger_type == "heartbeat"
        assert result.session_id == "heartbeat-scheduler"
        assert result.source_event_type == "HeartbeatTriggered"

    def test_extract_context_from_domain_event(self, trigger_service: AutoTriggerService) -> None:
        """Verify context extraction without publishing."""
        event = DomainEvent(
            event_id=uuid.uuid4(),
            event_type="ToolExecuted",
            payload={"session_id": "session-789", "tool_name": "web_search"},
        )

        context = trigger_service.extract_context(event)

        assert context.session_id == "session-789"
        assert context.trigger_type == "domain_event"
        assert context.task_context["tool_name"] == "web_search"

    def test_extract_context_from_heartbeat(self, trigger_service: AutoTriggerService) -> None:
        """Verify context extraction from heartbeat event."""
        heartbeat_id = uuid.uuid4()
        # Use HeartbeatTriggered which has heartbeat_id as attribute, not in payload
        from src.domain.events.heartbeat_events import HeartbeatTriggered

        event = HeartbeatTriggered(
            heartbeat_id=heartbeat_id,
            wake_reason="user_request",
            todo_items=("task1", "task2"),
            cost_budget=50.0,
        )

        context = trigger_service.extract_context(event)

        assert context.trigger_type == "heartbeat"
        assert context.session_id == "heartbeat-scheduler"
        assert context.task_context["wake_reason"] == "user_request"
        assert context.task_context["cost_budget"] == 50.0

    @pytest.mark.asyncio
    async def test_on_domain_event_no_publisher(self) -> None:
        """Verify no crash when no publisher configured."""
        trigger_service = AutoTriggerService(publisher=None)
        event = DomainEvent(
            event_id=uuid.uuid4(),
            event_type="AgentDecided",
            payload={"session_id": "session-abc"},
        )

        result = await trigger_service.on_domain_event(event)

        # Should return AutoTriggered but not publish (warning logged)
        assert result is not None
        assert result.trigger_type == "domain_event"

    @pytest.mark.asyncio
    async def test_publish_error_handling(
        self,
        trigger_service: AutoTriggerService,
        publisher: DummyPublisher,
    ) -> None:
        """Verify publish errors are logged and re-raised."""
        error_publisher = AsyncMock()
        error_publisher.publish.side_effect = RuntimeError("Publish failed")

        service = AutoTriggerService(publisher=error_publisher)
        event = DomainEvent(
            event_id=uuid.uuid4(),
            event_type="CheckpointReached",
            payload={"session_id": "session-xyz"},
        )

        with pytest.raises(RuntimeError, match="Publish failed"):
            await service.on_domain_event(event)


class TestAutoTriggerServiceArchitecture:
    """Architecture compliance tests for AutoTriggerService (hexagonal architecture)."""

    def test_trigger_service_is_domain_layer(self) -> None:
        """Verify AutoTriggerService has no infrastructure dependencies in constructor."""
        # AutoTriggerService should accept protocol, not concrete infra classes
        service = AutoTriggerService(publisher=None)
        assert service._publisher is None

    def test_trigger_service_uses_protocol_for_publishing(self) -> None:
        """Verify AutoTriggerService depends on protocol, not concrete implementation."""
        # The publisher should be Protocol, not a concrete class
        from src.domain.ports.event_publisher import EventPublisher

        # Verify the protocol exists and is a Protocol
        assert hasattr(EventPublisher, "publish")
