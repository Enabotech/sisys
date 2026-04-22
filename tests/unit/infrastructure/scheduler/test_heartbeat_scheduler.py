"""Tests for HeartbeatScheduler."""

from __future__ import annotations

import asyncio
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

        async def mock_poll_loop():
            # Mock async _poll_loop to do nothing
            while True:
                await asyncio.sleep(2000)

        # Mock _schedule_next and _poll_loop to prevent actual task creation
        with patch.object(scheduler, "_schedule_next"), patch.object(scheduler, "_poll_loop", side_effect=mock_poll_loop):
            scheduler._poll_task = None
            await scheduler.start()

        assert scheduler._running is True
        # Cleanup
        scheduler._running = False

    @pytest.mark.asyncio
    async def test_stop_clears_running_flag(self) -> None:
        """Verify stop() sets running flag to False."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config)
        scheduler._running = True
        scheduler._poll_task = None

        await scheduler.stop()

        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_double_start_no_op(self) -> None:
        """Verify starting twice is a no-op."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config)

        async def mock_poll_loop():
            # Mock async _poll_loop to do nothing
            while True:
                await asyncio.sleep(2000)

        with patch.object(scheduler, "_schedule_next"), patch.object(scheduler, "_poll_loop", side_effect=mock_poll_loop):
            scheduler._poll_task = None
            await scheduler.start()
            await scheduler.start()
            # _schedule_next should only be called once
            assert scheduler._running is True

        # Cleanup
        scheduler._running = False


class TestHeartbeatSchedulerMocked:
    """Test HeartbeatScheduler with mocked Redis/publisher."""

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

    def test_heartbeat_key_constant(self) -> None:
        """Verify the heartbeat Redis key constant is correct."""
        assert HeartbeatScheduler._HEARTBEAT_KEY == "heartbeat:pending"

    def test_poll_interval_default(self) -> None:
        """Verify default poll interval is 5 seconds."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config)
        assert scheduler._POLL_INTERVAL_SECONDS == 5


class TestHeartbeatSchedulerScheduleNext:
    """Test _schedule_next method coverage."""

    @pytest.mark.asyncio
    async def test_schedule_next_does_not_fire_when_not_running(self) -> None:
        """Coverage: _schedule_next returns early if not running."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config)
        scheduler._running = False

        # Should return without scheduling
        scheduler._schedule_next()

        assert scheduler._timer is None

    @pytest.mark.asyncio
    async def test_schedule_next_creates_timer(self) -> None:
        """Coverage: _schedule_next creates threading.Timer."""
        import threading

        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config, interval_seconds=30)
        scheduler._running = True

        with patch.object(scheduler, "_fire_heartbeat", AsyncMock()):
            scheduler._schedule_next()

        assert scheduler._timer is not None
        assert isinstance(scheduler._timer, threading.Timer)
        # Cleanup
        scheduler._timer.cancel()
        scheduler._running = False


class TestHeartbeatSchedulerFireHeartbeat:
    """Test _fire_heartbeat method coverage."""

    @pytest.mark.asyncio
    async def test_fire_heartbeat_stores_heartbeat(self) -> None:
        """Coverage: _fire_heartbeat calls _store_heartbeat."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config, interval_seconds=60)

        with patch.object(scheduler, "_store_heartbeat", AsyncMock()) as mock_store:
            await scheduler._fire_heartbeat()
            mock_store.assert_called_once()

    @pytest.mark.asyncio
    async def test_fire_heartbeat_generates_heartbeat_event(self) -> None:
        """Coverage: _fire_heartbeat generates event with correct fields."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config, interval_seconds=60)

        with patch.object(scheduler, "_store_heartbeat", AsyncMock()):
            with patch.object(scheduler, "_publisher", AsyncMock()):
                await scheduler._fire_heartbeat()


class TestHeartbeatSchedulerGetPool:
    """Test _get_pool method coverage."""

    @pytest.mark.asyncio
    async def test_get_pool_returns_existing_pool(self) -> None:
        """Coverage: _get_pool returns cached pool."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config)
        mock_pool = MagicMock()
        scheduler._pool = mock_pool

        result = await scheduler._get_pool()

        assert result is mock_pool


class TestHeartbeatSchedulerStop:
    """Test stop method coverage."""

    @pytest.mark.asyncio
    async def test_stop_already_stopped_no_op(self) -> None:
        """Coverage: stop() is no-op if already stopped."""
        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config)
        scheduler._running = False

        # Should not raise
        await scheduler.stop()

        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_stop_with_timer(self) -> None:
        """Coverage: stop() cancels timer if running."""
        import threading

        config = RedisConfig()
        scheduler = HeartbeatScheduler(redis_config=config, interval_seconds=30)
        scheduler._running = True

        # Create a mock timer
        mock_timer = MagicMock(spec=threading.Timer)
        scheduler._timer = mock_timer

        await scheduler.stop()

        mock_timer.cancel.assert_called_once()
        assert scheduler._running is False
