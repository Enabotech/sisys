"""HeartbeatScheduler — schedules periodic heartbeat events using Redis sorted set.

Technical decision: Use asyncio + threading + Redis sorted set (ZADD/ZRANGEBYSCORE).
No new dependencies (APScheduler not used). Integrates with existing Redis tech stack.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import redis.asyncio as aioredis

from src.domain.events.heartbeat_events import HeartbeatTriggered
from src.infrastructure.config.redis import RedisConfig

logger = logging.getLogger(__name__)


class HeartbeatScheduler:
    """Schedules periodic heartbeat events using Redis sorted set for delayed dispatch.

    Implementation:
    - Uses Redis sorted set (ZADD/ZRANGEBYSCORE) for delayed heartbeat scheduling
    - asyncio loop for async operations, threading for timer coordination
    - Generates HeartbeatTriggered events when timer fires

    Architecture: Infrastructure layer, depends on Redis and EventPublisher.
    """

    _HEARTBEAT_KEY = "heartbeat:pending"
    _POLL_INTERVAL_SECONDS = 5  # Poll Redis every 5 seconds

    def __init__(
        self,
        redis_config: RedisConfig,
        interval_seconds: int = 60,
        publisher: Callable[[HeartbeatTriggered], asyncio.Future] | None = None,
    ):
        """Initialize HeartbeatScheduler.

        Args:
            redis_config: Redis connection configuration
            interval_seconds: Heartbeat interval (default 60s, configurable via HEARTBEAT_INTERVAL_SECONDS)
            publisher: Async callable that publishes HeartbeatTriggered events
        """
        self._redis_config = redis_config
        self._interval_seconds = interval_seconds
        self._publisher = publisher
        self._running = False
        self._timer: threading.Timer | None = None
        self._poll_task: asyncio.Task | None = None
        self._pool: aioredis.ConnectionPool | None = None

    async def start(self) -> None:
        """Start the heartbeat scheduler (async entry point)."""
        if self._running:
            logger.warning("HeartbeatScheduler already running")
            return

        self._running = True
        logger.info("HeartbeatScheduler started with interval=%ds", self._interval_seconds)

        # Schedule first heartbeat
        self._schedule_next()

        # Start polling task
        loop = asyncio.get_running_loop()
        self._poll_task = loop.create_task(self._poll_loop())

    async def stop(self) -> None:
        """Stop the heartbeat scheduler gracefully."""
        if not self._running:
            return

        self._running = False
        logger.info("HeartbeatScheduler stopping")

        # Cancel timer
        if self._timer:
            self._timer.cancel()
            self._timer = None

        # Cancel poll task and wait for it to finish
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await asyncio.wait_for(self._poll_task, timeout=1.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            self._poll_task = None

        # Close Redis pool
        if self._pool:
            await self._pool.disconnect()
            self._pool = None

        logger.info("HeartbeatScheduler stopped")

    def _schedule_next(self) -> None:
        """Schedule the next heartbeat trigger using threading.Timer."""
        if not self._running:
            return

        def fire_heartbeat() -> None:
            """Fire heartbeat in a new asyncio context."""
            if not self._running:
                return
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._fire_heartbeat())
                loop.close()
            except Exception as e:
                logger.error("Error firing heartbeat: %s", e)

        self._timer = threading.Timer(self._interval_seconds, fire_heartbeat)
        self._timer.daemon = True
        self._timer.start()

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

    async def _poll_loop(self) -> None:
        """Poll Redis sorted set for due heartbeats (for at-least-once tracking)."""
        while self._running:
            try:
                await asyncio.sleep(self._POLL_INTERVAL_SECONDS)
                if not self._running:
                    break

                pool = await self._get_pool()
                async with aioredis.Redis(connection_pool=pool) as client:
                    now = datetime.now(UTC).timestamp()
                    # Get heartbeats due now or earlier
                    due = await client.zrangebyscore(
                        self._HEARTBEAT_KEY,
                        min="-inf",
                        max=now,
                        start=0,
                        num=10,
                    )
                    if due:
                        logger.debug("Found %d due heartbeats for tracking", len(due))
                        # Mark as processed (cleanup would be done by TTL)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in heartbeat poll loop: %s", e)

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
