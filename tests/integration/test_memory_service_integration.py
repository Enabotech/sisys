"""Tests for MemoryService.

RED PHASE: 验证 MemoryService CRUD 操作。
Uses mocks for repository layer to test MemoryService in isolation.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.application.use_cases.text_processing.l1_compressor import L1Compressor
from src.application.use_cases.text_processing.l1_text_extractor import L1TextExtractor
from src.domain.entities.memory_metadata import MemoryMetadata
from src.domain.ports.memory_repository import (
    L2ChangeHistoryRepositoryPort,
    L2MetadataRepositoryPort,
)
from src.domain.services.memory_service import (
    MemoryDeleteRequest,
    MemoryNotFoundError,
    MemorySaveRequest,
    MemoryService,
    MemoryUpdateRequest,
)


def run_async(coro):
    """Run async coroutine synchronously for tests."""
    return asyncio.run(coro)


# Store for mock repository state
_mock_metadata_store: dict[str, MemoryMetadata] = {}
_mock_history_store: list = []


def _create_mock_metadata_repo():
    """Create a mock metadata repository with stateful behavior."""
    mock = AsyncMock(spec=L2MetadataRepositoryPort)

    async def mock_save(metadata: MemoryMetadata) -> None:
        _mock_metadata_store[str(metadata.memory_id)] = metadata

    async def mock_get_by_id(memory_id: UUID) -> MemoryMetadata | None:
        return _mock_metadata_store.get(str(memory_id))

    async def mock_get_by_name(name: str) -> MemoryMetadata | None:
        for m in _mock_metadata_store.values():
            if m.name == name:
                return m
        return None

    async def mock_delete(memory_id: UUID) -> None:
        if str(memory_id) in _mock_metadata_store:
            del _mock_metadata_store[str(memory_id)]

    async def mock_list_by_user(user_id: str) -> list[MemoryMetadata]:
        return [m for m in _mock_metadata_store.values() if m.user_id == user_id]

    async def mock_list_by_type(memory_type: str) -> list[MemoryMetadata]:
        return [m for m in _mock_metadata_store.values() if m.type == memory_type]

    async def mock_list_all() -> list[MemoryMetadata]:
        return list(_mock_metadata_store.values())

    mock.save = mock_save
    mock.get_by_id = mock_get_by_id
    mock.get_by_name = mock_get_by_name
    mock.delete = mock_delete
    mock.list_by_user = mock_list_by_user
    mock.list_by_type = mock_list_by_type
    mock.list_all = mock_list_all
    return mock


def _create_mock_history_repo():
    """Create a mock history repository."""
    mock = AsyncMock(spec=L2ChangeHistoryRepositoryPort)
    mock.save = AsyncMock()
    mock.get_by_memory_id = AsyncMock(return_value=[])
    mock.get_by_id = AsyncMock(return_value=None)
    return mock


def _clear_mock_stores():
    """Clear mock stores before each test."""
    _mock_metadata_store.clear()
    _mock_history_store.clear()


def create_service():
    """Create a MemoryService with mock repositories."""
    _clear_mock_stores()
    return MemoryService(
        text_extractor=L1TextExtractor(),
        compressor=L1Compressor(),
        metadata_repository=_create_mock_metadata_repo(),
        history_repository=_create_mock_history_repo(),
    )


class TestMemoryServiceSave:
    """MemoryService save 操作验证"""

    def test_save_creates_memory(self):
        """验证 save 创建记忆"""
        service = create_service()
        request = MemorySaveRequest(
            user_id="user123",
            name="bun-npm",
            content="记住，以后用 bun 而不是 npm",
            memory_type="user",
            description="包管理器偏好",
        )
        memory = run_async(service.save(request))
        assert memory.name == "bun-npm"
        assert memory.user_id == "user123"
        assert memory.version == 1
        assert "bun" in memory.content

    def test_save_extracts_and_compresses(self):
        """验证 save 提取和压缩内容"""
        service = create_service()
        request = MemorySaveRequest(
            user_id="user123",
            name="test-memory",
            content="记住，这是一个很长的记忆内容需要压缩",
        )
        memory = run_async(service.save(request))
        # 压缩后内容应该变短
        assert len(memory.content) <= len("记住，这是一个很长的记忆内容需要压缩")


class TestMemoryServiceUpdate:
    """MemoryService update 操作验证"""

    def test_update_modifies_memory(self):
        """验证 update 修改记忆"""
        service = create_service()
        # 先创建
        request = MemorySaveRequest(
            user_id="user123",
            name="original",
            content="记住原始内容",
        )
        memory = run_async(service.save(request))

        # 再更新
        update_request = MemoryUpdateRequest(
            memory_id=memory.memory_id,
            user_id="user123",
            name="updated",
            content="改成新内容",
        )
        updated = run_async(service.update(update_request))
        assert updated.name == "updated"
        assert updated.version == 2

    def test_update_nonexistent_raises(self):
        """验证更新不存在的记忆抛出异常"""
        service = create_service()
        request = MemoryUpdateRequest(
            memory_id=uuid4(),
            user_id="user123",
        )
        with pytest.raises(MemoryNotFoundError):
            run_async(service.update(request))


class TestMemoryServiceDelete:
    """MemoryService delete 操作验证"""

    def test_delete_removes_memory(self):
        """验证 delete 删除记忆"""
        service = create_service()
        # 先创建
        request = MemorySaveRequest(
            user_id="user123",
            name="to-delete",
            content="记住要删除的内容",
        )
        memory = run_async(service.save(request))

        # 再删除
        delete_request = MemoryDeleteRequest(
            memory_id=memory.memory_id,
            user_id="user123",
        )
        run_async(service.delete(delete_request))

        # 验证已删除
        with pytest.raises(MemoryNotFoundError):
            run_async(service.get(memory.memory_id))

    def test_delete_nonexistent_raises(self):
        """验证删除不存在的记忆抛出异常"""
        service = create_service()
        request = MemoryDeleteRequest(
            memory_id=uuid4(),
            user_id="user123",
        )
        with pytest.raises(MemoryNotFoundError):
            run_async(service.delete(request))


class TestMemoryServiceList:
    """MemoryService list 操作验证"""

    def test_list_returns_user_memories(self):
        """验证 list 返回用户记忆"""
        service = create_service()
        # 创建多个记忆
        for i in range(3):
            run_async(
                service.save(
                    MemorySaveRequest(
                        user_id="user123",
                        name=f"memory-{i}",
                        content=f"记住内容 {i}",
                    )
                )
            )
        # 创建另一个用户的记忆
        run_async(
            service.save(
                MemorySaveRequest(
                    user_id="other-user",
                    name="other-memory",
                    content="记住其他内容",
                )
            )
        )

        # 列出 user123 的记忆
        memories = run_async(service.list("user123"))
        assert len(memories) == 3
        assert all(m.user_id == "user123" for m in memories)


class TestMemoryServiceGet:
    """MemoryService get 操作验证"""

    def test_get_returns_memory(self):
        """验证 get 返回记忆"""
        service = create_service()
        request = MemorySaveRequest(
            user_id="user123",
            name="test-get",
            content="记住测试内容",
        )
        created = run_async(service.save(request))

        retrieved = run_async(service.get(created.memory_id))
        assert retrieved.memory_id == created.memory_id
        assert retrieved.name == created.name


class TestMemoryServiceVersionConflict:
    """MemoryService 版本冲突验证"""

    def test_update_increments_version(self):
        """验证 update 递增版本"""
        service = create_service()
        request = MemorySaveRequest(
            user_id="user123",
            name="version-test",
            content="记住初始内容",
        )
        memory = run_async(service.save(request))
        assert memory.version == 1

        # 更新
        update_request = MemoryUpdateRequest(
            memory_id=memory.memory_id,
            user_id="user123",
            content="改成新内容",
        )
        updated = run_async(service.update(update_request))
        assert updated.version == 2

    def test_multiple_updates_increment_version(self):
        """验证多次更新递增版本"""
        service = create_service()
        request = MemorySaveRequest(
            user_id="user123",
            name="multi-update",
            content="记住内容",
        )
        memory = run_async(service.save(request))

        for i in range(3):
            run_async(
                service.update(
                    MemoryUpdateRequest(
                        memory_id=memory.memory_id,
                        user_id="user123",
                        content=f"改成内容 {i}",
                    )
                )
            )

        updated = run_async(service.get(memory.memory_id))
        assert updated.version == 4  # 1 + 3

    def test_update_with_file_adapter_writes_to_l0(self):
        """验证 update 调用 FileMemoryAdapter 更新 L0"""
        mock_adapter = MagicMock()
        mock_adapter.write = AsyncMock()
        mock_adapter.delete = AsyncMock()
        service = MemoryService(
            text_extractor=L1TextExtractor(),
            compressor=L1Compressor(),
            metadata_repository=_create_mock_metadata_repo(),
            history_repository=_create_mock_history_repo(),
            l0_storage=mock_adapter,
        )
        # 先创建
        request = MemorySaveRequest(
            user_id="user123",
            name="original",
            content="记住原始内容",
        )
        memory = run_async(service.save(request))

        # 重置 mock
        mock_adapter.reset_mock()

        # 再更新
        update_request = MemoryUpdateRequest(
            memory_id=memory.memory_id,
            user_id="user123",
            content="改成新内容",
        )
        run_async(service.update(update_request))

        # 验证 write 方法被调用（更新文件）
        assert mock_adapter.write.called, "FileMemoryAdapter.write() should be called"

    def test_delete_with_file_adapter_deletes_from_l0(self):
        """验证 delete 调用 FileMemoryAdapter 删除 L0"""
        mock_adapter = MagicMock()
        mock_adapter.write = AsyncMock()
        mock_adapter.delete = AsyncMock()
        service = MemoryService(
            text_extractor=L1TextExtractor(),
            compressor=L1Compressor(),
            metadata_repository=_create_mock_metadata_repo(),
            history_repository=_create_mock_history_repo(),
            l0_storage=mock_adapter,
        )
        # 先创建
        request = MemorySaveRequest(
            user_id="user123",
            name="to-delete",
            content="记住要删除的内容",
        )
        memory = run_async(service.save(request))

        # 重置 mock
        mock_adapter.reset_mock()

        # 再删除
        delete_request = MemoryDeleteRequest(
            memory_id=memory.memory_id,
            user_id="user123",
        )
        run_async(service.delete(delete_request))

        # 验证 delete 方法被调用
        assert mock_adapter.delete.called, "FileMemoryAdapter.delete() should be called"
        call_args = mock_adapter.delete.call_args
        assert call_args is not None
        memory_id, memory_type = call_args[0][:2]
        assert memory_type == "user"

    def test_service_without_file_adapter_still_works(self):
        """验证没有 FileMemoryAdapter 时服务仍正常工作"""
        service = MemoryService(
            text_extractor=L1TextExtractor(),
            compressor=L1Compressor(),
            metadata_repository=_create_mock_metadata_repo(),
            history_repository=_create_mock_history_repo(),
            l0_storage=None,  # 不提供 file_adapter
        )
        request = MemorySaveRequest(
            user_id="user123",
            name="no-file-adapter",
            content="记住，没有文件适配器",
            memory_type="user",
        )
        memory = run_async(service.save(request))
        assert memory.name == "no-file-adapter"
        assert memory.version == 1
