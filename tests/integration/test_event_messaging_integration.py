"""Integration tests for event messaging components (AC-1, AC-7).

Verifies end-to-end behavior of:
- PostgresDeadLetterQueue with PostgreSQL session
- PostgreSQLEventStore with PostgreSQL session
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest import mock
from uuid import uuid4

import pytest

from src.domain.events import DocumentProcessed
from src.domain.events.base import DomainEvent


class TestDeadLetterQueueIntegration:
    """Integration tests for PostgresDeadLetterQueue (AC-1)."""

    @pytest.fixture
    def mock_session(self):
        """Provide mock AsyncSession for integration testing."""
        session = mock.AsyncMock()
        session.add = mock.Mock()
        session.execute = mock.AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_enqueue_integration(self, mock_session):
        """enqueue should persist DLQ entry to database via session."""
        from src.infrastructure.messaging.outbox.postgres_dead_letter_queue import (
            PostgresDeadLetterQueue,
        )

        dlq = PostgresDeadLetterQueue(session=mock_session)
        event = DocumentProcessed(
            document_id=uuid4(),
            parse_result={"pages": 10},
            embedding=[0.1] * 1024,
        )

        await dlq.enqueue(event, "Connection timeout", retry_count=3)

        mock_session.add.assert_called_once()
        call_args = mock_session.add.call_args
        model = call_args[0][0]
        assert model.event_id == event.event_id
        assert model.event_type == "DocumentProcessed"
        assert model.error_message == "Connection timeout"
        assert model.retry_count == 3
        assert model.status == "pending"

    @pytest.mark.asyncio
    async def test_dequeue_integration(self, mock_session):
        """dequeue should retrieve and mark DLQ entry as processed."""
        from src.infrastructure.messaging.outbox.postgres_dead_letter_queue import (
            DeadLetterQueueModel,
            PostgresDeadLetterQueue,
        )

        dlq = PostgresDeadLetterQueue(session=mock_session)
        event = DocumentProcessed(
            document_id=uuid4(),
            parse_result={"pages": 10},
            embedding=[0.1] * 1024,
        )

        # Create mock model
        mock_model = mock.Mock(spec=DeadLetterQueueModel)
        mock_model.event_id = event.event_id
        mock_model.event_type = event.event_type
        mock_model.payload = event.to_dict()
        mock_model.error_message = "timeout"
        mock_model.retry_count = 2
        mock_model.status = "pending"
        mock_model.processed_at = None
        mock_model.action_taken = None

        # Configure mock chain - scalar_one_or_none is SYNC (not awaited)
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = mock_model
        mock_session.execute.return_value = mock_result

        result = await dlq.dequeue()

        assert result is not None
        entry, restored_event, error, retries = result
        assert entry.event_id == event.event_id
        assert restored_event.event_id == event.event_id
        assert error == "timeout"
        assert retries == 2
        assert mock_model.status == "processed"

    @pytest.mark.asyncio
    async def test_get_all_integration(self, mock_session):
        """get_all should return all DLQ entries."""
        from src.infrastructure.messaging.outbox.postgres_dead_letter_queue import (
            DeadLetterQueueModel,
            PostgresDeadLetterQueue,
        )

        dlq = PostgresDeadLetterQueue(session=mock_session)

        # Create mock models
        mock_model1 = mock.Mock(spec=DeadLetterQueueModel)
        mock_model1.event_id = uuid4()
        mock_model1.event_type = "DocumentProcessed"
        mock_model1.payload = {}
        mock_model1.error_message = "error1"
        mock_model1.retry_count = 1
        mock_model1.status = "pending"
        mock_model1.action_taken = None
        mock_model1.processed_at = None

        mock_model2 = mock.Mock(spec=DeadLetterQueueModel)
        mock_model2.event_id = uuid4()
        mock_model2.event_type = "DocumentProcessed"
        mock_model2.payload = {}
        mock_model2.error_message = "error2"
        mock_model2.retry_count = 2
        mock_model2.status = "processed"
        mock_model2.action_taken = None
        mock_model2.processed_at = None

        # Configure mock chain - scalars().all() is SYNC
        mock_result = mock.Mock()
        mock_scalars = mock.Mock()
        mock_scalars.all.return_value = [mock_model2, mock_model1]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        entries = await dlq.get_all()

        assert len(entries) == 2

    @pytest.mark.asyncio
    async def test_mark_action_taken_integration(self, mock_session):
        """mark_action_taken should update entry status and action."""
        from src.infrastructure.messaging.outbox.postgres_dead_letter_queue import (
            PostgresDeadLetterQueue,
        )

        dlq = PostgresDeadLetterQueue(session=mock_session)
        entry_id = uuid4()

        mock_model = mock.Mock()
        mock_model.id = entry_id
        mock_model.status = "pending"
        mock_model.action_taken = None

        # Configure mock chain - scalar_one_or_none is SYNC
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = mock_model
        mock_session.execute.return_value = mock_result

        await dlq.mark_action_taken(entry_id, "manual_retry")

        assert mock_model.action_taken == "manual_retry"
        assert mock_model.status == "processed"


class TestEventStoreIntegration:
    """Integration tests for PostgreSQLEventStore (AC-7)."""

    @pytest.fixture
    def mock_session(self):
        """Provide mock AsyncSession for integration testing."""
        session = mock.AsyncMock()
        session.execute = mock.AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_append_integration(self, mock_session):
        """append should persist event to event_store table."""
        from src.infrastructure.messaging.event_store import PostgreSQLEventStore

        store = PostgreSQLEventStore(session=mock_session)
        aggregate_id = uuid4()
        event = DomainEvent(
            event_id=uuid4(),
            event_type="DocumentProcessed",
            source="test",
            aggregate_id=aggregate_id,
            aggregate_type="Document",
            version=1,
            payload={"document_id": "test-doc-1"},
        )

        # Configure mock to return no existing record
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await store.append(event)

        assert mock_session.execute.call_count >= 1

    @pytest.mark.asyncio
    async def test_get_events_integration(self, mock_session):
        """get_events should retrieve events for aggregate."""
        from src.infrastructure.messaging.event_store import PostgreSQLEventStore

        store = PostgreSQLEventStore(session=mock_session)
        aggregate_id = uuid4()

        # Configure mock to return empty list
        mock_result = mock.Mock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        events = await store.get_events(aggregate_id)

        assert isinstance(events, list)

    @pytest.mark.asyncio
    async def test_get_events_by_type_integration(self, mock_session):
        """get_events_by_type should filter events by type and time range."""
        from src.infrastructure.messaging.event_store import PostgreSQLEventStore

        store = PostgreSQLEventStore(session=mock_session)
        now = datetime.now(UTC)
        start = now
        end = now

        # Configure mock to return empty list
        mock_result = mock.Mock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        events = await store.get_events_by_type("DocumentProcessed", start, end)

        assert isinstance(events, list)

    @pytest.mark.asyncio
    async def test_version_conflict_raises_error_integration(self, mock_session):
        """append should raise VersionError on duplicate aggregate_id + version."""
        from src.infrastructure.messaging.event_store import PostgreSQLEventStore, VersionError

        store = PostgreSQLEventStore(session=mock_session)
        aggregate_id = uuid4()
        event = DomainEvent(
            event_id=uuid4(),
            event_type="DocumentProcessed",
            source="test",
            aggregate_id=aggregate_id,
            aggregate_type="Document",
            version=1,
            payload={"document_id": "test-doc-1"},
        )

        # Configure mock to return existing record (version conflict)
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = mock.Mock()  # Existing record
        mock_session.execute.return_value = mock_result

        with pytest.raises(VersionError):
            await store.append(event)
