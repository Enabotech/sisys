"""RedisSnapshotStore 单元测试

基于 RedisAdapter mock 验证快照存储的 CRUD 行为

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot
from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
from src.infrastructure.storage.redis.redis_snapshot_store import RedisSnapshotStore


class TestRedisSnapshotStore:
    """RedisSnapshotStore TDD 测试"""

    @pytest.fixture
    def mock_adapter(self) -> MagicMock:
        """创建 mock RedisAdapter 及 raw_client"""
        adapter = MagicMock(spec=RedisAdapter)
        adapter.delete = AsyncMock()
        adapter.exists = AsyncMock()
        raw = MagicMock()
        raw.hset = AsyncMock()
        raw.hget = AsyncMock()
        raw.expire = AsyncMock()
        adapter.raw_client = raw
        return adapter

    @pytest.mark.asyncio
    async def test_save_snapshot_to_redis(self, mock_adapter: MagicMock) -> None:
        """save 应存储快照到 Redis Hash"""
        store = RedisSnapshotStore(adapter=mock_adapter)
        snapshot = CheckpointSnapshot(
            session_id="test-session",
            stage_id="planning",
            state_version=1,
            state_data={"key": "value"},
        )

        await store.save(snapshot)

        mock_adapter.raw_client.hset.assert_called_once()
        mock_adapter.raw_client.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_snapshot_from_redis(self, mock_adapter: MagicMock) -> None:
        """load 应从 Redis Hash 读取快照"""
        import json

        store = RedisSnapshotStore(adapter=mock_adapter)
        snapshot = CheckpointSnapshot(
            session_id="test-session",
            stage_id="execution",
            state_version=2,
            state_data={"result": "ok"},
        )
        hash_data = RedisSnapshotStore._snapshot_to_hash(snapshot)
        mock_adapter.raw_client.hget = AsyncMock(return_value=json.dumps(hash_data))

        result = await store.load("test-session")

        assert result is not None
        assert result.session_id == "test-session"
        assert result.stage_id == "execution"
        assert result.state_version == 2

    @pytest.mark.asyncio
    async def test_load_returns_none_when_not_found(self, mock_adapter: MagicMock) -> None:
        """load 应在快照不存在时返回 None"""
        store = RedisSnapshotStore(adapter=mock_adapter)
        mock_adapter.raw_client.hget = AsyncMock(return_value=None)

        result = await store.load("nonexistent-session")

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_snapshot(self, mock_adapter: MagicMock) -> None:
        """delete 应删除快照"""
        store = RedisSnapshotStore(adapter=mock_adapter)

        await store.delete("test-session")

        mock_adapter.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_exists_check(self, mock_adapter: MagicMock) -> None:
        """exists 应在快照存在时返回 True"""
        store = RedisSnapshotStore(adapter=mock_adapter)
        mock_adapter.exists = AsyncMock(return_value=True)

        result = await store.exists("test-session")

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false_when_missing(self, mock_adapter: MagicMock) -> None:
        """exists 应在快照不存在时返回 False"""
        store = RedisSnapshotStore(adapter=mock_adapter)
        mock_adapter.exists = AsyncMock(return_value=False)

        result = await store.exists("nonexistent-session")

        assert result is False

    def test_set_ttl_rejects_invalid_ttl(self, mock_adapter: MagicMock) -> None:
        """set_ttl 应拒绝超出范围的 TTL"""
        store = RedisSnapshotStore(adapter=mock_adapter)

        with pytest.raises(ValueError) as exc_info:
            store.set_ttl(30)

        assert "TTL must be between" in str(exc_info.value)

        with pytest.raises(ValueError):
            store.set_ttl(3000000)

    def test_set_ttl_accepts_valid_ttl(self, mock_adapter: MagicMock) -> None:
        """set_ttl 应接受合法 TTL"""
        store = RedisSnapshotStore(adapter=mock_adapter)
        store.set_ttl(3600)

        assert store._ttl_seconds == 3600

    @pytest.mark.asyncio
    async def test_save_handles_exception(self, mock_adapter: MagicMock) -> None:
        """save 应在 Redis 异常时抛出 RuntimeError"""
        store = RedisSnapshotStore(adapter=mock_adapter)
        mock_adapter.raw_client.hset = AsyncMock(side_effect=Exception("redis error"))
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
    async def test_load_handles_exception(self, mock_adapter: MagicMock) -> None:
        """load 应在 Redis 异常时返回 None"""
        store = RedisSnapshotStore(adapter=mock_adapter)
        mock_adapter.raw_client.hget = AsyncMock(side_effect=Exception("redis error"))

        result = await store.load("test-session")

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_handles_exception(self, mock_adapter: MagicMock) -> None:
        """delete 应在 Redis 异常时抛出 RuntimeError"""
        store = RedisSnapshotStore(adapter=mock_adapter)
        mock_adapter.delete = AsyncMock(side_effect=Exception("redis error"))

        with pytest.raises(RuntimeError) as exc_info:
            await store.delete("test-session")

        assert "Failed to delete snapshot" in str(exc_info.value)
