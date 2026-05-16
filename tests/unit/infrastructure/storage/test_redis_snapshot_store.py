"""Tests for RedisSnapshotStore infrastructure implementation."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot
from src.infrastructure.storage.redis.redis_snapshot_store import RedisSnapshotStore


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

    def test_set_ttl_rejects_invalid_ttl(self) -> None:
        """Coverage: set_ttl validation (lines 48-50)."""
        store = RedisSnapshotStore(redis_client=None)

        with pytest.raises(ValueError) as exc_info:
            store.set_ttl(30)  # Below minimum of 60

        assert "TTL must be between" in str(exc_info.value)

        with pytest.raises(ValueError):
            store.set_ttl(3000000)  # Above maximum

    def test_set_ttl_accepts_valid_ttl(self) -> None:
        """Coverage: set_ttl accepts valid values."""
        store = RedisSnapshotStore(redis_client=None)
        store.set_ttl(3600)  # 1 hour

        assert store._ttl_seconds == 3600

    @pytest.mark.asyncio
    async def test_save_handles_redis_none(self) -> None:
        """Coverage: save early return when redis is None (lines 62-63)."""
        store = RedisSnapshotStore(redis_client=None)
        snapshot = CheckpointSnapshot(
            session_id="test-session",
            stage_id="test",
            state_version=1,
            state_data={"key": "value"},
        )

        # Should not raise, just return
        await store.save(snapshot)

    @pytest.mark.asyncio
    async def test_save_handles_exception(self, mock_redis: MagicMock) -> None:
        """Coverage: save exception handler (lines 85-87)."""
        store = RedisSnapshotStore(redis_client=mock_redis)
        mock_redis.hset = AsyncMock(side_effect=Exception("redis error"))
        snapshot = CheckpointSnapshot(
            session_id="test-session",
            stage_id="test",
            state_version=1,
            state_data={"key": "value"},
        )

        with pytest.raises(RuntimeError) as exc_info:
            await store.save(snapshot)

        assert "Failed to save snapshot" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_load_handles_redis_none(self) -> None:
        """Coverage: load early return when redis is None (lines 102-103)."""
        store = RedisSnapshotStore(redis_client=None)

        result = await store.load("any-session")

        assert result is None

    @pytest.mark.asyncio
    async def test_load_handles_exception(self, mock_redis: MagicMock) -> None:
        """Coverage: load exception handler (lines 125-127)."""
        store = RedisSnapshotStore(redis_client=mock_redis)
        mock_redis.hget = AsyncMock(side_effect=Exception("redis error"))

        result = await store.load("test-session")

        # Should return None instead of raising
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_handles_redis_none(self) -> None:
        """Coverage: delete early return when redis is None (lines 139-140)."""
        store = RedisSnapshotStore(redis_client=None)

        # Should not raise
        await store.delete("any-session")

    @pytest.mark.asyncio
    async def test_delete_handles_exception(self, mock_redis: MagicMock) -> None:
        """Coverage: delete exception handler (lines 148-150)."""
        store = RedisSnapshotStore(redis_client=mock_redis)
        mock_redis.delete = AsyncMock(side_effect=Exception("redis error"))

        with pytest.raises(RuntimeError) as exc_info:
            await store.delete("test-session")

        assert "Failed to delete snapshot" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_exists_handles_redis_none(self) -> None:
        """Coverage: exists early return when redis is None (line 162)."""
        store = RedisSnapshotStore(redis_client=None)

        result = await store.exists("any-session")

        assert result is False
