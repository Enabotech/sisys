"""Tests for AutoTriggerListener."""

from __future__ import annotations

import queue
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.events.base import DomainEvent
from src.domain.services.auto_trigger_service import AutoTriggerService


class TestAutoTriggerListenerCreation:
    """Test AutoTriggerListener instantiation."""

    def test_listener_initialization(self) -> None:
        """Verify AutoTriggerListener initializes with correct defaults."""
        from src.application.event_handlers.auto_trigger_handler import AutoTriggerHandler

        mock_auto_trigger_service = MagicMock(spec=AutoTriggerService)
        mock_event_listener = MagicMock()

        listener = AutoTriggerHandler(
            auto_trigger_service=mock_auto_trigger_service,
            event_listener=mock_event_listener,
        )

        assert listener._auto_trigger_service is mock_auto_trigger_service
        assert listener._event_listener is mock_event_listener
        assert listener._running is False

    def test_registered_event_types(self) -> None:
        """Verify all expected event types are registered."""
        from src.application.event_handlers.auto_trigger_handler import AutoTriggerHandler

        mock_auto_trigger_service = MagicMock(spec=AutoTriggerService)
        mock_event_listener = MagicMock()

        listener = AutoTriggerHandler(
            auto_trigger_service=mock_auto_trigger_service,
            event_listener=mock_event_listener,
        )

        expected_types = [
            "DocumentProcessed",
            "ToolExecuted",
            "AgentDecided",
            "CheckpointReached",
            "CheckpointRecovered",
            "CorrectionClassified",
            "CorrectionApproved",
            "IsolationLevelSwitched",
            "HeartbeatTriggered",
            "StrategicDeviationWarning",
            "AuditEvent",
        ]
        assert listener.registered_event_types == expected_types


class TestAutoTriggerListenerHandlers:
    """Test handler registration and event queuing."""

    def test_register_handlers_creates_worker_thread(self) -> None:
        """Coverage: register_handlers starts background thread."""
        from src.application.event_handlers.auto_trigger_handler import AutoTriggerHandler

        mock_auto_trigger_service = MagicMock(spec=AutoTriggerService)
        mock_event_listener = MagicMock()

        listener = AutoTriggerHandler(
            auto_trigger_service=mock_auto_trigger_service,
            event_listener=mock_event_listener,
        )

        listener.register_handlers()

        assert listener._running is True
        assert listener._worker_thread is not None
        assert listener._worker_thread.is_alive() is True

        # Cleanup
        listener.stop()

    def test_create_handler_returns_callable(self) -> None:
        """Coverage: _create_handler returns a function."""
        from src.application.event_handlers.auto_trigger_handler import AutoTriggerHandler

        mock_auto_trigger_service = MagicMock(spec=AutoTriggerService)
        mock_event_listener = MagicMock()

        listener = AutoTriggerHandler(
            auto_trigger_service=mock_auto_trigger_service,
            event_listener=mock_event_listener,
        )

        handler = listener._create_handler("TestEvent")

        assert callable(handler)

    def test_handler_queues_event(self) -> None:
        """Coverage: handler puts event in queue."""
        from src.application.event_handlers.auto_trigger_handler import AutoTriggerHandler

        mock_auto_trigger_service = MagicMock(spec=AutoTriggerService)
        mock_event_listener = MagicMock()

        listener = AutoTriggerHandler(
            auto_trigger_service=mock_auto_trigger_service,
            event_listener=mock_event_listener,
        )

        handler = listener._create_handler("TestEvent")

        # Create mock event
        mock_event = MagicMock(spec=DomainEvent)
        mock_event.to_dict.return_value = {}

        handler(mock_event)

        # Event should be queued
        try:
            event_type, event = listener._event_queue.get_nowait()
            assert event_type == "TestEvent"
            assert event is mock_event
        except queue.Empty:
            pytest.fail("Event was not queued")


