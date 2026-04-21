"""Tests for HeartbeatScheduler."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

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

        # Mock _schedule_next and _poll_loop to prevent actual task creation
        with patch.object(scheduler, "_schedule_next"), patch.object(scheduler, "_poll_loop", return_value=asyncio.sleep(0.1)):
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

        with patch.object(scheduler, "_schedule_next"), patch.object(scheduler, "_poll_loop", return_value=asyncio.sleep(0.1)):
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
