"""Tests for MemoryChangeHistoryRepository.

RED PHASE: 验证 L2 历史记录存储接口。
"""

from __future__ import annotations

import asyncio
import uuid

from src.domain.entities.memory_change_history import MemoryChangeHistory
from src.infrastructure.repositories.memory_change_history_repository import (
    InMemoryMemoryChangeHistoryRepository,
)


def run_async(coro):
    """Run async coroutine synchronously for tests."""
    return asyncio.run(coro)


class TestMemoryChangeHistoryRepositoryInit:
    """MemoryChangeHistoryRepository 初始化验证"""

    def test_init_creates_repository(self):
        """验证初始化仓储"""
        repo = InMemoryMemoryChangeHistoryRepository()
        assert repo is not None


class TestMemoryChangeHistoryRepositorySave:
    """MemoryChangeHistoryRepository 保存操作验证"""

    def test_save_creates_history(self):
        """验证保存创建历史记录"""
        repo = InMemoryMemoryChangeHistoryRepository()
        memory_id = uuid.uuid4()

        history = MemoryChangeHistory.create(
            memory_id=memory_id,
            version=1,
            change_type="create",
            changed_by="user123",
            changed_fields={"name": ["", "test-memory"]},
            diff_summary="name: -> test-memory",
        )
        run_async(repo.save(history))

        results = run_async(repo.get_by_memory_id(memory_id))
        assert len(results) == 1
        assert results[0].change_type == "create"

    def test_save_append_only(self):
        """验证 append-only 行为（不更新，只新增）"""
        repo = InMemoryMemoryChangeHistoryRepository()
        memory_id = uuid.uuid4()

        # 创建第一条记录
        history1 = MemoryChangeHistory.create(
            memory_id=memory_id,
            version=1,
            change_type="create",
            changed_by="user123",
        )
        run_async(repo.save(history1))

        # 创建第二条记录（更新）
        history2 = MemoryChangeHistory.create(
            memory_id=memory_id,
            version=2,
            change_type="update",
            changed_by="user123",
            changed_fields={"name": ["old", "new"]},
        )
        run_async(repo.save(history2))

        results = run_async(repo.get_by_memory_id(memory_id))
        assert len(results) == 2
        assert results[0].change_type == "create"
        assert results[1].change_type == "update"


class TestMemoryChangeHistoryRepositoryGet:
    """MemoryChangeHistoryRepository 查询操作验证"""

    def test_get_by_memory_id_existing(self):
        """验证获取已存在的历史记录"""
        repo = InMemoryMemoryChangeHistoryRepository()
        memory_id = uuid.uuid4()

        history = MemoryChangeHistory.create(
            memory_id=memory_id,
            version=1,
            change_type="create",
            changed_by="user123",
        )
        run_async(repo.save(history))

        results = run_async(repo.get_by_memory_id(memory_id))
        assert len(results) == 1
        assert results[0].memory_id == memory_id

    def test_get_by_memory_id_nonexistent(self):
        """验证获取不存在的历史记录返回空列表"""
        repo = InMemoryMemoryChangeHistoryRepository()
        results = run_async(repo.get_by_memory_id(uuid.uuid4()))
        assert results == []

    def test_get_by_id_existing(self):
        """验证通过 ID 获取历史记录"""
        repo = InMemoryMemoryChangeHistoryRepository()
        memory_id = uuid.uuid4()

        history = MemoryChangeHistory.create(
            memory_id=memory_id,
            version=1,
            change_type="create",
            changed_by="user123",
        )
        run_async(repo.save(history))

        result = run_async(repo.get_by_id(history.id))
        assert result is not None
        assert result.id == history.id

    def test_get_by_id_nonexistent(self):
        """验证通过 ID 获取不存在的历史记录返回 None"""
        repo = InMemoryMemoryChangeHistoryRepository()
        result = run_async(repo.get_by_id(uuid.uuid4()))
        assert result is None


class TestMemoryChangeHistoryRepositoryOrder:
    """MemoryChangeHistoryRepository 顺序验证"""

    def test_history_ordered_by_changed_at(self):
        """验证历史记录按时间排序"""
        repo = InMemoryMemoryChangeHistoryRepository()
        memory_id = uuid.uuid4()

        # 创建多个历史记录
        for i in range(3):
            history = MemoryChangeHistory.create(
                memory_id=memory_id,
                version=i + 1,
                change_type="update" if i > 0 else "create",
                changed_by="user123",
            )
            run_async(repo.save(history))

        results = run_async(repo.get_by_memory_id(memory_id))
        assert len(results) == 3
        # 验证按 version 升序排列（等于按 changed_at 升序）
        assert results[0].version == 1
        assert results[1].version == 2
        assert results[2].version == 3
