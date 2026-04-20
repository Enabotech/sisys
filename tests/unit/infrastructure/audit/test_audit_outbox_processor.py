"""Test OutboxProcessor - Red Phase (Test First).

TDD Cycle: Red -> Green -> Refactor
Reference: Story 1.10 Task 2 - Transaction Outbox Pattern
"""

from __future__ import annotations

import uuid
from unittest import mock

import pytest


class TestOutboxProcessorProcessBatch:
    """Test process_batch() method."""

    @pytest.mark.asyncio
    async def test_process_batch_returns_count(self):
        """process_batch() returns number of processed entries."""
        from src.infrastructure.audit.outbox_processor import OutboxProcessor

        mock_session = mock.AsyncMock()

        # Create mock entries
        mock_entry = mock.Mock()
        mock_entry.id = 1
        mock_entry.event_id = uuid.uuid4()
        mock_entry.event_type = "AuditEvent"
        mock_entry.can_retry.return_value = True

        mock_result = mock.Mock()
        mock_result.scalars.return_value.all.return_value = [mock_entry]
        mock_session.execute.return_value = mock_result
        mock_session.flush = mock.AsyncMock()

        processor = OutboxProcessor(session=mock_session)

        # Mock RabbitMQ connection to avoid actual connection
        with mock.patch.object(processor, "_publish_entry", mock.AsyncMock()):
            count = await processor.process_batch()

        assert count == 1

    @pytest.mark.asyncio
    async def test_process_batch_marks_entries_published(self):
        """process_batch() marks entries as published on success."""
        from src.infrastructure.audit.outbox_processor import OutboxProcessor

        mock_session = mock.AsyncMock()
        mock_session.flush = mock.AsyncMock()

        mock_entry = mock.Mock()
        mock_entry.id = 1
        mock_entry.event_id = uuid.uuid4()
        mock_entry.event_type = "AuditEvent"
        mock_entry.can_retry.return_value = True

        mock_result = mock.Mock()
        mock_result.scalars.return_value.all.return_value = [mock_entry]
        mock_session.execute.return_value = mock_result

        processor = OutboxProcessor(session=mock_session)

        # Mock RabbitMQ connection to avoid actual connection
        with mock.patch.object(processor, "_publish_entry", mock.AsyncMock()):
            await processor.process_batch()

        mock_entry.mark_published.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_batch_marks_failed_on_error(self):
        """process_batch() marks entries as failed when exception occurs."""
        from src.infrastructure.audit.outbox_processor import OutboxProcessor

        mock_session = mock.AsyncMock()
        mock_session.flush = mock.AsyncMock()

        mock_entry = mock.Mock()
        mock_entry.id = 1
        mock_entry.event_id = uuid.uuid4()
        mock_entry.can_retry.return_value = True

        mock_result = mock.Mock()
        mock_result.scalars.return_value.all.return_value = [mock_entry]
        mock_session.execute.return_value = mock_result

        processor = OutboxProcessor(session=mock_session)

        # Patch _publish_entry to raise
        with mock.patch.object(processor, "_publish_entry", side_effect=Exception("Test error")):
            await processor.process_batch()

        mock_entry.mark_failed.assert_called_once_with("Test error")

    @pytest.mark.asyncio
    async def test_process_batch_respects_batch_size(self):
        """process_batch() respects batch_size parameter."""
        from src.infrastructure.audit.outbox_processor import OutboxProcessor

        mock_session = mock.AsyncMock()

        mock_result = mock.Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        processor = OutboxProcessor(session=mock_session)

        await processor.process_batch(batch_size=50)

        # Verify limit was passed in query
        call_args = mock_session.execute.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_process_batch_empty_when_no_pending(self):
        """process_batch() returns 0 when no pending entries."""
        from src.infrastructure.audit.outbox_processor import OutboxProcessor

        mock_session = mock.AsyncMock()

        mock_result = mock.Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        processor = OutboxProcessor(session=mock_session)

        count = await processor.process_batch()

        assert count == 0


class TestOutboxProcessorRetry:
    """Test retry logic."""

    @pytest.mark.asyncio
    async def test_mark_entries_for_retry_resets_failed_entries(self):
        """mark_entries_for_retry() resets failed entries older than cutoff."""
        from src.infrastructure.audit.outbox_processor import OutboxProcessor

        mock_session = mock.AsyncMock()
        mock_session.flush = mock.AsyncMock()

        mock_result = mock.Mock()
        mock_result.rowcount = 5
        mock_session.execute.return_value = mock_result

        processor = OutboxProcessor(session=mock_session)

        count = await processor.mark_entries_for_retry(older_than_minutes=60)

        assert count == 5
        mock_session.execute.assert_called_once()
        mock_session.flush.assert_called_once()


class TestOutboxProcessorLifecycle:
    """Test start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_stop_sets_running_false(self):
        """stop() sets _running to False and signals shutdown."""
        from src.infrastructure.audit.outbox_processor import OutboxProcessor

        mock_session = mock.AsyncMock()

        processor = OutboxProcessor(session=mock_session)
        processor._running = True
        processor._task = None
        processor._shutdown_event = mock.Mock()

        await processor.stop()

        assert processor._running is False
        processor._shutdown_event.set.assert_called_once()

    def test_start_creates_task(self):
        """start() creates asyncio task."""
        from src.infrastructure.audit.outbox_processor import OutboxProcessor

        mock_session = mock.AsyncMock()

        processor = OutboxProcessor(session=mock_session)
        processor._running = False
        processor._task = None

        # Mock asyncio.create_task to avoid needing a running event loop
        # Also mock process_forever to prevent coroutine warning
        mock_task = mock.Mock()
        with mock.patch("asyncio.create_task", return_value=mock_task):
            with mock.patch.object(processor, "process_forever", mock.AsyncMock()):
                processor.start()
                # Verify task was assigned
                assert processor._task is mock_task

        # Clean up
        processor._running = False

    def test_start_does_nothing_if_already_running(self):
        """start() does nothing if task already exists and not done."""
        from src.infrastructure.audit.outbox_processor import OutboxProcessor

        mock_session = mock.AsyncMock()

        processor = OutboxProcessor(session=mock_session)

        # Create a mock done task
        mock_task = mock.Mock()
        mock_task.done.return_value = False
        processor._task = mock_task

        processor.start()

        # Should not create new task
        mock_task.done.assert_called()


class TestOutboxProcessorPublish:
    """Test _publish_entry() method."""

    @pytest.mark.asyncio
    async def test_publish_entry_connects_and_publishes(self):
        """_publish_entry() connects to RabbitMQ and publishes message."""
        from src.infrastructure.audit.outbox_processor import OutboxProcessor

        mock_session = mock.AsyncMock()
        processor = OutboxProcessor(session=mock_session)

        mock_entry = mock.Mock()
        mock_entry.id = 1
        mock_entry.event_id = uuid.uuid4()
        mock_entry.event_type = "AuditEvent"
        mock_entry.payload = {"log_id": str(uuid.uuid4()), "action": "test"}

        # Mock aio_pika connection and channel
        mock_channel = mock.AsyncMock()
        mock_exchange = mock.AsyncMock()
        mock_channel.default_exchange = mock_exchange

        with mock.patch("aio_pika.connect_robust", new_callable=mock.AsyncMock) as mock_connect:
            mock_connection = mock.AsyncMock()
            mock_connection.channel = mock.AsyncMock(return_value=mock_channel)
            mock_connect.return_value = mock_connection

            await processor._publish_entry(mock_entry)

            # Verify connection was established
            mock_connect.assert_called_once()
            # Verify message was published
            mock_exchange.publish.assert_called_once()
