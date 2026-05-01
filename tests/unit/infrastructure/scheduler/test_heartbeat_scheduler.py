"""Tests for HeartbeatScheduler - pure asyncio implementation."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.events.heartbeat_events import HeartbeatTriggered
from src.infrastructure.config.redis import RedisConfig
from src.infrastructure.scheduler.heartbeat_scheduler import HeartbeatScheduler


class TestHeartbeatSchedulerCreation:
    """Test HeartbeatScheduler instantiation and configuration."""

    def test_heartbeat_scheduler_default_interval(self) -> None:
        """Verify default heartbeat interval is 60 seconds."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config)

        assert scheduler._interval_seconds == 60

    def test_heartbeat_scheduler_custom_interval(self) -> None:
        """Verify custom interval is respected."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config, interval_seconds=120)

        assert scheduler._interval_seconds == 120

    def test_heartbeat_scheduler_not_running_initially(self) -> None:
        """Verify scheduler is not running on creation."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config)

        assert scheduler._running is False


class TestHeartbeatSchedulerLifecycle:
    """Test HeartbeatScheduler start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_sets_running_flag(self) -> None:
        """Verify start() sets running flag to True."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config)

        await scheduler.start()

        assert scheduler._running is True
        assert scheduler._heartbeat_task is not None

        # Cleanup
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_clears_running_flag(self) -> None:
        """Verify stop() sets running flag to False."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config)
        scheduler._running = True
        scheduler._heartbeat_task = None

        await scheduler.stop()

        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_double_start_no_op(self) -> None:
        """Verify starting twice is a no-op."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config)

        await scheduler.start()
        assert scheduler._running is True

        # Second start should be no-op
        await scheduler.start()

        # Cleanup
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_already_stopped_no_op(self) -> None:
        """Verify stop() on already stopped scheduler is no-op."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config)
        scheduler._running = False

        # Should not raise
        await scheduler.stop()

        assert scheduler._running is False


class TestHeartbeatSchedulerHeartbeatLoop:
    """Test _heartbeat_loop method."""

    @pytest.mark.asyncio
    async def test_heartbeat_loop_fires_periodically(self) -> None:
        """Verify _heartbeat_loop fires heartbeat at interval."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config, interval_seconds=1)
        scheduler._running = True

        fire_count = 0

        async def mock_fire():
            nonlocal fire_count
            fire_count += 1
            if fire_count >= 2:
                scheduler._running = False

        with patch.object(scheduler, "_fire_heartbeat", side_effect=mock_fire):
            await scheduler._heartbeat_loop()

        assert fire_count >= 2

    @pytest.mark.asyncio
    async def test_heartbeat_loop_respects_running_flag(self) -> None:
        """Verify _heartbeat_loop exits when _running becomes False."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config, interval_seconds=1)
        scheduler._running = True

        fire_count = 0

        async def mock_fire():
            nonlocal fire_count
            fire_count += 1
            # Exit after first fire to avoid long-running loop
            scheduler._running = False

        with patch.object(scheduler, "_fire_heartbeat", side_effect=mock_fire):
            with patch("asyncio.sleep", AsyncMock()):
                await scheduler._heartbeat_loop()

        assert fire_count == 1

    @pytest.mark.asyncio
    async def test_heartbeat_loop_handles_cancellation(self) -> None:
        """Verify _heartbeat_loop handles cancellation gracefully."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config, interval_seconds=1)
        scheduler._running = True

        async def mock_fire():
            await asyncio.sleep(0.01)  # Brief delay

        with patch.object(scheduler, "_fire_heartbeat", side_effect=mock_fire):
            with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
                # Simulate cancellation after first sleep
                async def cancel_after_first(delay):
                    if mock_sleep.call_count < 1:
                        raise asyncio.CancelledError()
                    scheduler._running = False

                mock_sleep.side_effect = cancel_after_first
                # Should not raise, should exit cleanly
                await scheduler._heartbeat_loop()


class TestHeartbeatSchedulerFireHeartbeat:
    """Test _fire_heartbeat method."""

    @pytest.mark.asyncio
    async def test_fire_heartbeat_generates_event(self) -> None:
        """Verify _fire_heartbeat generates HeartbeatTriggered event."""
        config = RedisConfig()
        mock_publisher = AsyncMock()
        scheduler = HeartbeatScheduler(
            redis_config=config,
            interval_seconds=60,
            publisher=mock_publisher,
        )

        with patch.object(scheduler, "_store_heartbeat", AsyncMock()):
            await scheduler._fire_heartbeat()

        mock_publisher.assert_called_once()
        call_args = mock_publisher.call_args
        event = call_args[0][0]
        assert isinstance(event, HeartbeatTriggered)
        assert event.wake_reason == "scheduled"

    @pytest.mark.asyncio
    async def test_fire_heartbeat_no_publisher(self) -> None:
        """Verify _fire_heartbeat handles missing publisher gracefully."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(
            redis_config=config,
            interval_seconds=60,
            publisher=None,
        )

        with patch.object(scheduler, "_store_heartbeat", AsyncMock()):
            # Should not raise even without publisher
            await scheduler._fire_heartbeat()

    @pytest.mark.asyncio
    async def test_fire_heartbeat_stores_heartbeat(self) -> None:
        """Verify _fire_heartbeat calls _store_heartbeat."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config, interval_seconds=60)

        with patch.object(scheduler, "_store_heartbeat", AsyncMock()) as mock_store:
            await scheduler._fire_heartbeat()
            mock_store.assert_called_once()

    def test_heartbeat_key_constant(self) -> None:
        """Verify the heartbeat Redis key constant is correct."""
        assert HeartbeatScheduler._HEARTBEAT_KEY == "heartbeat:pending"


