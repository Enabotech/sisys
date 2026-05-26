"""基础设施层心跳调度器模块

使用 Redis 有序集合实现周期性心跳事件调度，采用纯 asyncio 实现
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import redis.asyncio as aioredis

from src.domain.events.heartbeat_events import HeartbeatTriggered
from src.infrastructure.config.redis import RedisConfig

logger = logging.getLogger(__name__)


class HeartbeatScheduler:
    """Schedules periodic heartbeat events using pure asyncio.

    Implementation:
    - Pure asyncio: uses asyncio.create_task() for scheduling instead of threading.Timer
    - asyncio event loop for all async operations
    - Generates HeartbeatTriggered events when timer fires
    - Redis sorted set (ZADD/ZRANGEBYSCORE) for at-least-once delivery tracking

    Architecture: Infrastructure layer, depends on Redis and EventPublisher.
    """

    _HEARTBEAT_KEY = "heartbeat:pending"

    def __init__(
        self,
        redis_config: RedisConfig,
        interval_seconds: int = 60,
        publisher: Callable[[HeartbeatTriggered], Awaitable[None]] | None = None,
    ):
        """Initialize HeartbeatScheduler.

        Args:
            redis_config: Redis connection configuration
            interval_seconds: Heartbeat interval (default 60s, configurable)
            publisher: Async callable that publishes HeartbeatTriggered events
        """
        self._redis_config = redis_config
        self._interval_seconds = interval_seconds
        self._publisher = publisher
        self._running = False
        self._heartbeat_task: asyncio.Task | None = None
        self._pool: aioredis.ConnectionPool | None = None

    async def start(self) -> None:
        """Start the heartbeat scheduler (async entry point)."""
        if self._running:
            logger.warning("HeartbeatScheduler already running")
            return

        self._running = True
        logger.info("HeartbeatScheduler started with interval=%ds", self._interval_seconds)

        # Start the heartbeat loop using pure asyncio
        loop = asyncio.get_running_loop()
        self._heartbeat_task = loop.create_task(self._heartbeat_loop())

    async def stop(self) -> None:
        """Stop the heartbeat scheduler gracefully.

        Graceful shutdown sequence:
        1. Set _running=False to signal heartbeat loop to stop
        2. Cancel the heartbeat task
        3. Clean up resources
        """
        if not self._running:
            return

        self._running = False
        logger.info("HeartbeatScheduler stopping")

        # Cancel heartbeat task
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            finally:
                self._heartbeat_task = None

        # Close Redis pool
        if self._pool:
            await self._pool.disconnect()
            self._pool = None

        logger.info("HeartbeatScheduler stopped")

    async def _heartbeat_loop(self) -> None:
        """Pure asyncio heartbeat loop - replaces threading.Timer.

        Runs every _interval_seconds, fires heartbeat and stores in Redis.
        """
        while self._running:
            try:
                await asyncio.sleep(self._interval_seconds)
            except asyncio.CancelledError:
                break

            if not self._running:
                break

            try:
                await self._fire_heartbeat()
            except Exception as e:
                logger.error("Error firing heartbeat: %s", e)

    async def _fire_heartbeat(self) -> None:
        """Generate and publish a HeartbeatTriggered event."""
        heartbeat_id = uuid.uuid4()
        now = datetime.now(UTC)

        event = HeartbeatTriggered(
            heartbeat_id=heartbeat_id,
            wake_reason="scheduled",
            todo_items=(),  # Could be populated from pending tasks
            cost_budget=0.0,  # Could be populated from cost tracking
        )

        logger.debug("Heartbeat fired: id=%s at %s", heartbeat_id, now)

        # Store in Redis sorted set for at-least-once delivery
        await self._store_heartbeat(heartbeat_id, now)

        # Publish event if publisher configured
        if self._publisher:
            try:
                await self._publisher(event)
                logger.info("HeartbeatTriggered published: id=%s", heartbeat_id)
            except Exception as e:
                logger.error("Failed to publish HeartbeatTriggered: %s", e)

    async def _store_heartbeat(self, heartbeat_id: uuid.UUID, timestamp: datetime) -> None:
        """Store heartbeat in Redis sorted set for tracking (ZADD with score=timestamp)."""
        pool = await self._get_pool()
        try:
            async with aioredis.Redis(connection_pool=pool) as client:
                score = timestamp.timestamp()
                await client.zadd(self._HEARTBEAT_KEY, {str(heartbeat_id): score})
                # Set TTL for cleanup (3x interval)
                ttl = self._interval_seconds * 3
                await client.expire(self._HEARTBEAT_KEY, ttl)
        except Exception as e:
            logger.error("Failed to store heartbeat in Redis: %s", e)

    async def _get_pool(self) -> aioredis.ConnectionPool:
        """Lazy-init Redis connection pool (async-safe).

        Raises:
            ConnectionError: If Redis connection cannot be established.
        """
        if self._pool is None:
            try:
                self._pool = aioredis.ConnectionPool(
                    host=self._redis_config.host,
                    port=self._redis_config.port,
                    db=self._redis_config.db,
                    password=self._redis_config.password,
                    max_connections=self._redis_config.max_connections,
                    socket_timeout=self._redis_config.socket_timeout,
                    decode_responses=True,
                )
                # Verify connection works
                async with aioredis.Redis(connection_pool=self._pool) as client:
                    await client.ping()
            except Exception as e:
                self._pool = None
                raise ConnectionError(f"Failed to initialize Redis connection: {e}") from e
        return self._pool

    async def schedule_heartbeat(
        self,
        heartbeat_id: uuid.UUID,
        delay_seconds: int,
        wake_reason: str = "scheduled",
    ) -> None:
        """Schedule a one-time heartbeat after delay_seconds.

        Args:
            heartbeat_id: Unique identifier for this heartbeat
            delay_seconds: Delay before firing
            wake_reason: Reason for the scheduled heartbeat
        """
        pool = await self._get_pool()
        fire_time = datetime.now(UTC).timestamp() + delay_seconds
        try:
            async with aioredis.Redis(connection_pool=pool) as client:
                await client.zadd(self._HEARTBEAT_KEY, {str(heartbeat_id): fire_time})
                logger.debug(
                    "Scheduled one-time heartbeat id=%s fire_at=%s",
                    heartbeat_id,
                    fire_time,
                )
        except Exception as e:
            logger.error("Failed to schedule one-time heartbeat: %s", e)
            raise
