"""RedisSnapshotStore 单元测试

基于 RedisAdapter mock 验证快照存储的 CRUD 行为
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot
from src.domain.exceptions import StorageError, ValidationError
from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
from src.infrastructure.storage.redis.redis_snapshot_store import RedisSnapshotStore


class TestRedisSnapshotStore:
    """RedisSnapshotStore TDD 测试"""

    @pytest.fixture
    def mock_adapter(self) -> MagicMock:
        """创建 mock RedisAdapter 及 raw_client（含 pipeline 替身——hset/expire 同步入队、execute 原子应用）"""
        adapter = MagicMock(spec=RedisAdapter)
        adapter.delete = AsyncMock()
        adapter.exists = AsyncMock()
        raw = MagicMock()
        raw.hget = AsyncMock()

        pipe = MagicMock()
        pipe.hset = MagicMock()
        pipe.expire = MagicMock()
        pipe.execute = AsyncMock(return_value=[1, True])
        pipe.__aenter__ = AsyncMock(return_value=pipe)
        pipe.__aexit__ = AsyncMock(return_value=None)

        raw.pipeline = MagicMock(return_value=pipe)
        adapter.raw_client = raw
        return adapter

    async def test_save_snapshot_to_redis(self, mock_adapter: MagicMock) -> None:
        """save 应经 pipeline 原子存储快照到 Redis Hash（D8 清偿：hset+expire 单事务，防崩溃窗口孤儿键）"""
        store = RedisSnapshotStore(adapter=mock_adapter)
        snapshot = CheckpointSnapshot(
            session_id="test-session",
            stage_id="planning",
            state_version=1,
            state_data={"key": "value"},
        )

        await store.save(snapshot)

        mock_adapter.raw_client.pipeline.assert_called_once_with(transaction=True)
        pipe = mock_adapter.raw_client.pipeline.return_value
        pipe.hset.assert_called_once()
        pipe.expire.assert_called_once()
        pipe.execute.assert_awaited_once()

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

    async def test_load_returns_none_when_not_found(self, mock_adapter: MagicMock) -> None:
        """load 应在快照不存在时返回 None"""
        store = RedisSnapshotStore(adapter=mock_adapter)
        mock_adapter.raw_client.hget = AsyncMock(return_value=None)

        result = await store.load("nonexistent-session")

        assert result is None

    async def test_delete_snapshot(self, mock_adapter: MagicMock) -> None:
        """delete 应删除快照"""
        store = RedisSnapshotStore(adapter=mock_adapter)

        await store.delete("test-session")

        mock_adapter.delete.assert_called_once()

    async def test_exists_check(self, mock_adapter: MagicMock) -> None:
        """exists 应在快照存在时返回 True"""
        store = RedisSnapshotStore(adapter=mock_adapter)
        mock_adapter.exists = AsyncMock(return_value=True)

        result = await store.exists("test-session")

        assert result is True

    async def test_exists_false_when_missing(self, mock_adapter: MagicMock) -> None:
        """exists 应在快照不存在时返回 False"""
        store = RedisSnapshotStore(adapter=mock_adapter)
        mock_adapter.exists = AsyncMock(return_value=False)

        result = await store.exists("nonexistent-session")

        assert result is False

    def test_set_ttl_rejects_invalid_ttl(self, mock_adapter: MagicMock) -> None:
        """set_ttl 应拒绝超出范围的 TTL"""
        store = RedisSnapshotStore(adapter=mock_adapter)

        with pytest.raises(ValidationError) as exc_info:
            store.set_ttl(30)

        assert "TTL must be between" in str(exc_info.value)

        with pytest.raises(ValidationError):
            store.set_ttl(3000000)

    def test_set_ttl_accepts_valid_ttl(self, mock_adapter: MagicMock) -> None:
        """set_ttl 应接受合法 TTL"""
        store = RedisSnapshotStore(adapter=mock_adapter)
        store.set_ttl(3600)

        assert store._ttl_seconds == 3600

    async def test_save_handles_exception(self, mock_adapter: MagicMock) -> None:
        """save 应在 Redis 异常时抛出 StorageError（pipeline execute 注入）"""
        store = RedisSnapshotStore(adapter=mock_adapter)
        mock_adapter.raw_client.pipeline.return_value.execute = AsyncMock(side_effect=Exception("redis error"))
        snapshot = CheckpointSnapshot(
            session_id="test-session",
            stage_id="test",
            state_version=1,
            state_data={"key": "value"},
        )

        with pytest.raises(StorageError) as exc_info:
            await store.save(snapshot)

        assert "Failed to save snapshot" in str(exc_info.value)

    async def test_load_handles_exception(self, mock_adapter: MagicMock) -> None:
        """load 应在 Redis 异常时返回 None"""
        store = RedisSnapshotStore(adapter=mock_adapter)
        mock_adapter.raw_client.hget = AsyncMock(side_effect=Exception("redis error"))

        result = await store.load("test-session")

        assert result is None

    async def test_delete_handles_exception(self, mock_adapter: MagicMock) -> None:
        """delete 应在 Redis 异常时抛出 RuntimeError"""
        store = RedisSnapshotStore(adapter=mock_adapter)
        mock_adapter.delete = AsyncMock(side_effect=Exception("redis error"))

        with pytest.raises(StorageError) as exc_info:
            await store.delete("test-session")

        assert "Failed to delete snapshot" in str(exc_info.value)


class TestCompleteFormSerialization:
    """Story 6-3 — 完整形态新四字段序列化 round-trip（白名单扩列——OD-2/R2A-1）。

    序列化直测：_snapshot_to_hash/_hash_to_snapshot 对称性（新四字段不丢 +
    旧七字段数据缺键回退默认值——白名单失误的唯一拦截面，R6-14）。
    """

    @pytest.fixture
    def mock_adapter_holder(self) -> MagicMock:
        """创建 mock RedisAdapter 及 raw_client（形态同 TestRedisSnapshotStore.mock_adapter）。"""
        adapter = MagicMock(spec=RedisAdapter)
        adapter.delete = AsyncMock()
        adapter.exists = AsyncMock()
        raw = MagicMock()
        raw.hget = AsyncMock()
        pipe = MagicMock()
        pipe.hset = MagicMock()
        pipe.expire = MagicMock()
        pipe.execute = AsyncMock(return_value=[1, True])
        pipe.__aenter__ = AsyncMock(return_value=pipe)
        pipe.__aexit__ = AsyncMock(return_value=None)
        raw.pipeline = MagicMock(return_value=pipe)
        adapter.raw_client = raw
        return adapter

    def _make_complete_snapshot(self) -> CheckpointSnapshot:
        """完整形态快照工厂（新四字段填充）。"""
        import uuid

        return CheckpointSnapshot(
            session_id="blm-checkpoint-plan-1:CP-1",
            stage_id="performance_gap",
            state_version=0,
            ttl_seconds=2592000,
            checkpoint_no="CP-1",
            persistent_note_ref=str(uuid.uuid4()),
            checksum="a" * 64,
            snapshot_metadata={"compression_ratio": 0.85, "rerun_count": 1},
            state_data={"checkpoint_no": "CP-1", "compressed_context": "压缩上下文"},
        )

    def test_new_four_fields_roundtrip(self) -> None:
        """新四字段经 _snapshot_to_hash→_hash_to_snapshot 读回不丢失（白名单扩列验证）。"""
        snapshot = self._make_complete_snapshot()

        hash_data = RedisSnapshotStore._snapshot_to_hash(snapshot)
        loaded = RedisSnapshotStore._hash_to_snapshot(hash_data)

        assert loaded.checkpoint_no == snapshot.checkpoint_no
        assert loaded.persistent_note_ref == snapshot.persistent_note_ref
        assert loaded.checksum == snapshot.checksum
        assert loaded.snapshot_metadata == snapshot.snapshot_metadata
        # 既有七字段不回归
        assert loaded.session_id == snapshot.session_id
        assert loaded.stage_id == snapshot.stage_id
        assert loaded.state_version == snapshot.state_version
        assert loaded.state_data == snapshot.state_data
        assert loaded.ttl_seconds == snapshot.ttl_seconds

    def test_legacy_seven_fields_missing_keys_fallback(self) -> None:
        """旧七字段数据 load 缺键回退默认值（6-1/6-2/5-10 旧数据向后兼容——不抛）。"""
        import json
        from datetime import UTC, datetime

        legacy_hash = {
            "snapshot_id": "0b6bb6b7-0c5d-4f9e-9d3a-1f2e3d4c5b6a",
            "session_id": "blm-planning-plan-1",
            "stage_id": "blm_planning",
            "state_version": "3",
            "state_data": json.dumps({"plan_id": "plan-1"}),
            "timestamp": datetime.now(UTC).isoformat(),
            "ttl_seconds": "86400",
        }

        loaded = RedisSnapshotStore._hash_to_snapshot(legacy_hash)

        assert loaded.checkpoint_no == ""
        assert loaded.persistent_note_ref == ""
        assert loaded.checksum == ""
        assert loaded.snapshot_metadata == {}

    async def test_save_load_full_roundtrip_via_adapter(self, mock_adapter_holder: MagicMock) -> None:
        """save→load 全链 round-trip（经 adapter pipeline 写入后回读——含新四字段）。"""
        store = RedisSnapshotStore(adapter=mock_adapter_holder)
        snapshot = self._make_complete_snapshot()

        # 捕获 pipeline hset 写入值（latest 字段 JSON）
        written: dict[str, str] = {}
        pipe = mock_adapter_holder.raw_client.pipeline.return_value
        pipe.hset.side_effect = lambda key, field, value: written.update({field: value})
        await store.save(snapshot)

        mock_adapter_holder.raw_client.hget = AsyncMock(return_value=written["latest"])
        loaded = await store.load(snapshot.session_id)

        assert loaded is not None
        assert loaded.checkpoint_no == snapshot.checkpoint_no
        assert loaded.persistent_note_ref == snapshot.persistent_note_ref
        assert loaded.checksum == snapshot.checksum
        assert loaded.snapshot_metadata == snapshot.snapshot_metadata
        # state_data 反序列化回 dict（R1 审查 FR-11 收紧——原 json.dumps 恒 str 恒真）
        assert isinstance(loaded.state_data, dict)