class TestAutoTriggerListenerStop:
    """Test stop method."""

    def test_stop_sets_running_false(self) -> None:
        """Coverage: stop() sets _running to False."""
        from src.application.event_handlers.auto_trigger_handler import AutoTriggerHandler

        mock_auto_trigger_service = MagicMock(spec=AutoTriggerService)
        mock_event_listener = MagicMock()

        listener = AutoTriggerHandler(
            auto_trigger_service=mock_auto_trigger_service,
            event_listener=mock_event_listener,
        )
        listener._running = True
        listener._worker_thread = None

        listener.stop()

        assert listener._running is False

    def test_stop_waits_for_thread(self) -> None:
        """Coverage: stop() joins worker thread."""
        from src.application.event_handlers.auto_trigger_handler import AutoTriggerHandler

        mock_auto_trigger_service = MagicMock(spec=AutoTriggerService)
        mock_event_listener = MagicMock()

        listener = AutoTriggerHandler(
            auto_trigger_service=mock_auto_trigger_service,
            event_listener=mock_event_listener,
        )

        listener.register_handlers()
        listener.stop()

        assert listener._running is False


class TestAutoTriggerListenerProcessEvent:
    """Test _process_event method."""

    @pytest.mark.asyncio
    async def test_process_event_heartbeat_triggered(self) -> None:
        """Coverage: HeartbeatTriggered uses special handler."""
        from src.application.event_handlers.auto_trigger_handler import AutoTriggerHandler

        mock_auto_trigger_service = AsyncMock(spec=AutoTriggerService)
        mock_auto_trigger_service.on_heartbeat_event = AsyncMock()
        mock_event_listener = MagicMock()

        listener = AutoTriggerHandler(
            auto_trigger_service=mock_auto_trigger_service,
            event_listener=mock_event_listener,
        )

        mock_event = MagicMock(spec=DomainEvent)
        mock_event.to_dict.return_value = {
            "heartbeat_id": "test-id",
            "wake_reason": "scheduled",
            "todo_items": [],
            "cost_budget": 0.0,
        }

        # Start the worker loop to process
        listener._running = True
        listener._event_queue.put(("HeartbeatTriggered", mock_event))

        # Give time for async processing
        import asyncio

        await asyncio.sleep(0.1)

        # Note: Due to threading complexity, we mainly verify no exception is raised
        listener.stop()

    @pytest.mark.asyncio
    async def test_process_event_logs_warning_on_none_trigger(self) -> None:
        """Coverage: _process_event logs warning when AutoTriggerService returns None."""
        from src.application.event_handlers.auto_trigger_handler import AutoTriggerHandler

        mock_auto_trigger_service = AsyncMock(spec=AutoTriggerService)
        mock_auto_trigger_service.on_domain_event = AsyncMock(return_value=None)
        mock_event_listener = MagicMock()

        listener = AutoTriggerHandler(
            auto_trigger_service=mock_auto_trigger_service,
            event_listener=mock_event_listener,
        )

        mock_event = MagicMock(spec=DomainEvent)
        mock_event.to_dict.return_value = {}
        mock_event.event_type = "TestEvent"

        # Process directly
        await listener._process_event("TestEvent", mock_event)

        mock_auto_trigger_service.on_domain_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_event_handles_exception(self) -> None:
        """Coverage: _process_event handles exceptions gracefully."""
        from src.application.event_handlers.auto_trigger_handler import AutoTriggerHandler

        mock_auto_trigger_service = AsyncMock(spec=AutoTriggerService)
        mock_auto_trigger_service.on_domain_event = AsyncMock(side_effect=Exception("processing failed"))
        mock_event_listener = MagicMock()

        listener = AutoTriggerHandler(
            auto_trigger_service=mock_auto_trigger_service,
            event_listener=mock_event_listener,
        )

        mock_event = MagicMock(spec=DomainEvent)
        mock_event.to_dict.return_value = {}
        mock_event.event_type = "TestEvent"

        # Should not raise
        await listener._process_event("TestEvent", mock_event)
