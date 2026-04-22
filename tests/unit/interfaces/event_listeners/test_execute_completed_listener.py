"""Tests for ExecuteCompletedListener."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.events.execute_events import Executed
from src.interfaces.event_listeners.execute_completed_listener import ExecuteCompletedListener


class TestExecuteCompletedListener:
    """TDD tests for ExecuteCompletedListener."""

    @pytest.fixture
    def mock_publisher(self) -> MagicMock:
        """Create a mock event publisher with async publish."""
        publisher = MagicMock()
        publisher.publish = AsyncMock()
        return publisher

    @pytest.mark.asyncio
    async def test_on_executed_publishes_tool_executed(self, mock_publisher: MagicMock) -> None:
        """RED: on_executed should publish ToolExecuted for business_event_type=ToolExecuted."""
        listener = ExecuteCompletedListener(publisher=mock_publisher)
        event = Executed(
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
        listener = ExecuteCompletedListener(publisher=mock_publisher)
        event = Executed(
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
        listener = ExecuteCompletedListener(publisher=mock_publisher)
        event = Executed(
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
        listener = ExecuteCompletedListener(publisher=mock_publisher)
        event = Executed(
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
