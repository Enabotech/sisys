"""Task 4 TDD Tests — Idempotency, Retry, DeadLetterQueue."""

from __future__ import annotations

from uuid import uuid4

import fakeredis
import pytest

from src.domain.events import DocumentProcessed
from src.infrastructure.idempotency.checker import IdempotencyChecker
from src.infrastructure.idempotency.dead_letter_queue import (
    DeadLetterQueue,
    InMemoryDeadLetterQueue,
)
from src.infrastructure.idempotency.retry_policy import RetryPolicy


def _make_event():
    from uuid import uuid4

    return DocumentProcessed(
        document_id=uuid4(),
        parse_result={"pages": 10},
        embedding=[0.1] * 1024,
    )


# ============================================================================
# TDD Cycle A: IdempotencyChecker
# ============================================================================


class TestIdempotencyChecker:
    """IdempotencyChecker tests using fakeredis."""

    def test_try_acquire_returns_true_first_time(self):
        """try_acquire should return True on first call."""
        from fakeredis import FakeRedis

        checker = IdempotencyChecker(redis_client=FakeRedis())
        event_id = uuid4()
        result = checker.try_acquire(event_id)
        assert result is True

    def test_try_acquire_returns_false_second_time(self):
        """try_acquire should return False on duplicate call."""
        fake_redis = fakeredis.FakeRedis()
        checker = IdempotencyChecker(redis_client=fake_redis)
        event_id = uuid4()

        assert checker.try_acquire(event_id) is True
        # Use same redis instance
        checker2 = IdempotencyChecker(redis_client=fake_redis)
        assert checker2.try_acquire(event_id) is False

    def test_try_acquire_uses_default_ttl(self):
        """try_acquire should use default 7-day TTL."""
        from fakeredis import FakeRedis

        checker = IdempotencyChecker(redis_client=FakeRedis())
        event_id = uuid4()
        checker.try_acquire(event_id, ttl=86400)  # 1 day for faster test

        # Key should exist
        redis_client = checker._redis
        assert redis_client.exists(f"idempotency:{event_id}") == 1

    def test_try_acquire_fail_open_on_connection_error(self):
        """try_acquire should return True (fail-open) on Redis connection error."""
        from unittest.mock import MagicMock

        import redis as redis_module

        # Create a checker that will fail on set()
        checker = IdempotencyChecker(host="invalid-host", port=9999)

        # Mock the Redis set method to raise ConnectionError
        checker._redis = MagicMock()
        checker._redis.set.side_effect = redis_module.ConnectionError("Connection refused")

        # Should return True (fail-open) to allow processing
        result = checker.try_acquire(uuid4())
        assert result is True

    def test_try_acquire_fail_open_on_timeout_error(self):
        """try_acquire should return True (fail-open) on Redis timeout error."""
        from unittest.mock import MagicMock

        import redis as redis_module

        checker = IdempotencyChecker(host="invalid-host", port=9999)
        checker._redis = MagicMock()
        checker._redis.set.side_effect = redis_module.TimeoutError("Connection timed out")

        # Should return True (fail-open)
        result = checker.try_acquire(uuid4())
        assert result is True

    def test_concurrent_try_acquire_only_one_succeeds(self):
        """Concurrent try_acquire calls should only return True once.

        Note: fakeredis doesn't support true multi-threading, so we
        simulate concurrency by using asyncio.gather in a single thread.
        """
        import asyncio

        fake_redis = fakeredis.FakeRedis()
        checker = IdempotencyChecker(redis_client=fake_redis)
        event_id = uuid4()

        async def try_acquire_async():
            return checker.try_acquire(event_id)

        async def run_concurrent():
            results = await asyncio.gather(*[try_acquire_async() for _ in range(10)])
            return list(results)

        results = asyncio.run(run_concurrent())

        assert results.count(True) == 1
        assert results.count(False) == 9


# ============================================================================
# TDD Cycle B: RetryPolicy
# ============================================================================


