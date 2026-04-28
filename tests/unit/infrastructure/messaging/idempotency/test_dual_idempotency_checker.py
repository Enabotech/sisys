"""Task 3 TDD Tests — DualIdempotencyChecker."""

from __future__ import annotations

from unittest import mock
from uuid import uuid4

import fakeredis.aioredis
import pytest
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.messaging.idempotency.dual_idempotency_checker import (
    DEFAULT_TTL,
    IDEMPOTENCY_TABLE,
    DualIdempotencyChecker,
    IdempotencyRecordModel,
)


@pytest.fixture
async def redis_client():
    """Provide a fakeredis client for testing."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
def mock_session():
    """Mock AsyncSession for testing."""
    session = mock.AsyncMock(spec=AsyncSession)
    session.execute = mock.AsyncMock()
    session.execute.return_value.rowcount = 1
    return session


@pytest.fixture
def checker(redis_client, mock_session):
    """Provide a DualIdempotencyChecker with mocks."""
    return DualIdempotencyChecker(redis_client=redis_client, session=mock_session)


# ============================================================================
# TDD Cycle A: DualIdempotencyChecker
# ============================================================================


class TestIdempotencyRecordModel:
    """IdempotencyRecordModel tests."""

    def test_create_table_sql(self):
        """Should return valid CREATE TABLE SQL."""
        sql = IdempotencyRecordModel.create_table_sql()
        assert "CREATE TABLE" in sql
        assert IDEMPOTENCY_TABLE in sql
        assert "event_id" in sql
        assert "processed_at" in sql


class TestDualIdempotencyChecker:
    """DualIdempotencyChecker tests."""

    @pytest.mark.asyncio
    async def test_try_acquire_returns_true_first_time(self, checker):
        """try_acquire should return True on first call."""
        event_id = uuid4()
        result = await checker.try_acquire(event_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_try_acquire_returns_false_second_time(self, checker, redis_client):
        """try_acquire should return False on duplicate call."""
        event_id = uuid4()

        # First call - should succeed
        assert await checker.try_acquire(event_id) is True

        # Second call with same event_id - should fail
        assert await checker.try_acquire(event_id) is False

    @pytest.mark.asyncio
    async def test_try_acquire_uses_correct_redis_key(self, checker, redis_client):
        """try_acquire should use correct Redis key format."""
        event_id = uuid4()
        expected_key = f"idempotency:{event_id}"

        await checker.try_acquire(event_id)

        # Verify key exists in Redis
        exists = await redis_client.exists(expected_key)
        assert exists == 1

    @pytest.mark.asyncio
    async def test_try_acquire_uses_default_ttl(self, checker, redis_client):
        """try_acquire should use default 7-day TTL."""
        event_id = uuid4()

        await checker.try_acquire(event_id)

        # Verify TTL is set
        key = f"idempotency:{event_id}"
        ttl = await redis_client.ttl(key)
        # TTL should be close to DEFAULT_TTL (allow small difference)
        assert ttl > 0
        assert ttl <= DEFAULT_TTL

    @pytest.mark.asyncio
    async def test_try_acquire_falls_back_to_postgresql_on_redis_error(self, redis_client, mock_session):
        """try_acquire should fall back to PostgreSQL when Redis fails."""
        event_id = uuid4()

        # Create checker with a mock that raises RedisError
        async def redis_error(*args, **kwargs):
            raise aioredis.RedisError("Connection refused")

        bad_redis = mock.AsyncMock()
        bad_redis.set = redis_error

        checker = DualIdempotencyChecker(redis_client=bad_redis, session=mock_session)

        result = await checker.try_acquire(event_id)

        # Should fall back to PostgreSQL and succeed
        assert result is True
        mock_session.execute.assert_called()

    @pytest.mark.asyncio
    async def test_is_processed_checks_redis_first(self, checker, redis_client, mock_session):
        """is_processed should check Redis first."""
        event_id = uuid4()

        # Setup mock for PostgreSQL fallback (not processed)
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        # Not processed yet
        assert await checker.is_processed(event_id) is False

        # Acquire lock
        await checker.try_acquire(event_id)

        # Setup mock for PostgreSQL fallback (processed)
        mock_result.scalar_one_or_none.return_value = True
        mock_session.execute.return_value = mock_result

        # Now should be processed
        assert await checker.is_processed(event_id) is True

    @pytest.mark.asyncio
    async def test_is_processed_falls_back_to_postgresql_on_redis_error(self, redis_client, mock_session):
        """is_processed should fall back to PostgreSQL when Redis fails."""
        event_id = uuid4()

        # Create checker with a mock that raises RedisError
        async def redis_error(*args, **kwargs):
            raise aioredis.RedisError("Connection refused")

        bad_redis = mock.AsyncMock()
        bad_redis.exists = redis_error

        # Setup mock to return None (not in PostgreSQL)
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        checker = DualIdempotencyChecker(redis_client=bad_redis, session=mock_session)

        result = await checker.is_processed(event_id)

        # Should fall back to PostgreSQL
        assert result is False

    @pytest.mark.asyncio
    async def test_try_acquire_writes_to_postgresql_on_success(self, checker, mock_session):
        """try_acquire should write to PostgreSQL after Redis success."""
        event_id = uuid4()

        await checker.try_acquire(event_id)

        # Verify PostgreSQL write was attempted
        mock_session.execute.assert_called()

    @pytest.mark.asyncio
    async def test_idempotency_record_model_table_name(self):
        """IdempotencyRecordModel should use correct table name."""
        assert IdempotencyRecordModel.__tablename__ == IDEMPOTENCY_TABLE
