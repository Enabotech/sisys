"""Tests for AutoExecuteCompletedListener."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.events.auto_execute_events import AutoExecuted
from src.interfaces.event_listeners.auto_execute_completed_listener import AutoExecuteCompletedListener


class TestAutoExecuteCompletedListener:
    """TDD tests for AutoExecuteCompletedListener."""

    @pytest.fixture
    def mock_publisher(self) -> MagicMock:
        """Create a mock event publisher with async publish."""
        publisher = MagicMock()
        publisher.publish = AsyncMock()
        return publisher

    @pytest.mark.asyncio
    async def test_on_executed_publishes_tool_executed(self, mock_publisher: MagicMock) -> None:
        """RED: on_executed should publish ToolExecuted for business_event_type=ToolExecuted."""
        listener = AutoExecuteCompletedListener(publisher=mock_publisher)
        event = AutoExecuted(
            session_id="test-session",
            business_event_type="ToolExecuted",
            task_context={"tool_id": "pestel"},
            execution_result={"status": "completed"},
        )

        await listener.on_executed(event)

        mock_publisher.publish.assert_called_once()
        call_args = mock_publisher.publish.call_args
        published_event = call_args[0][0]
        assert published_event.event_type == "ToolExecuted"

    @pytest.mark.asyncio
    async def test_on_executed_publishes_document_processed(self, mock_publisher: MagicMock) -> None:
        """RED: on_executed should publish DocumentProcessed for business_event_type=DocumentProcessed."""
        listener = AutoExecuteCompletedListener(publisher=mock_publisher)
        event = AutoExecuted(
            session_id="test-session",
            business_event_type="DocumentProcessed",
            task_context={"document_id": "doc-123"},
            execution_result={"status": "completed"},
        )

        await listener.on_executed(event)

        mock_publisher.publish.assert_called_once()
        call_args = mock_publisher.publish.call_args
        published_event = call_args[0][0]
        assert published_event.event_type == "DocumentProcessed"

    @pytest.mark.asyncio
    async def test_on_executed_publishes_agent_decided(self, mock_publisher: MagicMock) -> None:
        """RED: on_executed should publish AgentDecided for business_event_type=AgentDecided."""
        listener = AutoExecuteCompletedListener(publisher=mock_publisher)
        event = AutoExecuted(
            session_id="test-session",
            business_event_type="AgentDecided",
            task_context={"agent_id": "ceo-agent"},
            execution_result={"status": "completed"},
        )

        await listener.on_executed(event)

        mock_publisher.publish.assert_called_once()
        call_args = mock_publisher.publish.call_args
        published_event = call_args[0][0]
        assert published_event.event_type == "AgentDecided"

    @pytest.mark.asyncio
    async def test_on_executed_defaults_to_tool_executed(self, mock_publisher: MagicMock) -> None:
        """RED: on_executed should default to ToolExecuted for unknown business_event_type."""
        listener = AutoExecuteCompletedListener(publisher=mock_publisher)
        event = AutoExecuted(
            session_id="test-session",
            business_event_type="",  # Empty defaults to ToolExecuted
            task_context={},
            execution_result={"status": "completed"},
        )

        await listener.on_executed(event)

        mock_publisher.publish.assert_called_once()
        call_args = mock_publisher.publish.call_args
        published_event = call_args[0][0]
        assert published_event.event_type == "ToolExecuted"

    @pytest.mark.asyncio
    async def test_on_executed_with_unknown_type_logs_warning(self) -> None:
        """Coverage: unknown business_event_type logs warning and defaults (lines 68-69)."""
        mock_publisher = MagicMock()
        mock_publisher.publish = AsyncMock()
        listener = AutoExecuteCompletedListener(publisher=mock_publisher)

        event = AutoExecuted(
            session_id="test-session",
            business_event_type="UnknownType",
            task_context={},
            execution_result={"status": "completed"},
        )

        # Should not raise, just log warning and default to ToolExecuted
        await listener.on_executed(event)

        mock_publisher.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_without_publisher_logs_warning(self) -> None:
        """Coverage: _publish without publisher logs warning (lines 117-118)."""
        listener = AutoExecuteCompletedListener(publisher=None)

        # Create a minimal domain event for testing
        from src.domain.events.base import DomainEvent

        class TestEvent(DomainEvent):
            event_type = "test.event"

        event = TestEvent()

        # Should not raise, just log warning
        await listener._publish(event, "test:channel")

    @pytest.mark.asyncio
    async def test_publish_handles_exception(self, mock_publisher: MagicMock) -> None:
        """Coverage: _publish exception handler (lines 123-125)."""
        mock_publisher.publish = AsyncMock(side_effect=Exception("publish failed"))
        listener = AutoExecuteCompletedListener(publisher=mock_publisher)

        from src.domain.events.base import DomainEvent

        class TestEvent(DomainEvent):
            event_type = "test.event"

        event = TestEvent()

        with pytest.raises(Exception) as exc_info:
            await listener._publish(event, "test:channel")

        assert "publish failed" in str(exc_info.value)
