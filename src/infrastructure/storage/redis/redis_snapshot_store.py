"""SISYS 基础设施层 Redis 快照存储模块

基于 Redis Hash 实现检查点快照仓储端口，
支持 TTL 过期和主从复制

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class RedisSnapshotStore:
    """Redis-based snapshot storage implementation.

    Uses Redis Hash to store snapshot data:
    - Key: snapshot:{session_id}
    - Field: latest -> JSON snapshot data
    - TTL: configurable (default 24h, max 30d)

    Supports Redis Sentinel/Cluster for master-slave replication and failover.
    """

    SNAPSHOT_KEY_PREFIX = "snapshot:"

    def __init__(self, redis_client: Redis | None = None):
        """Initialize RedisSnapshotStore.

        Args:
            redis_client: Async Redis client. None for testing (mock mode).
        """
        self._redis = redis_client
        self._ttl_seconds: int = 86400  # Default 24 hours

    def set_ttl(self, ttl_seconds: int) -> None:
        """Set default TTL for snapshots.

        Args:
            ttl_seconds: TTL in seconds (60-2592000 range)
        """
        if ttl_seconds < 60 or ttl_seconds > 2592000:
            raise ValueError("TTL must be between 60 seconds and 30 days")
        self._ttl_seconds = ttl_seconds

    async def save(self, snapshot: CheckpointSnapshot) -> None:
        """Save a snapshot to Redis.

        Args:
            snapshot: CheckpointSnapshot to save

        Raises:
            RuntimeError: If Redis client is not configured
        """
        if self._redis is None:
            logger.warning("No Redis client configured, snapshot not saved")
            return

        key = f"{self.SNAPSHOT_KEY_PREFIX}{snapshot.session_id}"
        ttl = snapshot.ttl_seconds if snapshot.ttl_seconds > 0 else self._ttl_seconds

        try:
            # Serialize snapshot to Redis Hash
            hash_data = snapshot.to_redis_hash()

            # Store as JSON string under 'latest' field
            import json

            await self._redis.hset(key, "latest", json.dumps(hash_data))
            await self._redis.expire(key, ttl)

            logger.debug(
                "Saved snapshot: session_id=%s version=%d ttl=%d",
                snapshot.session_id,
                snapshot.state_version,
                ttl,
            )

        except Exception as e:
            logger.error("Failed to save snapshot: session_id=%s error=%s", snapshot.session_id, e)
            raise RuntimeError(f"Failed to save snapshot: {e}") from e

    async def load(self, session_id: str) -> CheckpointSnapshot | None:
        """Load the latest snapshot for a session.

        Args:
            session_id: Session identifier

        Returns:
            CheckpointSnapshot if found, None otherwise

        Raises:
            RuntimeError: If Redis client is not configured
        """
        if self._redis is None:
            logger.warning("No Redis client configured, cannot load snapshot")
            return None

        key = f"{self.SNAPSHOT_KEY_PREFIX}{session_id}"

        try:
            import json

            data = await self._redis.hget(key, "latest")
            if data is None:
                logger.debug("No snapshot found: session_id=%s", session_id)
                return None

            hash_data = json.loads(data)
            snapshot = CheckpointSnapshot.from_redis_hash(hash_data)

            logger.debug(
                "Loaded snapshot: session_id=%s version=%d",
                session_id,
                snapshot.state_version,
            )
            return snapshot

        except Exception as e:
            logger.error("Failed to load snapshot: session_id=%s error=%s", session_id, e)
            return None

    async def delete(self, session_id: str) -> None:
        """Delete all snapshots for a session.

        Args:
            session_id: Session identifier

        Raises:
            RuntimeError: If Redis client is not configured
        """
        if self._redis is None:
            logger.warning("No Redis client configured, cannot delete snapshot")
            return

        key = f"{self.SNAPSHOT_KEY_PREFIX}{session_id}"

        try:
            await self._redis.delete(key)
            logger.debug("Deleted snapshot: session_id=%s", session_id)

        except Exception as e:
            logger.error("Failed to delete snapshot: session_id=%s error=%s", session_id, e)
            raise RuntimeError(f"Failed to delete snapshot: {e}") from e

    async def exists(self, session_id: str) -> bool:
        """Check if a snapshot exists for a session.

        Args:
            session_id: Session identifier

        Returns:
            True if snapshot exists, False otherwise
        """
        if self._redis is None:
            return False

        key = f"{self.SNAPSHOT_KEY_PREFIX}{session_id}"
        return await self._redis.exists(key) > 0
