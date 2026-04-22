"""Tests for RedisSnapshotStore infrastructure implementation."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot
from src.infrastructure.storage.redis_snapshot_store import RedisSnapshotStore


class TestRedisSnapshotStore:
    """TDD tests for RedisSnapshotStore."""

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        """Create a mock Redis client with async methods."""
        redis = MagicMock()
        redis.hset = AsyncMock()
        redis.expire = AsyncMock()
        redis.hget = AsyncMock()
        redis.delete = AsyncMock()
        redis.exists = AsyncMock()
        return redis

    @pytest.mark.asyncio
    async def test_save_snapshot_to_redis(self, mock_redis: MagicMock) -> None:
        """RED: save should store snapshot as Redis hash."""
        store = RedisSnapshotStore(redis_client=mock_redis)
        snapshot = CheckpointSnapshot(
            session_id="test-session",
            stage_id="planning",
            state_version=1,
            state_data={"key": "value"},
        )

        await store.save(snapshot)

        mock_redis.hset.assert_called_once()
        mock_redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_snapshot_from_redis(self, mock_redis: MagicMock) -> None:
        """RED: load should retrieve snapshot from Redis hash."""
        import json

        store = RedisSnapshotStore(redis_client=mock_redis)
        snapshot = CheckpointSnapshot(
            session_id="test-session",
            stage_id="execution",
            state_version=2,
            state_data={"result": "ok"},
        )
        mock_redis.hget = AsyncMock(return_value=json.dumps(snapshot.to_redis_hash()))

        result = await store.load("test-session")

        assert result is not None
        assert result.session_id == "test-session"
        assert result.stage_id == "execution"
        assert result.state_version == 2

    @pytest.mark.asyncio
    async def test_load_returns_none_when_not_found(self, mock_redis: MagicMock) -> None:
        """RED: load should return None if snapshot doesn't exist."""
        store = RedisSnapshotStore(redis_client=mock_redis)
        mock_redis.hget = AsyncMock(return_value=None)

        result = await store.load("nonexistent-session")

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_snapshot(self, mock_redis: MagicMock) -> None:
        """RED: delete should remove snapshot from Redis."""
        store = RedisSnapshotStore(redis_client=mock_redis)
        mock_redis.delete = AsyncMock()

        await store.delete("test-session")

        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_exists_check(self, mock_redis: MagicMock) -> None:
        """RED: exists should return True if snapshot exists."""
        store = RedisSnapshotStore(redis_client=mock_redis)
        mock_redis.exists = AsyncMock(return_value=1)

        result = await store.exists("test-session")

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false_when_missing(self, mock_redis: MagicMock) -> None:
        """RED: exists should return False if snapshot doesn't exist."""
        store = RedisSnapshotStore(redis_client=mock_redis)
        mock_redis.exists = AsyncMock(return_value=0)

        result = await store.exists("nonexistent-session")

        assert result is False
