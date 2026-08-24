"""Tests for ChunkedUploadManager — 分片上传状态管理器"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from src.domain.exceptions import ConflictError, NotFoundError
from src.domain.value_objects.upload_limits import CHUNKED_UPLOAD_TTL, MEDIUM_PART_SIZE
from src.infrastructure.storage.redis.chunked_upload_manager import (
    _CHUNKED_UPLOAD_PREFIX,
    _LOCK_PREFIX,
    ChunkedUploadManager,
    ChunkedUploadState,
)


def _make_cache() -> AsyncMock:
    """创建 L1CachePort mock"""
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=True)
    cache.delete = AsyncMock(return_value=True)
    return cache


def _make_state_json(
    upload_id: str = "abc123",
    filename: str = "test.pdf",
    file_size: int = 500 * 1024 * 1024,
    chunk_size: int = MEDIUM_PART_SIZE,
    uploaded_parts: list[dict] | None = None,
    minio_upload_id: str | None = None,
    object_key: str | None = None,
) -> str:
    """构造 ChunkedUploadState JSON"""
    return json.dumps(
        {
            "upload_id": upload_id,
            "filename": filename,
            "file_size": file_size,
            "chunk_size": chunk_size,
            "uploaded_parts": uploaded_parts or [],
            "minio_upload_id": minio_upload_id,
            "object_key": object_key,
        }
    )


class TestChunkedUploadState:
    """验证 ChunkedUploadState 序列化/反序列化"""

    def test_to_json_roundtrip(self) -> None:
        """序列化后反序列化应还原原始状态"""
        state = ChunkedUploadState(
            upload_id="u1",
            filename="doc.pdf",
            file_size=1024,
            chunk_size=512,
            uploaded_parts=[{"part_number": 1, "etag": "abc"}],
            minio_upload_id="minio-123",
            object_key="docs/user/file.pdf",
        )
        restored = ChunkedUploadState.from_json(state.to_json())
        assert restored.upload_id == "u1"
        assert restored.filename == "doc.pdf"
        assert restored.file_size == 1024
        assert restored.chunk_size == 512
        assert len(restored.uploaded_parts) == 1
        assert restored.uploaded_parts[0]["part_number"] == 1
        assert restored.minio_upload_id == "minio-123"
        assert restored.object_key == "docs/user/file.pdf"

    def test_from_json_missing_uploaded_parts_defaults_empty(self) -> None:
        """uploaded_parts 缺失时默认空列表"""
        data = json.dumps(
            {
                "upload_id": "u2",
                "filename": "f.txt",
                "file_size": 100,
                "chunk_size": 50,
            }
        )
        state = ChunkedUploadState.from_json(data)
        assert state.uploaded_parts == []
        assert state.minio_upload_id is None
        assert state.object_key is None

    def test_to_json_roundtrip_without_minio_fields(self) -> None:
        """minio 字段为 None 时序列化/反序列化正确"""
        state = ChunkedUploadState(
            upload_id="u3",
            filename="doc.pdf",
            file_size=1024,
            chunk_size=512,
        )
        restored = ChunkedUploadState.from_json(state.to_json())
        assert restored.minio_upload_id is None
        assert restored.object_key is None


class TestChunkedUploadManagerInitUpload:
    """验证 init_upload 初始化分片上传"""

    async def test_init_small_file_chunk_size_equals_file_size(self) -> None:
        """小文件（< 100MB）不分片，chunk_size 等于文件大小"""
        cache = _make_cache()
        manager = ChunkedUploadManager(cache)
        file_size = 50 * 1024 * 1024
        result = await manager.init_upload("small.pdf", file_size)
        assert result["chunk_size"] == file_size
        assert result["total_parts"] == 1
        assert "upload_id" in result

    async def test_init_large_file_returns_chunked(self) -> None:
        """大文件（> 100MB）启用分片"""
        cache = _make_cache()
        manager = ChunkedUploadManager(cache)
        file_size = 500 * 1024 * 1024  # 500MB
        result = await manager.init_upload("big.pdf", file_size)
        assert result["chunk_size"] == MEDIUM_PART_SIZE
        assert result["total_parts"] > 1

    async def test_init_stores_state_in_redis(self) -> None:
        """初始化时应将状态写入 Redis"""
        cache = _make_cache()
        manager = ChunkedUploadManager(cache)
        await manager.init_upload("test.pdf", 200 * 1024 * 1024)
        cache.set.assert_called_once()
        call_args = cache.set.call_args
        key = call_args[0][0]
        assert key.startswith(_CHUNKED_UPLOAD_PREFIX)
        assert call_args[1]["ttl"] == CHUNKED_UPLOAD_TTL

    async def test_init_returns_unique_upload_ids(self) -> None:
        """每次初始化返回不同的 upload_id"""
        cache = _make_cache()
        manager = ChunkedUploadManager(cache)
        r1 = await manager.init_upload("a.pdf", 200 * 1024 * 1024)
        r2 = await manager.init_upload("b.pdf", 200 * 1024 * 1024)
        assert r1["upload_id"] != r2["upload_id"]

    async def test_init_with_minio_context_stores_in_state(self) -> None:
        """初始化时传递 minio_upload_id 和 object_key 存入状态"""
        cache = _make_cache()
        manager = ChunkedUploadManager(cache)
        await manager.init_upload(
            "test.pdf",
            200 * 1024 * 1024,
            minio_upload_id="minio-upload-123",
            object_key="docs/user/file.pdf",
        )
        cache.set.assert_called_once()
        stored_json = cache.set.call_args[0][1]
        stored = json.loads(stored_json)
        assert stored["minio_upload_id"] == "minio-upload-123"
        assert stored["object_key"] == "docs/user/file.pdf"


class TestChunkedUploadManagerUploadPart:
    """验证 upload_part 记录已上传分片"""

    async def test_upload_part_success(self) -> None:
        """正常记录分片上传"""
        cache = _make_cache()
        manager = ChunkedUploadManager(cache)

        state_json = _make_state_json()
        cache.get = AsyncMock(return_value=state_json)

        result = await manager.upload_part("abc123", 1, "etag-001")
        assert result["uploaded_parts"] == 1

    async def test_upload_part_appends_to_existing(self) -> None:
        """分片追加到已有列表"""
        cache = _make_cache()
        manager = ChunkedUploadManager(cache)

        state_json = _make_state_json(uploaded_parts=[{"part_number": 1, "etag": "etag-001"}])
        cache.get = AsyncMock(return_value=state_json)

        result = await manager.upload_part("abc123", 2, "etag-002")
        assert result["uploaded_parts"] == 2

    async def test_upload_part_nonexistent_raises(self) -> None:
        """upload_id 不存在抛出 ValueError"""
        cache = _make_cache()
        manager = ChunkedUploadManager(cache)
        cache.get = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError, match="不存在或已过期"):
            await manager.upload_part("bad-id", 1, "etag")

    async def test_upload_part_duplicate_is_idempotent(self) -> None:
        """重复分片幂等处理：返回成功而非报错"""
        cache = _make_cache()
        manager = ChunkedUploadManager(cache)

        state_json = _make_state_json(uploaded_parts=[{"part_number": 1, "etag": "etag-001"}])
        cache.get = AsyncMock(return_value=state_json)
        cache.set_nx = AsyncMock(return_value=True)
        cache.eval = AsyncMock(return_value=1)

        result = await manager.upload_part("abc123", 1, "etag-001-again")
        assert result["uploaded_parts"] == 1

    async def test_upload_part_persists_updated_state(self) -> None:
        """上传分片后应持久化更新后的状态"""
        cache = _make_cache()
        manager = ChunkedUploadManager(cache)

        state_json = _make_state_json()
        cache.get = AsyncMock(return_value=state_json)

        await manager.upload_part("abc123", 1, "etag-001")
        cache.set.assert_called_once()

        stored_json = cache.set.call_args[0][1]
        stored = json.loads(stored_json)
        assert len(stored["uploaded_parts"]) == 1
        assert stored["uploaded_parts"][0]["part_number"] == 1

    async def test_upload_part_out_of_order_raises(self) -> None:
        """分片乱序到达抛出 ValueError"""
        cache = _make_cache()
        manager = ChunkedUploadManager(cache)

        # 已上传 part 1，期望下一个是 part 2
        state_json = _make_state_json(uploaded_parts=[{"part_number": 1, "etag": "etag-001"}])
        cache.get = AsyncMock(return_value=state_json)

        with pytest.raises(ConflictError, match="分片乱序"):
            await manager.upload_part("abc123", 3, "etag-003")

    async def test_upload_part_sequential_order_accepted(self) -> None:
        """按顺序上传分片正常接受"""
        cache = _make_cache()
        manager = ChunkedUploadManager(cache)

        # 已上传 part 1 和 2，期望下一个是 part 3
        state_json = _make_state_json(uploaded_parts=[{"part_number": 1, "etag": "e1"}, {"part_number": 2, "etag": "e2"}])
        cache.get = AsyncMock(return_value=state_json)

        result = await manager.upload_part("abc123", 3, "etag-003")
        assert result["uploaded_parts"] == 3


class TestChunkedUploadManagerCompleteUpload:
    """验证 complete_upload 完成分片上传"""

    async def test_complete_returns_full_state(self) -> None:
        """完成时返回完整状态"""
        cache = _make_cache()
        manager = ChunkedUploadManager(cache)

        parts = [{"part_number": i, "etag": f"etag-{i}"} for i in range(1, 4)]
        state_json = _make_state_json(uploaded_parts=parts)
        cache.get = AsyncMock(return_value=state_json)

        state = await manager.complete_upload("abc123")
        assert state.upload_id == "abc123"
        assert len(state.uploaded_parts) == 3

    async def test_complete_deletes_redis_key(self) -> None:
        """完成后应删除 Redis 中的状态键"""
        cache = _make_cache()
        manager = ChunkedUploadManager(cache)

        state_json = _make_state_json()
        cache.get = AsyncMock(return_value=state_json)

        await manager.complete_upload("abc123")
        cache.delete.assert_called_once_with(f"{_CHUNKED_UPLOAD_PREFIX}abc123")

    async def test_complete_nonexistent_raises(self) -> None:
        """upload_id 不存在抛出 ValueError"""
        cache = _make_cache()
        manager = ChunkedUploadManager(cache)
        cache.get = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError, match="不存在或已过期"):
            await manager.complete_upload("bad-id")


class TestChunkedUploadManagerResumeUpload:
    """验证 resume_upload 断点续传查询"""

    async def test_resume_returns_state_and_remaining(self) -> None:
        """返回上传状态和剩余分片列表"""
        cache = _make_cache()
        manager = ChunkedUploadManager(cache)

        file_size = 300 * 1024 * 1024
        chunk_size = MEDIUM_PART_SIZE
        total_parts = (file_size + chunk_size - 1) // chunk_size

        state_json = _make_state_json(
            file_size=file_size,
            chunk_size=chunk_size,
            uploaded_parts=[{"part_number": 1, "etag": "e1"}],
        )
        cache.get = AsyncMock(return_value=state_json)

        result = await manager.resume_upload("abc123")
        assert result is not None
        assert result["upload_id"] == "abc123"
        assert result["uploaded_parts"] == [{"part_number": 1, "etag": "e1"}]
        assert 1 not in result["remaining_parts"]
        assert len(result["remaining_parts"]) == total_parts - 1

    async def test_resume_nonexistent_returns_none(self) -> None:
        """不存在的 upload_id 返回 None"""
        cache = _make_cache()
        manager = ChunkedUploadManager(cache)
        cache.get = AsyncMock(return_value=None)

        result = await manager.resume_upload("bad-id")
        assert result is None

    async def test_resume_all_parts_uploaded_empty_remaining(self) -> None:
        """所有分片已上传，remaining_parts 为空"""
        cache = _make_cache()
        manager = ChunkedUploadManager(cache)

        file_size = 200 * 1024 * 1024
        chunk_size = MEDIUM_PART_SIZE
        total_parts = (file_size + chunk_size - 1) // chunk_size
        all_parts = [{"part_number": i, "etag": f"e{i}"} for i in range(1, total_parts + 1)]

        state_json = _make_state_json(
            file_size=file_size,
            chunk_size=chunk_size,
            uploaded_parts=all_parts,
        )
        cache.get = AsyncMock(return_value=state_json)

        result = await manager.resume_upload("abc123")
        assert result is not None
        assert result["remaining_parts"] == []


class TestChunkedUploadManagerConcurrency:
    """验证分布式锁（SET NX + Lua）"""

    async def test_acquire_lock_returns_true_when_available(self) -> None:
        """锁未被占用时 acquire 返回 True"""
        cache = _make_cache()
        cache.set_nx = AsyncMock(return_value=True)
        manager = ChunkedUploadManager(cache)
        acquired = await manager._acquire_lock("id-1")
        assert acquired is True
        cache.set_nx.assert_called_once()
        key = cache.set_nx.call_args[0][0]
        assert key.startswith(_LOCK_PREFIX)
        assert key.endswith("id-1")

    async def test_acquire_lock_returns_false_when_held(self) -> None:
        """锁已被其他进程持有时 acquire 返回 False"""
        cache = _make_cache()
        cache.set_nx = AsyncMock(return_value=False)
        manager = ChunkedUploadManager(cache)
        acquired = await manager._acquire_lock("id-1")
        assert acquired is False

    async def test_lock_per_upload_id(self) -> None:
        """不同 upload_id 使用不同的锁"""
        cache = _make_cache()
        cache.set_nx = AsyncMock(return_value=True)
        cache.eval = AsyncMock(return_value=1)
        manager = ChunkedUploadManager(cache)
        acq1 = await manager._acquire_lock("id-1")
        acq2 = await manager._acquire_lock("id-2")
        assert acq1 is True
        assert acq2 is True

    async def test_same_upload_id_reuses_lock(self) -> None:
        """相同 upload_id 获取锁后再次获取返回 False（锁已被持有）"""
        cache = _make_cache()
        cache.set_nx = AsyncMock(return_value=True)
        cache.eval = AsyncMock(return_value=1)
        manager = ChunkedUploadManager(cache)
        acq1 = await manager._acquire_lock("id-1")
        assert acq1 is True
        # 再次获取同一 id 的锁，set_nx 返回 False（锁已被持有）
        cache.set_nx.return_value = False
        acq2 = await manager._acquire_lock("id-1")
        assert acq2 is False

    async def test_release_lock_clears_owner(self) -> None:
        """release_lock 清除本地 owner 记录"""
        cache = _make_cache()
        cache.set_nx = AsyncMock(return_value=True)
        cache.eval = AsyncMock(return_value=1)
        manager = ChunkedUploadManager(cache)

        await manager._acquire_lock("id-1")
        assert "id-1" in manager._lock_owners

        await manager._release_lock("id-1")
        assert "id-1" not in manager._lock_owners
        cache.eval.assert_called_once()

    async def test_release_lock_noop_when_not_owner(self) -> None:
        """未持有锁时 release_lock 不执行任何操作"""
        cache = _make_cache()
        manager = ChunkedUploadManager(cache)
        await manager._release_lock("id-1")
        assert not hasattr(cache, "eval") or cache.eval.call_count == 0


class TestChunkedUploadManagerGetMultipartInfo:
    """验证 get_multipart_info 获取 MinIO 分片上下文"""

    async def test_returns_minio_upload_id_and_object_key(self) -> None:
        """返回 minio_upload_id 和 object_key"""
        cache = _make_cache()
        manager = ChunkedUploadManager(cache)

        state_json = _make_state_json(
            minio_upload_id="minio-123",
            object_key="docs/user/file.pdf",
        )
        cache.get = AsyncMock(return_value=state_json)

        result = await manager.get_multipart_info("abc123")
        assert result is not None
        assert result["minio_upload_id"] == "minio-123"
        assert result["object_key"] == "docs/user/file.pdf"

    async def test_returns_none_when_state_not_found(self) -> None:
        """upload_id 不存在返回 None"""
        cache = _make_cache()
        manager = ChunkedUploadManager(cache)
        cache.get = AsyncMock(return_value=None)

        result = await manager.get_multipart_info("bad-id")
        assert result is None

    async def test_returns_none_values_when_minio_fields_not_set(self) -> None:
        """minio 字段未设置时返回 None 值"""
        cache = _make_cache()
        manager = ChunkedUploadManager(cache)

        state_json = _make_state_json(minio_upload_id=None, object_key=None)
        cache.get = AsyncMock(return_value=state_json)

        result = await manager.get_multipart_info("abc123")
        assert result is not None
        assert result["minio_upload_id"] is None
        assert result["object_key"] is None
