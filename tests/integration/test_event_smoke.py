"""Smoke tests for domain event pipeline (publish → in-memory outbox → query).

Verifies Story 1.2/1.3 event infrastructure works end-to-end at a basic level.
Does NOT test full RabbitMQ routing — that's Story 1.3 AC-3 scope.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from src.domain.events.base import DomainEvent
from src.infrastructure.messaging.adapters.event_outbox_adapter import EventOutboxAdapter
from src.infrastructure.messaging.idempotency.checker import IdempotencyChecker
from src.infrastructure.messaging.idempotency.retry_policy import RetryPolicy
from src.infrastructure.repositories.outbox import InMemoryOutboxRepository

# ===================================================================
# TDD Cycle A: Event Publish → In-Memory Outbox
# ===================================================================


class TestEventPublishToOutbox:
    """Verify events can be published to InMemoryOutboxRepository."""

    def test_save_event_to_outbox(self, outbox_repo: InMemoryOutboxRepository) -> None:
        """Event should be saved to outbox and retrievable."""
        event = DomainEvent(
            event_id=uuid4(),
            event_type="DocumentProcessed",
            source="test",
            aggregate_id=uuid4(),
            aggregate_type="Document",
            version=1,
            payload={"doc_id": "test-1"},
        )
        outbox_repo.save(event)

        unpublished = outbox_repo.get_unpublished(limit=10)
        assert len(unpublished) == 1
        assert unpublished[0].event_type == "DocumentProcessed"

    def test_save_multiple_events_fifo(self, outbox_repo: InMemoryOutboxRepository) -> None:
        """Multiple events should be saved and returned in FIFO order."""
        events = [
            DomainEvent(
                event_id=uuid4(),
                event_type="ToolExecuted",
                source="test",
                aggregate_id=uuid4(),
                aggregate_type="Tool",
                version=i,
                payload={"tool_id": f"tool-{i}"},
            )
            for i in range(3)
        ]
        for e in events:
            outbox_repo.save(e)

        unpublished = outbox_repo.get_unpublished(limit=10)
        assert len(unpublished) == 3
        # FIFO order
        assert unpublished[0].version == 0
        assert unpublished[1].version == 1
        assert unpublished[2].version == 2

    def test_mark_published_event(self, outbox_repo: InMemoryOutboxRepository) -> None:
        """After marking published, event should not appear in unpublished."""
        event = DomainEvent(
            event_id=uuid4(),
            event_type="AgentDecided",
            source="test",
            aggregate_id=uuid4(),
            aggregate_type="Agent",
            version=1,
            payload={},
        )
        outbox_repo.save(event)
        outbox_repo.mark_published(event.event_id)

        unpublished = outbox_repo.get_unpublished(limit=10)
        assert len(unpublished) == 0

    def test_event_format_standard(self, outbox_repo: InMemoryOutboxRepository) -> None:
        """Published event should have all standard fields."""
        event_id = uuid4()
        aggregate_id = uuid4()
        event = DomainEvent(
            event_id=event_id,
            event_type="CheckpointReached",
            source="test",
            aggregate_id=aggregate_id,
            aggregate_type="Checkpoint",
            version=1,
            payload={"stage": "market_insight"},
        )
        outbox_repo.save(event)

        unpublished = outbox_repo.get_unpublished(limit=10)
        assert len(unpublished) == 1
        evt = unpublished[0]
        assert evt.event_id == event_id
        assert evt.event_type == "CheckpointReached"
        assert evt.aggregate_id == aggregate_id
        assert evt.aggregate_type == "Checkpoint"
        assert evt.version == 1


# ===================================================================
# TDD Cycle B: Event Type Registry
# ===================================================================


class TestEventRegistry:
    """Verify event type registry correctly deserializes events."""

    def test_event_roundtrip_via_outbox_adapter(self) -> None:
        """Event should roundtrip correctly through EventOutboxAdapter."""
        event_id = uuid4()
        event = DomainEvent(
            event_id=event_id,
            event_type="DocumentProcessed",
            source="test",
            aggregate_id=uuid4(),
            aggregate_type="Document",
            version=1,
            payload={"doc_id": "test-1"},
        )

        # Serialize to entity
        from src.infrastructure.messaging.adapters.event_outbox_adapter import EventOutboxAdapter

        entity = EventOutboxAdapter.from_domain_event(event)
        assert entity.event_id == event_id
        assert entity.event_type == "DocumentProcessed"

        # Deserialize back
        restored = EventOutboxAdapter.to_domain_event(entity)
        assert restored.event_id == event_id
        assert restored.event_type == "DocumentProcessed"
        assert restored.payload["doc_id"] == "test-1"

    def test_unknown_event_type_raises_value_error(self) -> None:
        """EventOutboxAdapter should raise ValueError for unknown event_type."""
        from src.infrastructure.messaging.outbox.outbox import OutboxEntity

        # Create an entity with an unregistered event_type
        unknown_entity = OutboxEntity()
        unknown_entity.event_id = uuid4()
        unknown_entity.event_type = "UnknownEventType"
        unknown_entity.payload = {"some": "data"}

        with pytest.raises(ValueError, match="Unknown event_type"):
            EventOutboxAdapter.to_domain_event(unknown_entity)


# ===================================================================
# TDD Cycle C: Idempotency & Retry Smoke
# ===================================================================


class TestIdempotencyAndRetry:
    """Verify idempotency checker and retry policy at smoke level."""

    @pytest.mark.asyncio
    async def test_idempotency_try_acquire_atomic(self, idempotency_checker: IdempotencyChecker, event_id: UUID) -> None:
        """try_acquire should be atomic — only first call succeeds."""
        assert await idempotency_checker.try_acquire(event_id) is True
        assert await idempotency_checker.try_acquire(event_id) is False

    @pytest.mark.asyncio
    async def test_idempotency_different_events_independent(self, idempotency_checker: IdempotencyChecker) -> None:
        """Different event IDs should be independent."""
        id1 = uuid4()
        id2 = uuid4()
        assert await idempotency_checker.try_acquire(id1) is True
        assert await idempotency_checker.try_acquire(id2) is True
        assert await idempotency_checker.try_acquire(id1) is False
        assert await idempotency_checker.try_acquire(id2) is False

    def test_retry_policy_exponential_backoff(self, retry_policy: RetryPolicy) -> None:
        """Retry delays should follow exponential backoff pattern."""
        # Use average to account for jitter
        avg_0 = sum(retry_policy.get_delay(0) for _ in range(10)) / 10
        avg_1 = sum(retry_policy.get_delay(1) for _ in range(10)) / 10
        avg_2 = sum(retry_policy.get_delay(2) for _ in range(10)) / 10

        assert avg_1 > avg_0
        assert avg_2 > avg_1

    def test_retry_policy_max_delay_cap(self, retry_policy: RetryPolicy) -> None:
        """Retry delays should never exceed max_delay."""
        for i in range(50):
            delay = retry_policy.get_delay(i)
            assert delay <= retry_policy.max_delay, f"delay {delay} > max {retry_policy.max_delay} at retry {i}"

    def test_retry_policy_should_retry_below_max(self, retry_policy: RetryPolicy) -> None:
        """should_retry should return True when below max_retries."""
        assert retry_policy.should_retry(0) is True
        assert retry_policy.should_retry(2) is True
        assert retry_policy.should_retry(3) is False
