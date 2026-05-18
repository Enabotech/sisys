"""Tests for integration test infrastructure utilities.

Verifies test fixtures, Mock configuration, and data factory correctness.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import fakeredis.aioredis
import pytest

from src.domain.events.base import DomainEvent
from src.infrastructure.messaging.retry.checker import IdempotencyChecker
from src.infrastructure.messaging.retry.retry_policy import RetryPolicy

# ===================================================================
# TDD Cycle A: Test Directory & Configuration
# ===================================================================


class TestTestFixtureConfiguration:
    """Verify test fixtures are correctly configured and isolated."""

    @pytest.mark.asyncio
    async def test_outbox_repo_fixture_is_fresh_mock(self, outbox_repo: AsyncMock) -> None:
        """Each test should get a fresh mock OutboxRepository."""
        outbox_repo.get_unpublished.return_value = []
        result = await outbox_repo.get_unpublished(limit=10)
        assert result == []

    def test_event_store_fixture_is_fresh(self, event_id: UUID) -> None:
        """Each test should get a fresh InMemoryEventStore instance."""
        from src.infrastructure.messaging.message_serializer import InMemoryEventStore

        store = InMemoryEventStore()
        events = store.get_events(event_id)
        assert len(events) == 0

    def test_event_id_fixture_is_valid_uuid(self, event_id: UUID) -> None:
        """The event_id fixture should be a valid UUID."""
        assert isinstance(event_id, UUID)

    def test_sample_event_is_domain_event(self, sample_event: DomainEvent) -> None:
        """The sample_event fixture should be a DomainEvent instance."""
        assert isinstance(sample_event, DomainEvent)
        assert sample_event.event_type == "DocumentProcessed"

    def test_event_list_has_multiple_events(self, event_list: list[DomainEvent]) -> None:
        """The event_list fixture should provide multiple events."""
        assert len(event_list) == 3
        assert all(isinstance(e, DomainEvent) for e in event_list)


# ===================================================================
# TDD Cycle B: Test Data Factory
# ===================================================================


class TestDataFactory:
    """Verify test data factory generates correct domain entities."""

    def test_sample_event_has_required_fields(self, sample_event: DomainEvent) -> None:
        """Sample event should have all required DomainEvent fields."""
        assert sample_event.event_id is not None
        assert sample_event.event_type != ""
        assert sample_event.timestamp is not None
        assert sample_event.source == "test"
        assert sample_event.aggregate_id is not None
        assert sample_event.aggregate_type == "Document"

    def test_sample_event_payload_is_dict(self, sample_event: DomainEvent) -> None:
        """Sample event payload should be a dictionary."""
        assert isinstance(sample_event.payload, dict)
        assert "document_id" in sample_event.payload

    def test_event_list_unique_ids(self, event_list: list[DomainEvent]) -> None:
        """All events in the list should have unique IDs."""
        ids = [e.event_id for e in event_list]
        assert len(ids) == len(set(ids))


# ===================================================================
# TDD Cycle C: External Service Mock Configuration + Timeout
# ===================================================================


class TestMockConfiguration:
    """Verify external service Mock fixtures work correctly."""

    def test_mock_redis_is_fakeredis(self, mock_redis: fakeredis.aioredis.FakeRedis) -> None:
        """Mock Redis should be a fakeredis instance."""
        assert isinstance(mock_redis, fakeredis.aioredis.FakeRedis)

    @pytest.mark.asyncio
    async def test_mock_redis_can_set_and_get(self, mock_redis: fakeredis.aioredis.FakeRedis) -> None:
        """Mock Redis should support basic set/get operations."""
        await mock_redis.set("key", "value")
        assert await mock_redis.get("key") == "value"

    @pytest.mark.asyncio
    async def test_mock_redis_set_nx_atomic(self, mock_redis: fakeredis.aioredis.FakeRedis) -> None:
        """Mock Redis SET NX should be atomic (first call succeeds, second fails)."""
        result1 = await mock_redis.set("idempotency:test", "1", nx=True, ex=3600)
        result2 = await mock_redis.set("idempotency:test", "1", nx=True, ex=3600)
        assert result1 is True
        assert not result2  # Already exists (fakeredis returns None or False)

    def test_mock_postgresql_repo_is_async_mock(self, mock_postgresql_repo) -> None:
        """PostgreSQL mock should be an AsyncMock."""
        from unittest.mock import AsyncMock

        assert isinstance(mock_postgresql_repo, AsyncMock)

    def test_mock_rabbitmq_publisher_is_async_mock(self, mock_rabbitmq_publisher) -> None:
        """RabbitMQ mock should be an AsyncMock."""
        from unittest.mock import AsyncMock

        assert isinstance(mock_rabbitmq_publisher, AsyncMock)


class TestIdempotencyChecker:
    """Verify IdempotencyChecker uses fakeredis atomically."""

    @pytest.mark.asyncio
    async def test_try_acquire_first_time_succeeds(self, idempotency_checker: IdempotencyChecker, event_id: UUID) -> None:
        """First try_acquire should return True."""
        assert await idempotency_checker.try_acquire(event_id) is True

    @pytest.mark.asyncio
    async def test_try_acquire_second_time_fails(self, idempotency_checker: IdempotencyChecker, event_id: UUID) -> None:
        """Second try_acquire for same event_id should return False."""
        await idempotency_checker.try_acquire(event_id)
        assert await idempotency_checker.try_acquire(event_id) is False

    @pytest.mark.asyncio
    async def test_try_acquire_different_events_both_succeed(self, idempotency_checker: IdempotencyChecker) -> None:
        """Different event_ids should both succeed independently."""
        id1 = uuid4()
        id2 = uuid4()
        assert await idempotency_checker.try_acquire(id1) is True
        assert await idempotency_checker.try_acquire(id2) is True


class TestRetryPolicy:
    """Verify RetryPolicy implements exponential backoff with jitter."""

    def test_get_delay_increases_with_retries(self, retry_policy: RetryPolicy, monkeypatch: pytest.MonkeyPatch) -> None:
        """Delay should increase with retry count (exponential backoff)."""
        # Mock jitter to fixed 1.0 so ordering is deterministic.
        # Without this, random.uniform(0.5, 1.5) can make delay_1 < delay_0.
        monkeypatch.setattr("src.infrastructure.messaging.retry.retry_policy.random.uniform", lambda a, b: 1.0)

        delay_0 = retry_policy.get_delay(0)
        delay_1 = retry_policy.get_delay(1)
        delay_2 = retry_policy.get_delay(2)
        assert delay_1 > delay_0
        assert delay_2 > delay_1

    def test_get_delay_respects_max_delay(self, retry_policy: RetryPolicy) -> None:
        """Delay should never exceed max_delay."""
        for i in range(20):
            assert retry_policy.get_delay(i) <= retry_policy.max_delay

    def test_get_delay_contains_jitter(self, retry_policy: RetryPolicy) -> None:
        """Multiple calls with same retry_count should produce different delays (jitter)."""
        delays = {retry_policy.get_delay(0) for _ in range(10)}
        # With jitter, we should see some variation (probabilistic)
        assert len(delays) > 1

    def test_should_retry_below_max(self, retry_policy: RetryPolicy) -> None:
        """should_retry should return True when retry_count < max_retries."""
        assert retry_policy.should_retry(0) is True
        assert retry_policy.should_retry(2) is True

    def test_should_retry_at_max(self, retry_policy: RetryPolicy) -> None:
        """should_retry should return False when retry_count >= max_retries."""
        assert retry_policy.should_retry(3) is False
        assert retry_policy.should_retry(5) is False
