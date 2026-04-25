"""Tests for MemoryMetadataRepository.

RED PHASE: 验证 L2 PostgreSQL 存储接口。
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from src.domain.entities.memory_metadata import MemoryMetadata
from src.infrastructure.repositories.memory_metadata_repository import (
    InMemoryMemoryMetadataRepository,
)


def run_async(coro):
    """Run async coroutine synchronously for tests."""
    return asyncio.run(coro)


class TestMemoryMetadataRepositoryInit:
    """MemoryMetadataRepository 初始化验证"""

    def test_init_creates_repository(self):
        """验证初始化仓储"""
        repo = InMemoryMemoryMetadataRepository()
        assert repo is not None


class TestMemoryMetadataRepositorySave:
    """MemoryMetadataRepository 保存操作验证"""

    def test_save_creates_metadata(self):
        """验证保存创建元数据"""
        repo = InMemoryMemoryMetadataRepository()
        metadata = MemoryMetadata.create(
            name="test-memory",
            memory_type="user",
            user_id="user123",
            description="测试记忆",
        )
        run_async(repo.save(metadata))

        result = run_async(repo.get_by_id(metadata.memory_id))
        assert result is not None
        assert result.name == "test-memory"
        assert result.type == "user"

    def test_save_updates_existing_metadata(self):
        """验证保存更新已有元数据（UPSERT）"""
        repo = InMemoryMemoryMetadataRepository()
        metadata = MemoryMetadata.create(
            name="test-memory",
            memory_type="user",
            user_id="user123",
        )
        run_async(repo.save(metadata))

        # 更新
        metadata.description = "更新后的描述"
        metadata.bump_version()
        run_async(repo.save(metadata))

        result = run_async(repo.get_by_id(metadata.memory_id))
        assert result is not None
        assert result.description == "更新后的描述"
        assert result.version == 2

    def test_save_with_version_conflict(self):
        """验证版本冲突检测"""
        repo = InMemoryMemoryMetadataRepository()
        metadata = MemoryMetadata.create(
            name="conflict-test",
            memory_type="user",
            user_id="user123",
        )
        run_async(repo.save(metadata))

        # 创建同 memory_id 的过期版本
        from src.infrastructure.repositories.memory_metadata_repository import (
            MemoryVersionConflictError,
        )

        metadata2 = MemoryMetadata(
            memory_id=metadata.memory_id,
            name="conflict-test",
            type="user",
            path=metadata.path,
            user_id="user123",
            version=1,  # 模拟过期版本
        )

        with pytest.raises(MemoryVersionConflictError):
            run_async(repo.save(metadata2))


class TestMemoryMetadataRepositoryGet:
    """MemoryMetadataRepository 查询操作验证"""

    def test_get_by_id_existing(self):
        """验证获取已存在的元数据"""
        repo = InMemoryMemoryMetadataRepository()
        metadata = MemoryMetadata.create(
            name="get-test",
            memory_type="user",
            user_id="user123",
        )
        run_async(repo.save(metadata))

        result = run_async(repo.get_by_id(metadata.memory_id))
        assert result is not None
        assert result.memory_id == metadata.memory_id

    def test_get_by_id_nonexistent(self):
        """验证获取不存在的元数据返回 None"""
        repo = InMemoryMemoryMetadataRepository()
        result = run_async(repo.get_by_id(uuid.uuid4()))
        assert result is None

    def test_get_by_name(self):
        """验证通过名称获取元数据"""
        repo = InMemoryMemoryMetadataRepository()
        metadata = MemoryMetadata.create(
            name="unique-test-name",
            memory_type="user",
            user_id="user123",
        )
        run_async(repo.save(metadata))

        result = run_async(repo.get_by_name("unique-test-name"))
        assert result is not None
        assert result.name == "unique-test-name"

    def test_get_by_name_nonexistent(self):
        """验证通过不存在的名称获取返回 None"""
        repo = InMemoryMemoryMetadataRepository()
        result = run_async(repo.get_by_name("nonexistent"))
        assert result is None


class TestMemoryMetadataRepositoryDelete:
    """MemoryMetadataRepository 删除操作验证"""

    def test_delete_existing(self):
        """验证删除已存在的元数据（软删除）"""
        repo = InMemoryMemoryMetadataRepository()
        metadata = MemoryMetadata.create(
            name="delete-test",
            memory_type="user",
            user_id="user123",
        )
        run_async(repo.save(metadata))

        # 删除
        run_async(repo.delete(metadata.memory_id))

        # 验证已删除（get_by_id 返回 None）
        result = run_async(repo.get_by_id(metadata.memory_id))
        assert result is None

    def test_delete_nonexistent_no_raise(self):
        """验证删除不存在的元数据不抛出异常"""
        repo = InMemoryMemoryMetadataRepository()
        run_async(repo.delete(uuid.uuid4()))  # 不应抛出异常


class TestMemoryMetadataRepositoryList:
    """MemoryMetadataRepository 列表操作验证"""

    def test_list_by_user(self):
        """验证列出用户的所有元数据"""
        repo = InMemoryMemoryMetadataRepository()
        run_async(repo.save(MemoryMetadata.create(name="mem-1", memory_type="user", user_id="u1")))
        run_async(repo.save(MemoryMetadata.create(name="mem-2", memory_type="user", user_id="u1")))
        run_async(repo.save(MemoryMetadata.create(name="mem-3", memory_type="user", user_id="u2")))

        results = run_async(repo.list_by_user("u1"))
        assert len(results) == 2

    def test_list_by_type(self):
        """验证列出指定类型的所有元数据"""
        repo = InMemoryMemoryMetadataRepository()
        run_async(repo.save(MemoryMetadata.create(name="mem-1", memory_type="user", user_id="u1")))
        run_async(repo.save(MemoryMetadata.create(name="mem-2", memory_type="feedback", user_id="u2")))
        run_async(repo.save(MemoryMetadata.create(name="mem-3", memory_type="user", user_id="u3")))

        results = run_async(repo.list_by_type("user"))
        assert len(results) == 2

    def test_list_all(self):
        """验证列出所有元数据"""
        repo = InMemoryMemoryMetadataRepository()
        run_async(repo.save(MemoryMetadata.create(name="mem-1", memory_type="user", user_id="u1")))
        run_async(repo.save(MemoryMetadata.create(name="mem-2", memory_type="feedback", user_id="u2")))

        results = run_async(repo.list_all())
        assert len(results) == 2


class TestMemoryMetadataRepositoryVersionConflict:
    """MemoryMetadataRepository 版本冲突验证"""

    def test_optimistic_locking(self):
        """验证乐观锁机制"""
        repo = InMemoryMemoryMetadataRepository()
        metadata = MemoryMetadata.create(
            name="lock-test",
            memory_type="user",
            user_id="user123",
        )
        run_async(repo.save(metadata))

        # 获取副本
        copy1 = run_async(repo.get_by_id(metadata.memory_id))
        copy2 = run_async(repo.get_by_id(metadata.memory_id))

        # copy1 先更新
        copy1.bump_version()
        run_async(repo.save(copy1))

        # copy2 更新时版本已过期，抛出冲突
        from src.infrastructure.repositories.memory_metadata_repository import (
            MemoryVersionConflictError,
        )

        copy2.bump_version()  # 与 copy1 相同的版本
        with pytest.raises(MemoryVersionConflictError):
            run_async(repo.save(copy2))
