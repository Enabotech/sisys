"""Task 7 TDD Tests — PostgreSQLEventStore (AC-7)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest import mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.messaging.event_store import (
    EVENT_STORE_TABLE,
    EventStoreModel,
    PostgreSQLEventStore,
)
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session


class MockEventStoreModel:
    """Mock model for event store records."""

    def __init__(
        self,
        event_id: str,
        aggregate_id: str,
        aggregate_type: str,
        version: int,
        event_type: str,
        payload: dict,
        timestamp: datetime,
        metadata: dict | None = None,
    ):
        self.id = uuid4()
        self.event_id = event_id
        self.aggregate_id = aggregate_id
        self.aggregate_type = aggregate_type
        self.version = version
        self.event_type = event_type
        self.payload = payload
        self.timestamp = timestamp
        self.metadata = metadata or {}
        # For scalar_one_or_none
        self.scalar_one_or_none = None


class MockRow:
    """Mock row for fetchall results."""

    def __init__(self, event_id, aggregate_id, aggregate_type, version, event_type, payload, timestamp, metadata=None):
        self.event_id = event_id
        self.aggregate_id = aggregate_id
        self.aggregate_type = aggregate_type
        self.version = version
        self.event_type = event_type
        self.payload = payload
        self.timestamp = timestamp
        self.metadata = metadata


@pytest.fixture
def mock_session():
    """Mock AsyncSession for testing."""
    session = mock.AsyncMock(spec=AsyncSession)
    session.execute = mock.AsyncMock()
    # Default result that supports both scalar_one_or_none and fetchall
    mock_result = mock.MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_result.fetchall.return_value = []
    session.execute.return_value = mock_result
    return session


@pytest.fixture
def event_store(mock_session):
    """Provide PostgreSQLEventStore with mock session."""
    token = set_session(mock_session)
    repo = PostgreSQLEventStore()
    yield repo
    reset_session(token)


# ============================================================================
# Tests
# ============================================================================


class TestEventStoreModel:
    """EventStoreModel tests."""

    def test_create_table_sql(self):
        """Should return valid CREATE TABLE SQL."""
        sql = EventStoreModel.create_table_sql()
        assert "CREATE TABLE" in sql
        assert EVENT_STORE_TABLE in sql
        assert "event_id" in sql
        assert "aggregate_id" in sql
        assert "payload" in sql

    def test_init_stores_all_fields(self):
        """EventStoreModel.__init__ should store all fields (lines 52-60)."""
        timestamp = datetime.now(UTC)
        model = EventStoreModel(
            event_id="evt-123",
            aggregate_id="agg-456",
            aggregate_type="Document",
            version=1,
            event_type="DocumentProcessed",
            payload={"key": "value"},
            timestamp=timestamp,
            metadata={"meta": "data"},
            id=999,
        )
        assert model.id == 999
        assert model.event_id == "evt-123"
        assert model.aggregate_id == "agg-456"
        assert model.aggregate_type == "Document"
        assert model.version == 1
        assert model.event_type == "DocumentProcessed"
        assert model.payload == {"key": "value"}
        assert model.timestamp == timestamp
        assert model.metadata == {"meta": "data"}

    def test_init_with_defaults(self):
        """EventStoreModel.__init__ with minimal args uses defaults."""
        timestamp = datetime.now(UTC)
        model = EventStoreModel(
            event_id="evt-789",
            aggregate_id="agg-abc",
            aggregate_type="Agent",
            version=2,
            event_type="AgentDecided",
            payload={},
            timestamp=timestamp,
        )
        assert model.id is None
        assert model.metadata is None

    def test_tablename_constant(self):
        """EventStoreModel.__tablename__ should equal EVENT_STORE_TABLE."""
        assert EventStoreModel.__tablename__ == EVENT_STORE_TABLE


class TestPostgreSQLEventStore:
    """PostgreSQLEventStore tests."""

    async def test_append_adds_event_to_database(self, event_store, mock_session):
        """append should persist an event to PostgreSQL."""
        from src.domain.events import DocumentProcessed

        event = DocumentProcessed(
            document_id=uuid4(),
            parse_result={"pages": 10},
            embedding=[0.1] * 1024,
        )

        await event_store.append(event)

        assert mock_session.execute.call_count == 2
        # Second call is the INSERT
        call_args = mock_session.execute.call_args_list[1]
        params = call_args[0][1]
        assert params["event_id"] == str(event.event_id)
        assert params["aggregate_id"] == str(event.aggregate_id)
        assert params["event_type"] == event.event_type

    async def test_append_with_optimistic_locking(self, event_store, mock_session):
        """append should raise error on version conflict."""
        from src.domain.events import DocumentProcessed
        from src.infrastructure.messaging.event_store import VersionError

        event = DocumentProcessed(
            document_id=uuid4(),
            parse_result={"pages": 10},
            embedding=[0.1] * 1024,
        )

        # Configure execute to return existing record (version conflict)
        mock_result = mock.MagicMock()
        mock_result.scalar_one_or_none.return_value = {"id": 1}  # Existing record found
        mock_session.execute.return_value = mock_result

        with pytest.raises(VersionError):
            await event_store.append(event)

    async def test_get_events_returns_events_for_aggregate(self, event_store, mock_session):
        """get_events should return all events for an aggregate."""
        agg_id = uuid4()
        doc_id = uuid4()

        mock_row = MockRow(
            event_id=str(doc_id),
            aggregate_id=str(agg_id),
            aggregate_type="Document",
            version=1,
            event_type="DocumentProcessed",
            payload=json.dumps({"document_id": str(doc_id), "parse_result": {"pages": 10}}),
            timestamp=datetime.now(UTC),
        )

        mock_result = mock.MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        events = await event_store.get_events(agg_id)

        assert len(events) == 1
        assert events[0].event_id == doc_id
        assert events[0].event_type == "DocumentProcessed"
        assert events[0].payload["parse_result"] == {"pages": 10}

    async def test_get_events_returns_empty_list_for_no_events(self, event_store, mock_session):
        """get_events should return empty list when no events exist."""
        mock_result = mock.MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        events = await event_store.get_events(uuid4())

        assert events == []

    async def test_get_events_by_type_filters_by_event_type(self, event_store, mock_session):
        """get_events_by_type should filter by event type and time range."""
        doc_id = uuid4()
        start_time = datetime.now(UTC) - timedelta(hours=1)
        end_time = datetime.now(UTC)

        mock_row = MockRow(
            event_id=str(doc_id),
            aggregate_id=str(uuid4()),
            aggregate_type="Document",
            version=1,
            event_type="DocumentProcessed",
            payload=json.dumps({"document_id": str(doc_id), "parse_result": {"pages": 10}}),
            timestamp=datetime.now(UTC),
        )

        mock_result = mock.MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        events = await event_store.get_events_by_type("DocumentProcessed", start_time, end_time)

        assert len(events) == 1
        assert events[0].event_type == "DocumentProcessed"

    async def test_get_events_by_type_returns_empty_list(self, event_store, mock_session):
        """get_events_by_type should return empty list when no matches."""
        mock_result = mock.MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        events = await event_store.get_events_by_type(
            "NonExistentEvent",
            datetime.now(UTC) - timedelta(hours=1),
            datetime.now(UTC),
        )

        assert events == []
