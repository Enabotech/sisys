"""Unit tests for PostgreSQLMemoryMetadataRepository.

TDD 阶段：红 → 绿
验证 PostgreSQL 记忆元数据仓储 CRUD 操作。
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.domain.entities.memory_metadata import MemoryMetadata
from src.infrastructure.storage.postgresql.memory_metadata_repository import (
    MemoryVersionConflictError,
    PostgreSQLMemoryMetadataRepository,
)


def run_async(coro):
    """Run async coroutine synchronously for tests."""
    return asyncio.run(coro)


class MockResult:
    """Mock SQLAlchemy execute result."""

    def __init__(self, scalar_one_or_none=None, scalars_all=None):
        self._scalar_one_or_none = scalar_one_or_none
        self._scalars_all = scalars_all

    def scalar_one_or_none(self):
        return self._scalar_one_or_none

    def scalars(self):
        return self


class MockScalars:
    """Mock scalars result."""

    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class TestMemoryVersionConflictError:
    """MemoryVersionConflictError 异常测试。"""

    def test_exception_has_memory_id(self):
        """异常应包含 memory_id。"""
        memory_id = uuid4()
        error = MemoryVersionConflictError(memory_id=memory_id)
        assert error.memory_id == memory_id
        assert "版本冲突" in error.message
        assert str(memory_id) in error.message

    def test_exception_message_format(self):
        """异常消息格式正确。"""
        memory_id = uuid4()
        error = MemoryVersionConflictError(memory_id=memory_id)
        assert error.message == f"版本冲突: memory_id={memory_id}"


class TestPostgreSQLMemoryMetadataRepositoryInit:
    """PostgreSQLMemoryMetadataRepository 初始化测试。"""

    def test_repository_initialization(self):
        """验证仓库正确初始化。"""
        mock_session = AsyncMock()
        repo = PostgreSQLMemoryMetadataRepository(session=mock_session)
        assert repo._session == mock_session


class TestPostgreSQLMemoryMetadataRepositorySave:
    """PostgreSQLMemoryMetadataRepository save 操作测试。"""

    @pytest.fixture
    def mock_session(self):
        """Mock AsyncSession."""
        return AsyncMock()

    @pytest.fixture
    def repo(self, mock_session):
        """Create repository with mock session."""
        return PostgreSQLMemoryMetadataRepository(session=mock_session)

    @pytest.fixture
    def sample_metadata(self):
        """Sample MemoryMetadata entity."""
        return MemoryMetadata(
            memory_id=uuid4(),
            name="test-memory",
            type="user",
            user_id="user123",
            description="test description",
            path="user/test-memory.md",
            version=1,
        )

    def test_save_insert_new_metadata(self, repo, mock_session, sample_metadata):
        """验证保存新记录执行插入。"""
        mock_session.execute = AsyncMock(return_value=MockResult(scalar_one_or_none=None))
        mock_session.flush = AsyncMock()

        run_async(repo.save(sample_metadata))

        mock_session.execute.assert_called()
        mock_session.add.assert_called()
        mock_session.flush.assert_called()

    def test_save_update_existing_metadata(self, repo, mock_session, sample_metadata):
        """验证更新已存在记录。"""
        existing = MagicMock()
        existing.version = 1
        existing.memory_id = sample_metadata.memory_id
        mock_session.execute = AsyncMock(return_value=MockResult(scalar_one_or_none=existing))
        mock_session.flush = AsyncMock()

        sample_metadata.version = 2
        run_async(repo.save(sample_metadata))

        mock_session.execute.assert_called()
        mock_session.flush.assert_called()

    def test_save_raises_version_conflict(self, repo, mock_session, sample_metadata):
        """验证版本冲突时抛出异常。"""
        existing = MagicMock()
        existing.version = 2
        existing.memory_id = sample_metadata.memory_id
        mock_session.execute = AsyncMock(return_value=MockResult(scalar_one_or_none=existing))

        sample_metadata.version = 1
        with pytest.raises(MemoryVersionConflictError) as exc_info:
            run_async(repo.save(sample_metadata))

        assert exc_info.value.memory_id == sample_metadata.memory_id


class TestPostgreSQLMemoryMetadataRepositoryGet:
    """PostgreSQLMemoryMetadataRepository get 操作测试。"""

    @pytest.fixture
    def mock_session(self):
        """Mock AsyncSession."""
        return AsyncMock()

    @pytest.fixture
    def repo(self, mock_session):
        """Create repository with mock session."""
        return PostgreSQLMemoryMetadataRepository(session=mock_session)

    @pytest.fixture
    def sample_model(self):
        """Sample MemoryMetadataModel."""
        model = MagicMock()
        model.memory_id = uuid4()
        model.user_id = "user123"
        model.name = "test-memory"
        model.description = "test description"
        model.type = "user"
        model.path = "user/test-memory.md"
        model.version = 1
        model.mtime = datetime.now(UTC)
        model.owner = ""
        model.group_id = ""
        model.created_at = datetime.now(UTC)
        model.updated_at = datetime.now(UTC)
        return model

    def test_get_by_id_returns_metadata(self, repo, mock_session, sample_model):
        """验证 get_by_id 返回记忆元数据。"""
        mock_session.execute = AsyncMock(return_value=MockResult(scalar_one_or_none=sample_model))

        result = run_async(repo.get_by_id(sample_model.memory_id))

        assert result is not None
        assert result.memory_id == sample_model.memory_id
        assert result.name == sample_model.name

    def test_get_by_id_returns_none_when_not_found(self, repo, mock_session):
        """验证 get_by_id 查询不到时返回 None。"""
        mock_session.execute = AsyncMock(return_value=MockResult(scalar_one_or_none=None))

        result = run_async(repo.get_by_id(uuid4()))

        assert result is None

    def test_get_by_name_returns_metadata(self, repo, mock_session, sample_model):
        """验证 get_by_name 返回记忆元数据。"""
        mock_session.execute = AsyncMock(return_value=MockResult(scalar_one_or_none=sample_model))

        result = run_async(repo.get_by_name("test-memory"))

        assert result is not None
        assert result.name == sample_model.name

    def test_get_by_name_returns_none_when_not_found(self, repo, mock_session):
        """验证 get_by_name 查询不到时返回 None。"""
        mock_session.execute = AsyncMock(return_value=MockResult(scalar_one_or_none=None))

        result = run_async(repo.get_by_name("nonexistent"))

        assert result is None


class TestPostgreSQLMemoryMetadataRepositoryDelete:
    """PostgreSQLMemoryMetadataRepository delete 操作测试。"""

    @pytest.fixture
    def mock_session(self):
        """Mock AsyncSession."""
        return AsyncMock()

    @pytest.fixture
    def repo(self, mock_session):
        """Create repository with mock session."""
        return PostgreSQLMemoryMetadataRepository(session=mock_session)

    def test_delete_soft_deletes(self, repo, mock_session):
        """验证 delete 执行软删除。"""
        memory_id = uuid4()
        mock_session.execute = AsyncMock()
        mock_session.flush = AsyncMock()

        run_async(repo.delete(memory_id))

        mock_session.execute.assert_called()
        mock_session.flush.assert_called()


class TestPostgreSQLMemoryMetadataRepositoryList:
    """PostgreSQLMemoryMetadataRepository list 操作测试。"""

    @pytest.fixture
    def mock_session(self):
        """Mock AsyncSession."""
        return AsyncMock()

    @pytest.fixture
    def repo(self, mock_session):
        """Create repository with mock session."""
        return PostgreSQLMemoryMetadataRepository(session=mock_session)

    @pytest.fixture
    def sample_models(self):
        """Sample list of MemoryMetadataModel."""
        model1 = MagicMock()
        model1.memory_id = uuid4()
        model1.user_id = "user123"
        model1.name = "memory1"
        model1.description = "desc1"
        model1.type = "user"
        model1.path = "user/memory1.md"
        model1.version = 1
        model1.mtime = datetime.now(UTC)
        model1.owner = ""
        model1.group_id = ""
        model1.created_at = datetime.now(UTC)
        model1.updated_at = datetime.now(UTC)

        model2 = MagicMock()
        model2.memory_id = uuid4()
        model2.user_id = "user123"
        model2.name = "memory2"
        model2.description = "desc2"
        model2.type = "user"
        model2.path = "user/memory2.md"
        model2.version = 1
        model2.mtime = datetime.now(UTC)
        model2.owner = ""
        model2.group_id = ""
        model2.created_at = datetime.now(UTC)
        model2.updated_at = datetime.now(UTC)

        return [model1, model2]

    def test_list_by_user_returns_memories(self, repo, mock_session, sample_models):
        """验证 list_by_user 返回用户记忆列表。"""
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MockScalars(sample_models))
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = run_async(repo.list_by_user("user123"))

        assert len(result) == 2
        assert result[0].name == "memory1"
        assert result[1].name == "memory2"

    def test_list_by_user_returns_empty_when_no_memories(self, repo, mock_session):
        """验证 list_by_user 无记录时返回空列表。"""
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MockScalars([]))
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = run_async(repo.list_by_user("nonexistent"))

        assert result == []

    def test_list_by_type_returns_memories(self, repo, mock_session, sample_models):
        """验证 list_by_type 返回指定类型记忆列表。"""
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MockScalars(sample_models))
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = run_async(repo.list_by_type("user"))

        assert len(result) == 2

    def test_list_by_type_returns_empty_when_no_memories(self, repo, mock_session):
        """验证 list_by_type 无记录时返回空列表。"""
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MockScalars([]))
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = run_async(repo.list_by_type("nonexistent"))

        assert result == []

    def test_list_all_returns_all_memories(self, repo, mock_session, sample_models):
        """验证 list_all 返回所有记忆列表。"""
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MockScalars(sample_models))
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = run_async(repo.list_all())

        assert len(result) == 2

    def test_list_all_returns_empty_when_no_memories(self, repo, mock_session):
        """验证 list_all 无记录时返回空列表。"""
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MockScalars([]))
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = run_async(repo.list_all())

        assert result == []


class TestPostgreSQLMemoryMetadataRepositoryConverters:
    """PostgreSQLMemoryMetadataRepository 转换方法测试。"""

    @pytest.fixture
    def mock_session(self):
        """Mock AsyncSession."""
        return AsyncMock()

    @pytest.fixture
    def repo(self, mock_session):
        """Create repository with mock session."""
        return PostgreSQLMemoryMetadataRepository(session=mock_session)

    def test_to_entity_converts_model_correctly(self, repo):
        """验证 _to_entity 正确转换模型。"""
        model = MagicMock()
        model.memory_id = uuid4()
        model.user_id = "user123"
        model.name = "test-memory"
        model.description = "test description"
        model.type = "user"
        model.path = "user/test-memory.md"
        model.version = 1
        model.mtime = datetime.now(UTC)
        model.owner = "owner1"
        model.group_id = "group1"
        model.created_at = datetime.now(UTC)
        model.updated_at = datetime.now(UTC)

        entity = repo._to_entity(model)

        assert entity.memory_id == model.memory_id
        assert entity.user_id == model.user_id
        assert entity.name == model.name
        assert entity.description == model.description
        assert entity.type == model.type
        assert entity.path == model.path
        assert entity.version == model.version
        assert entity.owner == model.owner
        assert entity.group_id == model.group_id

    def test_to_entity_handles_none_description(self, repo):
        """验证 _to_entity 处理 None description。"""
        model = MagicMock()
        model.memory_id = uuid4()
        model.user_id = "user123"
        model.name = "test-memory"
        model.description = None
        model.type = "user"
        model.path = "user/test-memory.md"
        model.version = 1
        model.mtime = datetime.now(UTC)
        model.owner = None
        model.group_id = None
        model.created_at = datetime.now(UTC)
        model.updated_at = datetime.now(UTC)

        entity = repo._to_entity(model)

        assert entity.description == ""

    def test_to_model_converts_entity_correctly(self, repo):
        """验证 _to_model 正确转换实体。"""
        entity = MemoryMetadata(
            memory_id=uuid4(),
            name="test-memory",
            type="user",
            path="user/test-memory.md",
            user_id="user123",
            description="test description",
            version=1,
            owner="owner1",
            group_id="group1",
        )

        model = repo._to_model(entity)

        assert model.memory_id == entity.memory_id
        assert model.user_id == entity.user_id
        assert model.name == entity.name
        assert model.description == entity.description
        assert model.type == entity.type
        assert model.path == entity.path
        assert model.version == entity.version
        assert model.owner == entity.owner
        assert model.group_id == entity.group_id
