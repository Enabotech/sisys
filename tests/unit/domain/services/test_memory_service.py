"""Tests for MemoryService.

RED PHASE: 验证 MemoryService CRUD 操作。
"""

from __future__ import annotations

import pytest

from src.application.text_processing.l1_compressor import L1Compressor
from src.application.text_processing.l1_text_extractor import L1TextExtractor
from src.domain.services.memory_service import (
    MemoryDeleteRequest,
    MemoryNotFoundError,
    MemorySaveRequest,
    MemoryService,
    MemoryUpdateRequest,
)


class TestMemoryServiceSave:
    """MemoryService save 操作验证"""

    def test_save_creates_memory(self):
        """验证 save 创建记忆"""
        service = MemoryService(
            text_extractor=L1TextExtractor(),
            compressor=L1Compressor(),
        )
        request = MemorySaveRequest(
            user_id="user123",
            name="bun-npm",
            content="记住，以后用 bun 而不是 npm",
            memory_type="user",
            description="包管理器偏好",
        )
        memory = service.save(request)
        assert memory.name == "bun-npm"
        assert memory.user_id == "user123"
        assert memory.version == 1
        assert "bun" in memory.content

    def test_save_extracts_and_compresses(self):
        """验证 save 提取和压缩内容"""
        service = MemoryService(
            text_extractor=L1TextExtractor(),
            compressor=L1Compressor(),
        )
        request = MemorySaveRequest(
            user_id="user123",
            name="test-memory",
            content="记住，这是一个很长的记忆内容需要压缩",
        )
        memory = service.save(request)
        # 压缩后内容应该变短
        assert len(memory.content) <= len("记住，这是一个很长的记忆内容需要压缩")


class TestMemoryServiceUpdate:
    """MemoryService update 操作验证"""

    def test_update_modifies_memory(self):
        """验证 update 修改记忆"""
        service = MemoryService(
            text_extractor=L1TextExtractor(),
            compressor=L1Compressor(),
        )
        # 先创建
        request = MemorySaveRequest(
            user_id="user123",
            name="original",
            content="记住原始内容",
        )
        memory = service.save(request)

        # 再更新
        update_request = MemoryUpdateRequest(
            memory_id=memory.memory_id,
            user_id="user123",
            name="updated",
            content="改成新内容",
        )
        updated = service.update(update_request)
        assert updated.name == "updated"
        assert updated.version == 2

    def test_update_nonexistent_raises(self):
        """验证更新不存在的记忆抛出异常"""
        service = MemoryService(
            text_extractor=L1TextExtractor(),
            compressor=L1Compressor(),
        )
        request = MemoryUpdateRequest(
            memory_id="nonexistent",
            user_id="user123",
        )
        with pytest.raises(MemoryNotFoundError):
            service.update(request)


class TestMemoryServiceDelete:
    """MemoryService delete 操作验证"""

    def test_delete_removes_memory(self):
        """验证 delete 删除记忆"""
        service = MemoryService(
            text_extractor=L1TextExtractor(),
            compressor=L1Compressor(),
        )
        # 先创建
        request = MemorySaveRequest(
            user_id="user123",
            name="to-delete",
            content="记住要删除的内容",
        )
        memory = service.save(request)

        # 再删除
        delete_request = MemoryDeleteRequest(
            memory_id=memory.memory_id,
            user_id="user123",
        )
        service.delete(delete_request)

        # 验证已删除
        with pytest.raises(MemoryNotFoundError):
            service.get(memory.memory_id)

    def test_delete_nonexistent_raises(self):
        """验证删除不存在的记忆抛出异常"""
        service = MemoryService(
            text_extractor=L1TextExtractor(),
            compressor=L1Compressor(),
        )
        request = MemoryDeleteRequest(
            memory_id="nonexistent",
            user_id="user123",
        )
        with pytest.raises(MemoryNotFoundError):
            service.delete(request)


class TestMemoryServiceList:
    """MemoryService list 操作验证"""

    def test_list_returns_user_memories(self):
        """验证 list 返回用户记忆"""
        service = MemoryService(
            text_extractor=L1TextExtractor(),
            compressor=L1Compressor(),
        )
        # 创建多个记忆
        for i in range(3):
            service.save(
                MemorySaveRequest(
                    user_id="user123",
                    name=f"memory-{i}",
                    content=f"记住内容 {i}",
                )
            )
        # 创建另一个用户的记忆
        service.save(
            MemorySaveRequest(
                user_id="other-user",
                name="other-memory",
                content="记住其他内容",
            )
        )

        # 列出 user123 的记忆
        memories = service.list("user123")
        assert len(memories) == 3
        assert all(m.user_id == "user123" for m in memories)


class TestMemoryServiceGet:
    """MemoryService get 操作验证"""

    def test_get_returns_memory(self):
        """验证 get 返回记忆"""
        service = MemoryService(
            text_extractor=L1TextExtractor(),
            compressor=L1Compressor(),
        )
        request = MemorySaveRequest(
            user_id="user123",
            name="test-get",
            content="记住测试内容",
        )
        created = service.save(request)

        retrieved = service.get(created.memory_id)
        assert retrieved.memory_id == created.memory_id
        assert retrieved.name == created.name


class TestMemoryServiceVersionConflict:
    """MemoryService 版本冲突验证"""

    def test_update_increments_version(self):
        """验证 update 递增版本"""
        service = MemoryService(
            text_extractor=L1TextExtractor(),
            compressor=L1Compressor(),
        )
        request = MemorySaveRequest(
            user_id="user123",
            name="version-test",
            content="记住初始内容",
        )
        memory = service.save(request)
        assert memory.version == 1

        # 更新
        update_request = MemoryUpdateRequest(
            memory_id=memory.memory_id,
            user_id="user123",
            content="改成新内容",
        )
        updated = service.update(update_request)
        assert updated.version == 2

    def test_multiple_updates_increment_version(self):
        """验证多次更新递增版本"""
        service = MemoryService(
            text_extractor=L1TextExtractor(),
            compressor=L1Compressor(),
        )
        request = MemorySaveRequest(
            user_id="user123",
            name="multi-update",
            content="记住内容",
        )
        memory = service.save(request)

        for i in range(3):
            service.update(
                MemoryUpdateRequest(
                    memory_id=memory.memory_id,
                    user_id="user123",
                    content=f"改成内容 {i}",
                )
            )

        updated = service.get(memory.memory_id)
        assert updated.version == 4  # 1 + 3