class TestHeartbeatSchedulerGetPool:
    """Test _get_pool method coverage."""

    @pytest.mark.asyncio
    async def test_get_pool_returns_existing_pool(self) -> None:
        """Verify _get_pool returns cached pool."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config)
        mock_pool = MagicMock()
        scheduler._pool = mock_pool

        result = await scheduler._get_pool()

        assert result is mock_pool


class TestHeartbeatSchedulerRedisOperations:
    """Tests for Redis operations with proper mocking."""

    @pytest.fixture
    def mock_redis_client(self):
        """Create a mock Redis client that supports async context manager."""
        client = MagicMock()
        client.zadd = AsyncMock()
        client.expire = AsyncMock()
        client.ping = AsyncMock()

        # Make it work as async context manager
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        return client

    @pytest.mark.asyncio
    async def test_store_heartbeat_calls_zadd_and_expire(self, mock_redis_client) -> None:
        """Verify _store_heartbeat calls Redis zadd and expire."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config, interval_seconds=60)
        heartbeat_id = uuid.uuid4()
        timestamp = datetime.now(UTC)

        with patch("redis.asyncio.Redis", return_value=mock_redis_client):
            with patch.object(scheduler, "_get_pool", AsyncMock()):
                await scheduler._store_heartbeat(heartbeat_id, timestamp)

        mock_redis_client.zadd.assert_called_once()
        mock_redis_client.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_heartbeat_handles_exception(self, mock_redis_client) -> None:
        """Verify _store_heartbeat handles Redis exceptions gracefully."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config, interval_seconds=60)
        heartbeat_id = uuid.uuid4()
        timestamp = datetime.now(UTC)

        mock_redis_client.zadd = AsyncMock(side_effect=Exception("Redis error"))

        with patch("redis.asyncio.Redis", return_value=mock_redis_client):
            with patch.object(scheduler, "_get_pool", AsyncMock()):
                # Should not raise, just log error
                await scheduler._store_heartbeat(heartbeat_id, timestamp)

    @pytest.mark.asyncio
    async def test_schedule_heartbeat_calls_redis_zadd(self, mock_redis_client) -> None:
        """Verify schedule_heartbeat calls Redis zadd."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config, interval_seconds=60)
        heartbeat_id = uuid.uuid4()

        with patch("redis.asyncio.Redis", return_value=mock_redis_client):
            with patch.object(scheduler, "_get_pool", AsyncMock()):
                await scheduler.schedule_heartbeat(heartbeat_id, delay_seconds=30)

        mock_redis_client.zadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_heartbeat_handles_exception(self, mock_redis_client) -> None:
        """Verify schedule_heartbeat handles Redis exceptions."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config, interval_seconds=60)
        heartbeat_id = uuid.uuid4()

        mock_redis_client.zadd = AsyncMock(side_effect=Exception("Redis error"))

        with patch("redis.asyncio.Redis", return_value=mock_redis_client):
            with patch.object(scheduler, "_get_pool", AsyncMock()):
                with pytest.raises(Exception):
                    await scheduler.schedule_heartbeat(heartbeat_id, delay_seconds=30)

    @pytest.mark.asyncio
    async def test_get_pool_creates_connection(self, mock_redis_client) -> None:
        """Verify _get_pool creates new connection pool."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config)

        mock_pool = MagicMock()

        with patch("redis.asyncio.ConnectionPool", return_value=mock_pool):
            with patch("redis.asyncio.Redis", return_value=mock_redis_client):
                result = await scheduler._get_pool()

                assert result is mock_pool
                assert scheduler._pool is mock_pool

    @pytest.mark.asyncio
    async def test_get_pool_handles_connection_error(self) -> None:
        """Verify _get_pool handles connection errors."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config)

        with patch("redis.asyncio.ConnectionPool", side_effect=Exception("Connection failed")):
            with pytest.raises(ConnectionError):
                await scheduler._get_pool()

        assert scheduler._pool is None


class TestHeartbeatSchedulerStop:
    """Test stop method coverage."""

    @pytest.mark.asyncio
    async def test_stop_cancels_heartbeat_task(self) -> None:
        """Verify stop() cancels heartbeat task."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config, interval_seconds=30)
        scheduler._running = True

        # Create a mock task that returns a coroutine
        async def mock_coro():
            await asyncio.sleep(3600)

        scheduler._heartbeat_task = asyncio.create_task(mock_coro())

        await scheduler.stop()

        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_stop_with_no_task(self) -> None:
        """Verify stop() handles case with no heartbeat task."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config)
        scheduler._running = True
        scheduler._heartbeat_task = None

        # Should not raise
        await scheduler.stop()

        assert scheduler._running is False
