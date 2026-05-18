"""Task 1 TDD Tests — PostgresDeadLetterQueue."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest import mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.events import DocumentProcessed
from src.domain.events.base import DomainEvent
from src.infrastructure.messaging.outbox.postgres_dead_letter_queue import (
    DeadLetterQueueEntry,
    DeadLetterQueueModel,
    PostgresDeadLetterQueue,
)
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session


def _make_event() -> DomainEvent:
    """Create a test domain event."""
    return DocumentProcessed(
        document_id=uuid4(),
        parse_result={"pages": 10},
        embedding=[0.1] * 1024,
    )


class MockDLQModel:
    """Mock DLQ model that behaves like a real SQLAlchemy model."""

    def __init__(
        self,
        event: DomainEvent,
        error_msg: str,
        retry_count: int,
        status: str = "pending",
    ):
        self.id = uuid4()
        self.event_id = event.event_id
        self.event_type = event.event_type
        self.payload = event.to_dict()  # Real dict
        self.error_message = error_msg
        self.retry_count = retry_count
        self.context = None
        self.created_at = datetime.now(UTC)
        self.status = status
        self.processed_at = None
        self.action_taken = None


@pytest.fixture
def mock_session():
    """Mock AsyncSession for testing."""
    session = mock.AsyncMock(spec=AsyncSession)
    session.add = mock.Mock()
    session.flush = mock.AsyncMock()
    # Configure execute to return a sync mock result
    session.execute.return_value = mock.MagicMock()
    return session


@pytest.fixture
def dlq(mock_session):
    """Provide PostgresDeadLetterQueue with mock session."""
    token = set_session(mock_session)
    repo = PostgresDeadLetterQueue()
    yield repo
    reset_session(token)


# ============================================================================
# TDD Cycle A: PostgresDeadLetterQueue
# ============================================================================


class TestDeadLetterQueueEntry:
    """DeadLetterQueueEntry tests — a data class to hold DLQ records."""

    def test_create_entry_with_required_fields(self):
        """Should create entry with event data and error info."""
        event = _make_event()
        entry = DeadLetterQueueEntry(
            event_id=event.event_id,
            event_type=event.event_type,
            payload=event.to_dict(),
            error_message="Connection timeout",
            retry_count=3,
        )
        assert entry.event_id == event.event_id
        assert entry.event_type == event.event_type
        assert entry.error_message == "Connection timeout"
        assert entry.retry_count == 3
        assert entry.status == "pending"
        assert entry.processed_at is None
        assert entry.action_taken is None

    def test_create_entry_with_optional_fields(self):
        """Should create entry with all optional fields."""
        event = _make_event()
        entry = DeadLetterQueueEntry(
            event_id=event.event_id,
            event_type=event.event_type,
            payload=event.to_dict(),
            error_message="Connection timeout",
            retry_count=3,
            context={"host": "rabbitmq-1", "queue": "documents"},
            status="processed",
            action_taken="retry_limit_exceeded",
        )
        assert entry.context == {"host": "rabbitmq-1", "queue": "documents"}
        assert entry.status == "processed"
        assert entry.action_taken == "retry_limit_exceeded"

    def test_to_domain_event_reconstructs_event(self):
        """Should reconstruct DomainEvent from payload."""
        event = _make_event()
        entry = DeadLetterQueueEntry(
            event_id=event.event_id,
            event_type=event.event_type,
            payload=event.to_dict(),
            error_message="error",
            retry_count=1,
        )
        reconstructed = entry.to_domain_event()
        assert reconstructed.event_id == event.event_id
        assert reconstructed.event_type == event.event_type


class TestPostgresDeadLetterQueue:
    """PostgresDeadLetterQueue tests using mock AsyncSession."""

    @pytest.mark.asyncio
    async def test_enqueue_adds_entry_to_database(self, mock_session):
        """enqueue should persist a DLQ entry to PostgreSQL."""
        token = set_session(mock_session)
        try:
            dlq = PostgresDeadLetterQueue()
            event = _make_event()
            error_msg = "Connection timeout"
            retry_count = 3

            await dlq.enqueue(event, error_msg, retry_count)

            # Verify add was called with a DeadLetterQueueModel
            mock_session.add.assert_called_once()
            call_args = mock_session.add.call_args
            model = call_args[0][0]
            assert isinstance(model, DeadLetterQueueModel)
            assert model.event_id == event.event_id
            assert model.event_type == event.event_type
            assert model.error_message == error_msg
            assert model.retry_count == retry_count
            assert model.status == "pending"
            # Verify flush was called to persist
            mock_session.flush.assert_awaited_once()
        finally:
            reset_session(token)

    @pytest.mark.asyncio
    async def test_enqueue_with_context(self, mock_session):
        """enqueue should store additional context."""
        token = set_session(mock_session)
        try:
            dlq = PostgresDeadLetterQueue()
            event = _make_event()
            context = {"host": "rabbitmq-1", "queue": "documents"}

            await dlq.enqueue(event, "error", retry_count=2, context=context)

            model = mock_session.add.call_args[0][0]
            assert model.context == context
        finally:
            reset_session(token)

    @pytest.mark.asyncio
    async def test_dequeue_returns_oldest_pending_entry(self, mock_session):
        """dequeue should return (event, error, retry_count) and mark as processed."""
        token = set_session(mock_session)
        try:
            dlq = PostgresDeadLetterQueue()
            event1 = _make_event()
            model1 = MockDLQModel(event1, "error1", 1)

            # Configure mock chain
            mock_session.execute.return_value.scalar_one_or_none.return_value = model1

            result = await dlq.dequeue()

            assert result is not None
            event, error, retries = result
            assert event.event_id == event1.event_id
            assert error == "error1"
            assert retries == 1
            assert model1.status == "processed"
            assert model1.processed_at is not None
        finally:
            reset_session(token)

    @pytest.mark.asyncio
    async def test_dequeue_on_empty_queue_returns_none(self, mock_session):
        """dequeue on empty DLQ should return None."""
        token = set_session(mock_session)
        try:
            dlq = PostgresDeadLetterQueue()

            # Configure mock to return None
            mock_session.execute.return_value.scalar_one_or_none.return_value = None

            result = await dlq.dequeue()
            assert result is None
        finally:
            reset_session(token)

    @pytest.mark.asyncio
    async def test_get_all_returns_entries_ordered_by_created_at_desc(self, mock_session):
        """get_all should return all DLQ entries ordered by created_at desc."""
        token = set_session(mock_session)
        try:
            dlq = PostgresDeadLetterQueue()
            event1 = _make_event()
            event2 = _make_event()
            model1 = MockDLQModel(event1, "error1", 1)
            model2 = MockDLQModel(event2, "error2", 2)

            # Configure mock chain: session.execute() -> result -> scalars() -> all() -> [model2, model1]
            mock_session.execute.return_value.scalars.return_value.all.return_value = [model2, model1]

            entries = await dlq.get_all()

            assert len(entries) == 2
            assert entries[0].event_id == event2.event_id
            assert entries[1].event_id == event1.event_id
        finally:
            reset_session(token)

    @pytest.mark.asyncio
    async def test_get_by_status_filters_correctly(self, mock_session):
        """get_by_status should filter entries by status."""
        token = set_session(mock_session)
        try:
            dlq = PostgresDeadLetterQueue()
            event = _make_event()
            model = MockDLQModel(event, "error", 1, status="processed")

            mock_session.execute.return_value.scalars.return_value.all.return_value = [model]

            entries = await dlq.get_by_status("processed")

            assert len(entries) == 1
            assert entries[0].status == "processed"
        finally:
            reset_session(token)

    @pytest.mark.asyncio
    async def test_mark_action_taken_updates_entry(self, mock_session):
        """mark_action_taken should update action_taken and status."""
        token = set_session(mock_session)
        try:
            dlq = PostgresDeadLetterQueue()
            entry_id = uuid4()
            model = mock.Mock()
            model.id = entry_id
            model.action_taken = None
            model.status = "pending"

            mock_session.execute.return_value.scalar_one_or_none.return_value = model

            await dlq.mark_action_taken(entry_id, "manual_retry")

            assert model.action_taken == "manual_retry"
            assert model.status == "processed"
        finally:
            reset_session(token)

    @pytest.mark.asyncio
    async def test_count_pending_returns_count(self, mock_session):
        """count_pending should return the count of pending entries."""
        token = set_session(mock_session)
        try:
            dlq = PostgresDeadLetterQueue()

            mock_session.execute.return_value.scalar.return_value = 5

            count = await dlq.count_pending()
            assert count == 5
        finally:
            reset_session(token)
