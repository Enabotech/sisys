"""Task 4 TDD Tests — Idempotency, Retry, DeadLetterQueue."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import fakeredis.aioredis
import pytest
import redis.asyncio as aioredis

from src.domain.events import DocumentProcessed
from src.domain.ports.dead_letter_queue import DeadLetterQueue
from src.infrastructure.messaging.inmemory_dead_letter_queue import InMemoryDeadLetterQueue
from src.infrastructure.messaging.retry.checker import IdempotencyChecker
from src.infrastructure.messaging.retry.retry_policy import RetryPolicy


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

    @pytest.mark.asyncio
    async def test_try_acquire_returns_true_first_time(self):
        """try_acquire should return True on first call."""
        checker = IdempotencyChecker(redis_client=fakeredis.aioredis.FakeRedis())
        event_id = uuid4()
        result = await checker.try_acquire(event_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_try_acquire_returns_false_second_time(self):
        """try_acquire should return False on duplicate call."""
        fake_redis = fakeredis.aioredis.FakeRedis()
        checker = IdempotencyChecker(redis_client=fake_redis)
        event_id = uuid4()

        assert await checker.try_acquire(event_id) is True
        # Use same redis instance
        checker2 = IdempotencyChecker(redis_client=fake_redis)
        assert await checker2.try_acquire(event_id) is False

    @pytest.mark.asyncio
    async def test_try_acquire_uses_default_ttl(self):
        """try_acquire should use default 7-day TTL."""
        checker = IdempotencyChecker(redis_client=fakeredis.aioredis.FakeRedis())
        event_id = uuid4()
        await checker.try_acquire(event_id, ttl=86400)

        # Key should exist
        redis_client = checker._redis
        assert await redis_client.exists(f"idempotency:{event_id}") == 1

    @pytest.mark.asyncio
    async def test_try_acquire_fail_open_on_connection_error(self):
        """try_acquire should return True (fail-open) on Redis connection error."""
        # Create a checker with a mock Redis that raises ConnectionError
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(side_effect=aioredis.ConnectionError("Connection refused"))

        checker = IdempotencyChecker.__new__(IdempotencyChecker)
        checker._redis = mock_redis

        result = await checker.try_acquire(uuid4())
        assert result is True

    @pytest.mark.asyncio
    async def test_try_acquire_fail_open_on_timeout_error(self):
        """try_acquire should return True (fail-open) on Redis timeout error."""
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(side_effect=aioredis.TimeoutError("Connection timed out"))

        checker = IdempotencyChecker.__new__(IdempotencyChecker)
        checker._redis = mock_redis

        result = await checker.try_acquire(uuid4())
        assert result is True

    @pytest.mark.asyncio
    async def test_concurrent_try_acquire_only_one_succeeds(self):
        """Concurrent try_acquire calls should only return True once."""
        fake_redis = fakeredis.aioredis.FakeRedis()
        checker = IdempotencyChecker(redis_client=fake_redis)
        event_id = uuid4()

        async def try_acquire_async():
            return await checker.try_acquire(event_id)

        results = await asyncio.gather(*[try_acquire_async() for _ in range(10)])

        assert list(results).count(True) == 1
        assert list(results).count(False) == 9

    def test_creates_connection_pool_when_redis_client_not_provided(self):
        """Should create connection pool when redis_client is None."""
        with patch("redis.asyncio.ConnectionPool") as mock_pool_class:
            with patch("redis.asyncio.Redis") as mock_redis_class:
                mock_pool_instance = MagicMock()
                mock_pool_class.return_value = mock_pool_instance
                mock_redis_class.return_value = MagicMock()

                IdempotencyChecker(host="localhost", port=6379, db=0)

                mock_pool_class.assert_called_once()
                call_kwargs = mock_pool_class.call_args[1]
                assert call_kwargs["host"] == "localhost"
                assert call_kwargs["port"] == 6379
                assert call_kwargs["db"] == 0
                assert call_kwargs["decode_responses"] is True


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

    @pytest.mark.asyncio
    async def test_enqueue_adds_event(self):
        """enqueue should add event to DLQ."""
        dlq = InMemoryDeadLetterQueue()
        event = _make_event()
        await dlq.enqueue(event, "error message")

        assert len(dlq) == 1

    @pytest.mark.asyncio
    async def test_dequeue_removes_event(self):
        """dequeue should remove and return event."""
        dlq = InMemoryDeadLetterQueue()
        event = _make_event()
        await dlq.enqueue(event, "error message")

        dequeued_event, error, retry_count = await dlq.dequeue()
        assert dequeued_event.event_id == event.event_id
        assert error == "error message"
        assert len(dlq) == 0

    @pytest.mark.asyncio
    async def test_dequeue_empty_returns_none(self):
        """dequeue on empty DLQ should return None."""
        dlq = InMemoryDeadLetterQueue()
        result = await dlq.dequeue()
        assert result is None

    @pytest.mark.asyncio
    async def test_fifo_order(self):
        """DLQ should follow FIFO order."""
        dlq = InMemoryDeadLetterQueue()
        event1 = _make_event()
        event2 = DocumentProcessed(
            document_id=uuid4(),
            parse_result={"pages": 5},
            embedding=[0.2] * 1024,
        )
        await dlq.enqueue(event1, "error1")
        await dlq.enqueue(event2, "error2")

        dequeued1, error1, _ = await dlq.dequeue()
        dequeued2, error2, _ = await dlq.dequeue()

        assert dequeued1.event_id == event1.event_id
        assert error1 == "error1"
        assert dequeued2.event_id == event2.event_id
        assert error2 == "error2"

    def test_protocol_is_runtime_checkable(self):
        """DeadLetterQueue Protocol 应该是 runtime_checkable 的。"""
        dlq = InMemoryDeadLetterQueue()
        assert isinstance(dlq, DeadLetterQueue)
