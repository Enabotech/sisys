"""Smoke tests for domain event pipeline (event registry, idempotency, retry).

Verifies Story 1.2/1.3 event infrastructure works end-to-end at a basic level.
Does NOT test full RabbitMQ routing — that's Story 1.3 AC-3 scope.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from src.domain.events.base import DomainEvent
from src.infrastructure.messaging.adapters.event_outbox_adapter import EventOutboxAdapter
from src.infrastructure.messaging.retry.checker import IdempotencyChecker
from src.infrastructure.messaging.retry.retry_policy import RetryPolicy

# ===================================================================
# TDD Cycle A: Event Type Registry
# ===================================================================


class TestEventRegistry:
    """Verify DomainEvent._registry correctly deserializes events."""

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

    def test_registry_contains_known_types(self) -> None:
        """DomainEvent._registry should contain known event types."""
        assert "DocumentProcessed" in DomainEvent._registry
        assert DomainEvent._registry["DocumentProcessed"] is not None

    def test_registry_get_returns_none_for_unknown(self) -> None:
        """DomainEvent._registry.get should return None for unknown type."""
        result = DomainEvent._registry.get("NonExistentType")
        assert result is None


# ===================================================================
# TDD Cycle B: Idempotency & Retry Smoke
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
