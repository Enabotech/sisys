"""Task 2 TDD Tests — RedisRetryQueue."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import fakeredis.aioredis
import pytest

from src.domain.events import DocumentProcessed
from src.domain.events.base import DomainEvent
from src.infrastructure.messaging.retry.redis_retry_queue import (
    RedisRetryQueue,
    RetryQueueEntry,
)


def _make_event() -> DomainEvent:
    """Create a test domain event."""
    return DocumentProcessed(
        document_id=uuid4(),
        parse_result={"pages": 10},
        embedding=[0.1] * 1024,
    )


@pytest.fixture
async def redis_client():
    """Provide a fakeredis client for testing."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
async def retry_queue(redis_client):
    """Provide a RedisRetryQueue with fakeredis."""
    queue = RedisRetryQueue(redis_client=redis_client)
    yield queue
    # Cleanup after test
    await queue.clear()


# ============================================================================
# TDD Cycle A: RedisRetryQueue
# ============================================================================


class TestRetryQueueEntry:
    """RetryQueueEntry tests."""

    def test_create_entry(self):
        """Should create entry with all fields."""
        event_id = uuid4()
        retry_at = datetime.now(UTC) + timedelta(minutes=5)

        entry = RetryQueueEntry(
            event_id=event_id,
            event_type="TestEvent",
            payload={"key": "value"},
            retry_at=retry_at,
            retry_count=1,
            error="Connection timeout",
        )

        assert entry.event_id == event_id
        assert entry.event_type == "TestEvent"
        assert entry.payload == {"key": "value"}
        assert entry.retry_at == retry_at
        assert entry.retry_count == 1
        assert entry.error == "Connection timeout"

    def test_to_json_and_back(self):
        """Should serialize to JSON and deserialize back."""
        event_id = uuid4()
        retry_at = datetime.now(UTC) + timedelta(minutes=5)

        original = RetryQueueEntry(
            event_id=event_id,
            event_type="TestEvent",
            payload={"key": "value"},
            retry_at=retry_at,
            retry_count=1,
            error="Connection timeout",
        )

        json_str = original.to_json()
        restored = RetryQueueEntry.from_json(json_str)

        assert restored.event_id == event_id
        assert restored.event_type == "TestEvent"
        assert restored.payload == {"key": "value"}
        assert restored.retry_count == 1
        assert restored.error == "Connection timeout"


class TestRedisRetryQueue:
    """RedisRetryQueue tests using fakeredis."""

    async def test_enqueue_adds_event_to_zset(self, retry_queue):
        """enqueue should add event to Redis ZSET."""
        event = _make_event()
        retry_at = datetime.now(UTC) + timedelta(minutes=5)

        await retry_queue.enqueue(
            event_id=event.event_id,
            event_type=event.event_type,
            payload=event.to_dict(),
            retry_at=retry_at,
            retry_count=0,
        )

        count = await retry_queue.count()
        assert count == 1

    async def test_dequeue_returns_expired_events(self, retry_queue, redis_client):
        """dequeue should return events whose retry_at has passed."""
        event = _make_event()
        # Set retry_at to past time
        retry_at = datetime.now(UTC) - timedelta(minutes=1)

        await retry_queue.enqueue(
            event_id=event.event_id,
            event_type=event.event_type,
            payload=event.to_dict(),
            retry_at=retry_at,
            retry_count=1,
        )

        entries = await retry_queue.dequeue(limit=10)

        assert len(entries) == 1
        assert entries[0].event_id == event.event_id
        assert entries[0].retry_count == 1

        # Verify removed from queue
        count = await retry_queue.count()
        assert count == 0

    async def test_dequeue_does_not_return_future_events(self, retry_queue):
        """dequeue should NOT return events with future retry_at."""
        event = _make_event()
        # Set retry_at to future time
        retry_at = datetime.now(UTC) + timedelta(hours=1)

        await retry_queue.enqueue(
            event_id=event.event_id,
            event_type=event.event_type,
            payload=event.to_dict(),
            retry_at=retry_at,
            retry_count=0,
        )

        entries = await retry_queue.dequeue(limit=10)

        assert len(entries) == 0
        # Event should still be in queue
        count = await retry_queue.count()
        assert count == 1

    async def test_dequeue_on_empty_queue_returns_empty(self, retry_queue):
        """dequeue on empty queue should return empty list."""
        entries = await retry_queue.dequeue(limit=10)
        assert entries == []

    async def test_count_returns_queue_size(self, retry_queue):
        """count should return number of events in queue."""
        event1 = _make_event()
        event2 = _make_event()
        retry_at = datetime.now(UTC) + timedelta(minutes=5)

        await retry_queue.enqueue(event1.event_id, event1.event_type, event1.to_dict(), retry_at)
        await retry_queue.enqueue(event2.event_id, event2.event_type, event2.to_dict(), retry_at)

        count = await retry_queue.count()
        assert count == 2

    async def test_peek_returns_events_without_removing(self, retry_queue):
        """peek should return events without removing them."""
        event = _make_event()
        retry_at = datetime.now(UTC) - timedelta(minutes=1)

        await retry_queue.enqueue(
            event_id=event.event_id,
            event_type=event.event_type,
            payload=event.to_dict(),
            retry_at=retry_at,
            retry_count=0,
        )

        entries = await retry_queue.peek(limit=10)

        assert len(entries) == 1
        # Event should still be in queue
        count = await retry_queue.count()
        assert count == 1

    async def test_remove_deletes_specific_event(self, retry_queue):
        """remove should delete the specified event by ID."""
        event = _make_event()
        retry_at = datetime.now(UTC) + timedelta(minutes=5)

        await retry_queue.enqueue(
            event_id=event.event_id,
            event_type=event.event_type,
            payload=event.to_dict(),
            retry_at=retry_at,
            retry_count=0,
        )

        removed = await retry_queue.remove(event.event_id)

        assert removed is True
        count = await retry_queue.count()
        assert count == 0

    async def test_remove_returns_false_for_nonexistent_event(self, retry_queue):
        """remove should return False if event not found."""
        removed = await retry_queue.remove(uuid4())
        assert removed is False

    async def test_clear_removes_all_events(self, retry_queue):
        """clear should remove all events from queue."""
        event1 = _make_event()
        event2 = _make_event()
        retry_at = datetime.now(UTC) + timedelta(minutes=5)

        await retry_queue.enqueue(event1.event_id, event1.event_type, event1.to_dict(), retry_at)
        await retry_queue.enqueue(event2.event_id, event2.event_type, event2.to_dict(), retry_at)

        await retry_queue.clear()

        count = await retry_queue.count()
        assert count == 0

    async def test_multiple_events_ordered_by_retry_at(self, retry_queue):
        """Events should be dequeued in order of retry_at (oldest first)."""
        event1 = _make_event()
        event2 = _make_event()
        retry_at1 = datetime.now(UTC) - timedelta(minutes=5)  # Earlier
        retry_at2 = datetime.now(UTC) - timedelta(minutes=10)  # Even earlier

        # Add in reverse order
        await retry_queue.enqueue(event1.event_id, event1.event_type, event1.to_dict(), retry_at1)
        await retry_queue.enqueue(event2.event_id, event2.event_type, event2.to_dict(), retry_at2)

        entries = await retry_queue.dequeue(limit=10)

        # Should get event2 first (earlier retry_at)
        assert len(entries) == 2
        assert entries[0].event_id == event2.event_id
        assert entries[1].event_id == event1.event_id