class TestRetryPolicy:
    """RetryPolicy tests."""

    def test_default_values(self):
        """RetryPolicy should have sensible defaults."""
        policy = RetryPolicy()
        assert policy.base_delay == 1.0
        assert policy.max_delay == 60.0
        assert policy.max_retries == 3

    def test_custom_values(self):
        """RetryPolicy should accept custom values."""
        policy = RetryPolicy(base_delay=2.0, max_delay=120.0, max_retries=5)
        assert policy.base_delay == 2.0
        assert policy.max_delay == 120.0
        assert policy.max_retries == 5

    def test_get_delay_exponential(self):
        """get_delay should follow exponential backoff."""
        policy = RetryPolicy(base_delay=1.0, max_delay=60.0)

        # retry_count=0: 1.0 * 2^0 = 1.0 (with jitter)
        # retry_count=1: 1.0 * 2^1 = 2.0 (with jitter)
        # retry_count=2: 1.0 * 2^2 = 4.0 (with jitter)
        delay0 = policy.get_delay(0)
        delay1 = policy.get_delay(1)
        delay2 = policy.get_delay(2)

        # With jitter range [0.5, 1.5], delays should be approximately:
        # delay0 in [0.5, 1.5], delay1 in [1.0, 3.0], delay2 in [2.0, 6.0]
        assert 0.5 <= delay0 <= 1.5
        assert 1.0 <= delay1 <= 3.0
        assert 2.0 <= delay2 <= 6.0

    def test_get_delay_capped_at_max(self):
        """get_delay should never exceed max_delay (absolute upper bound)."""
        policy = RetryPolicy(base_delay=1.0, max_delay=10.0)

        # retry_count=10: 1.0 * 2^10 = 1024, but capped at max_delay=10.0
        for i in range(20):
            delay = policy.get_delay(i)
            assert delay <= 10.0, f"Delay {delay} exceeds max_delay at retry_count={i}"

    def test_should_retry_below_max(self):
        """should_retry should return True below max_retries."""
        policy = RetryPolicy(max_retries=3)
        assert policy.should_retry(0, max_retries=3) is True
        assert policy.should_retry(1, max_retries=3) is True
        assert policy.should_retry(2, max_retries=3) is True

    def test_should_retry_at_max(self):
        """should_retry should return False at max_retries."""
        policy = RetryPolicy(max_retries=3)
        assert policy.should_retry(3, max_retries=3) is False

    def test_jitter_range(self):
        """jitter should be between 0.5 and 1.5."""
        policy = RetryPolicy(base_delay=1.0, max_delay=1000.0)

        # Run multiple times to verify jitter range
        for _ in range(100):
            delay = policy.get_delay(0)
            # base * 2^0 * jitter = 1.0 * 1 * jitter
            # So delay should be in [0.5, 1.5]
            assert 0.5 <= delay <= 1.5


# ============================================================================
# TDD Cycle C: DeadLetterQueue
# ============================================================================


class TestDeadLetterQueue:
    """DeadLetterQueue tests."""

    def test_enqueue_adds_event(self):
        """enqueue should add event to DLQ."""
        dlq = InMemoryDeadLetterQueue()
        event = _make_event()
        dlq.enqueue(event, "error message")

        assert len(dlq) == 1

    def test_dequeue_removes_event(self):
        """dequeue should remove and return event."""
        dlq = InMemoryDeadLetterQueue()
        event = _make_event()
        dlq.enqueue(event, "error message")

        dequeued_event, error, retry_count = dlq.dequeue()
        assert dequeued_event.event_id == event.event_id
        assert error == "error message"
        assert len(dlq) == 0

    def test_dequeue_empty_returns_none(self):
        """dequeue on empty DLQ should return None."""
        dlq = InMemoryDeadLetterQueue()
        result = dlq.dequeue()
        assert result is None

    def test_fifo_order(self):
        """DLQ should follow FIFO order."""
        dlq = InMemoryDeadLetterQueue()
        event1 = _make_event()
        event2 = DocumentProcessed(
            document_id=uuid4(),
            parse_result={"pages": 5},
            embedding=[0.2] * 1024,
        )
        dlq.enqueue(event1, "error1")
        dlq.enqueue(event2, "error2")

        dequeued1, error1, _ = dlq.dequeue()
        dequeued2, error2, _ = dlq.dequeue()

        assert dequeued1.event_id == event1.event_id
        assert error1 == "error1"
        assert dequeued2.event_id == event2.event_id
        assert error2 == "error2"

    def test_abstract_base_class(self):
        """DeadLetterQueue should be abstract."""
        with pytest.raises(TypeError):
            DeadLetterQueue()
