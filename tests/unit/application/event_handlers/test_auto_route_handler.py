"""Tests for AutoRouteHandler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.domain.events.auto_route_events import AutoRouted
from src.domain.events.auto_trigger_events import AutoTriggered
from src.domain.events.base import DomainEvent


class TestAutoRouteHandlerInit:
    """Test AutoRouteHandler initialization."""

    def test_init_with_all_dependencies(self) -> None:
        """Coverage: __init__ with all dependencies."""
        from src.application.event_handlers.auto_route_handler import AutoRouteHandler

        mock_service = MagicMock()
        mock_publisher = MagicMock()

        handler = AutoRouteHandler(
            auto_route_service=mock_service,
            publisher=mock_publisher,
        )

        assert handler._auto_route_service is mock_service
        assert handler._publisher is mock_publisher

    def test_init_with_no_publisher(self) -> None:
        """Coverage: __init__ with publisher=None."""
        from src.application.event_handlers.auto_route_handler import AutoRouteHandler

        mock_service = MagicMock()

        handler = AutoRouteHandler(
            auto_route_service=mock_service,
            publisher=None,
        )

        assert handler._publisher is None


class MockEventPublisher:
    """Mock event publisher for testing."""

    def __init__(self) -> None:
        self.published_events: list = []

    async def publish(self, event: DomainEvent, channel: str | None = None) -> None:
        self.published_events.append(event)


class TestAutoRouteHandlerOnTriggered:
    """Test on_triggered method."""

    @pytest.mark.asyncio
    async def test_on_triggered_with_non_auto_triggered_event(self) -> None:
        """Coverage: Returns None for non-AutoTriggered event."""
        from src.application.event_handlers.auto_route_handler import AutoRouteHandler

        mock_service = MagicMock()
        handler = AutoRouteHandler(auto_route_service=mock_service)

        mock_event = MagicMock()  # Not AutoTriggered
        result = await handler.on_triggered(mock_event)

        assert result is None

    @pytest.mark.asyncio
    async def test_on_triggered_returns_none_when_service_returns_none(self) -> None:
        """Coverage: Returns None when AutoRouteService returns None."""
        from src.application.event_handlers.auto_route_handler import AutoRouteHandler

        mock_service = MagicMock()
        mock_service.on_triggered_event = AsyncMock(return_value=None)
        handler = AutoRouteHandler(auto_route_service=mock_service)

        event = AutoTriggered(
            event_id=uuid4(),
            trigger_type="domain_event",
            session_id="test-session",
            task_context={"task": "test"},
        )

        result = await handler.on_triggered(event)

        assert result is None

    @pytest.mark.asyncio
    async def test_on_triggered_with_auto_triggered_event(self) -> None:
        """Coverage: Processes AutoTriggered event and returns AutoRouted."""
        from src.application.event_handlers.auto_route_handler import AutoRouteHandler

        mock_service = MagicMock()
        routed_event = AutoRouted(
            event_id=uuid4(),
            route_type="hash",
            session_id="test-session",
            task_context={"task": "test"},
            route_target="agent-1",
            route_score=1.0,
            trigger_event_type="AutoTriggered",
        )
        mock_service.on_triggered_event = AsyncMock(return_value=routed_event)
        handler = AutoRouteHandler(auto_route_service=mock_service)

        event = AutoTriggered(
            event_id=uuid4(),
            trigger_type="domain_event",
            session_id="test-session",
            task_context={"task": "test"},
        )

        result = await handler.on_triggered(event)

        assert result is routed_event
        mock_service.on_triggered_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_triggered_logs_warning_when_service_returns_none(self) -> None:
        """Coverage: Logs warning when AutoRouteService returns None."""
        from src.application.event_handlers.auto_route_handler import AutoRouteHandler

        mock_service = MagicMock()
        mock_service.on_triggered_event = AsyncMock(return_value=None)
        handler = AutoRouteHandler(auto_route_service=mock_service)

        event = AutoTriggered(
            event_id=uuid4(),
            trigger_type="domain_event",
            session_id="test-session",
            task_context={"task": "test"},
        )

        result = await handler.on_triggered(event)

        assert result is None

    @pytest.mark.asyncio
    async def test_on_triggered_raises_exception_on_service_error(self) -> None:
        """Coverage: Raises exception when AutoRouteService fails."""
        from src.application.event_handlers.auto_route_handler import AutoRouteHandler

        mock_service = MagicMock()
        mock_service.on_triggered_event = AsyncMock(side_effect=Exception("Service error"))
        handler = AutoRouteHandler(auto_route_service=mock_service)

        event = AutoTriggered(
            event_id=uuid4(),
            trigger_type="domain_event",
            session_id="test-session",
            task_context={"task": "test"},
        )

        with pytest.raises(Exception, match="Service error"):
            await handler.on_triggered(event)


class TestAutoRouteHandlerPublish:
    """Test _publish method."""

    @pytest.mark.asyncio
    async def test_publish_without_publisher(self) -> None:
        """Coverage: _publish does nothing when publisher is None."""
        from src.application.event_handlers.auto_route_handler import AutoRouteHandler

        mock_service = MagicMock()
        handler = AutoRouteHandler(auto_route_service=mock_service, publisher=None)

        event = AutoRouted(
            event_id=uuid4(),
            route_type="hash",
            session_id="test-session",
            task_context={},
            route_target="agent-1",
            route_score=1.0,
        )

        # Should not raise
        await handler._publish(event)

    @pytest.mark.asyncio
    async def test_publish_with_publisher(self) -> None:
        """Coverage: _publish publishes event via publisher."""
        from src.application.event_handlers.auto_route_handler import AutoRouteHandler

        mock_service = MagicMock()
        mock_publisher = AsyncMock()
        handler = AutoRouteHandler(auto_route_service=mock_service, publisher=mock_publisher)

        event = AutoRouted(
            event_id=uuid4(),
            route_type="hash",
            session_id="test-session",
            task_context={},
            route_target="agent-1",
            route_score=1.0,
        )

        await handler._publish(event, channel="rt:AutoRouted")

        mock_publisher.publish.assert_called_once_with(event, channel="rt:AutoRouted")

    @pytest.mark.asyncio
    async def test_publish_with_default_channel(self) -> None:
        """Coverage: _publish uses default channel."""
        from src.application.event_handlers.auto_route_handler import AutoRouteHandler

        mock_service = MagicMock()
        mock_publisher = AsyncMock()
        handler = AutoRouteHandler(auto_route_service=mock_service, publisher=mock_publisher)

        event = AutoRouted(
            event_id=uuid4(),
            route_type="semantic",
            session_id="test-session",
            task_context={},
            route_target="agent-2",
            route_score=0.95,
        )

        await handler._publish(event)

        mock_publisher.publish.assert_called_once_with(event, channel="rt:AutoRouted")

    @pytest.mark.asyncio
    async def test_publish_raises_on_publisher_error(self) -> None:
        """Coverage: _publish raises exception when publisher fails."""
        from src.application.event_handlers.auto_route_handler import AutoRouteHandler

        mock_service = MagicMock()
        mock_publisher = MagicMock()
        mock_publisher.publish = AsyncMock(side_effect=Exception("Publish failed"))
        handler = AutoRouteHandler(auto_route_service=mock_service, publisher=mock_publisher)

        event = AutoRouted(
            event_id=uuid4(),
            route_type="mixed",
            session_id="test-session",
            task_context={},
            route_target="agent-3",
            route_score=0.9,
        )

        with pytest.raises(Exception, match="Publish failed"):
            await handler._publish(event)
