"""Tests for AutoRouteHandler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.domain.events.auto_route_events import AutoRouted
from src.domain.events.auto_trigger_events import AutoTriggered


class TestAutoRouteHandlerInit:
    """Test AutoRouteHandler initialization."""

    def test_init_with_service(self) -> None:
        """Coverage: __init__ with service dependency."""
        from src.application.event_handlers.auto_route_handler import AutoRouteHandler

        mock_service = MagicMock()
        handler = AutoRouteHandler(auto_route_service=mock_service)
        assert handler._auto_route_service is mock_service


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
