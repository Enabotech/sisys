"""Unit tests for MemoryService.

TDD 阶段：红 → 绿
验证 MemoryService CRUD 操作和事件发布
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.domain.entities.memory_change_history import MemoryChangeHistory
from src.domain.entities.memory_metadata import MemoryMetadata
from src.domain.events.memory_events import MemoryChanged
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
    MemoryVersionConflictError,
)


class MockTextExtractor:
    """Mock text extractor."""

    def extract(self, content: str) -> MagicMock:
        mock = MagicMock()
        mock.content = content.replace("记住", "").replace("改成", "").strip()
        return mock


class MockCompressor:
    """Mock compressor."""

    def compress(self, content: str) -> MagicMock:
        mock = MagicMock()
        mock.compressed = f"compressed: {content[:50]}"
        return mock


class MockEventPublisher:
    """Mock event publisher."""

    def __init__(self) -> None:
        self.published_events: list = []

    def publish(self, event: Any) -> None:
        self.published_events.append(event)


def run_async(coro: Any) -> Any:
    """Run async coroutine synchronously for tests."""
    return asyncio.run(coro)


class TestMemoryVersionConflictError:
    """MemoryVersionConflictError 异常测试"""

    def test_exception_has_memory_id(self):
        """异常应包含 memory_id"""
        memory_id = uuid4()
        error = MemoryVersionConflictError(memory_id=memory_id, message="版本冲突")
        assert error.memory_id == memory_id
        assert "版本冲突" in str(error)

    def test_exception_default_message(self):
        """异常应有默认消息（包含 memory_id）"""
        memory_id = uuid4()
        error = MemoryVersionConflictError(memory_id=memory_id)
        assert error.memory_id == memory_id
        assert error.message == f"版本冲突: memory_id={memory_id}"


class TestMemoryNotFoundError:
    """MemoryNotFoundError 异常测试"""

    def test_exception_has_memory_id(self):
        """异常应包含 memory_id"""
        memory_id = uuid4()
        error = MemoryNotFoundError(memory_id=memory_id)
        assert error.memory_id == memory_id


class TestMemoryServiceInit:
    """MemoryService 初始化测试"""

    def test_service_initialization(self):
        """验证服务正确初始化"""
        mock_repo = AsyncMock(spec=L2MetadataRepositoryPort)
        mock_history = AsyncMock(spec=L2ChangeHistoryRepositoryPort)
        service = MemoryService(
            text_extractor=MockTextExtractor(),
            compressor=MockCompressor(),
            metadata_repository=mock_repo,
            history_repository=mock_history,
        )
        assert service._text_extractor is not None
        assert service._compressor is not None
        assert service._metadata_repository is not None

    def test_service_with_optional_adapters(self):
        """验证服务支持可选适配器"""
        mock_repo = AsyncMock(spec=L2MetadataRepositoryPort)
        mock_history = AsyncMock(spec=L2ChangeHistoryRepositoryPort)
        mock_adapter = MagicMock()
        mock_publisher = MockEventPublisher()
        service = MemoryService(
            text_extractor=MockTextExtractor(),
            compressor=MockCompressor(),
            metadata_repository=mock_repo,
            history_repository=mock_history,
            l0_storage=mock_adapter,
            event_publisher=mock_publisher,
        )
        assert service._l0_storage is not None
        assert service._event_publisher is not None

    def test_service_without_optional_adapters(self):
        """验证服务可在没有可选适配器时工作"""
        mock_repo = AsyncMock(spec=L2MetadataRepositoryPort)
        mock_history = AsyncMock(spec=L2ChangeHistoryRepositoryPort)
        service = MemoryService(
            text_extractor=MockTextExtractor(),
            compressor=MockCompressor(),
            metadata_repository=mock_repo,
            history_repository=mock_history,
            l0_storage=None,
            event_publisher=None,
        )
        assert service._l0_storage is None
        assert service._event_publisher is None


class TestMemoryServiceSave:
    """MemoryService save 操作测试"""

    @pytest.fixture
    def mock_metadata_repo(self):
        """Mock metadata repository."""
        mock = AsyncMock(spec=L2MetadataRepositoryPort)
        mock.save = AsyncMock()
        mock.get_by_id = AsyncMock(return_value=None)
        return mock

    @pytest.fixture
    def mock_history_repo(self):
        """Mock history repository."""
        mock = AsyncMock(spec=L2MetadataRepositoryPort)
        mock.save = AsyncMock()
        mock.get_by_memory_id = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def mock_l0_storage(self):
        """Mock L0 storage adapter."""
        mock = AsyncMock()
        mock.write = AsyncMock()
        return mock

    @pytest.fixture
    def service(self, mock_metadata_repo, mock_history_repo, mock_l0_storage):
        """Create service with mocks."""
        return MemoryService(
            text_extractor=MockTextExtractor(),
            compressor=MockCompressor(),
            metadata_repository=mock_metadata_repo,
            history_repository=mock_history_repo,
            l0_storage=mock_l0_storage,
            event_publisher=None,
        )

    def test_save_creates_memory(self, service, mock_metadata_repo, mock_history_repo):
        """验证 save 创建记忆"""
        request = MemorySaveRequest(
            user_id="user123",
            name="test-memory",
            content="记住测试内容",
        )
        memory = run_async(service.save(request))

        assert memory.name == "test-memory"
        assert memory.user_id == "user123"
        assert memory.version == 1
        assert mock_metadata_repo.save.called
        assert mock_history_repo.save.called

    def test_save_with_event_publisher(self, mock_metadata_repo, mock_history_repo, mock_l0_storage):
        """验证 save 发布事件"""
        publisher = MockEventPublisher()
        service = MemoryService(
            text_extractor=MockTextExtractor(),
            compressor=MockCompressor(),
            metadata_repository=mock_metadata_repo,
            history_repository=mock_history_repo,
            l0_storage=mock_l0_storage,
            event_publisher=publisher,
        )
        request = MemorySaveRequest(
            user_id="user123",
            name="test-memory",
            content="记住测试内容",
        )
        run_async(service.save(request))

        assert len(publisher.published_events) == 1
        event = publisher.published_events[0]
        assert isinstance(event, MemoryChanged)
        assert event.change_type == "create"
        assert event.is_automatic is False

    def test_save_writes_to_l0(self, mock_metadata_repo, mock_history_repo, mock_l0_storage):
        """验证 save 写入 L0 文件系统"""
        service = MemoryService(
            text_extractor=MockTextExtractor(),
            compressor=MockCompressor(),
            metadata_repository=mock_metadata_repo,
            history_repository=mock_history_repo,
            l0_storage=mock_l0_storage,
            event_publisher=None,
        )
        request = MemorySaveRequest(
            user_id="user123",
            name="test-memory",
            content="记住测试内容",
            memory_type="user",
        )
        run_async(service.save(request))

        assert mock_l0_storage.write.called


class TestMemoryServiceUpdate:
    """MemoryService update 操作测试"""

    @pytest.fixture
    def mock_metadata_repo_with_data(self):
        """Mock metadata repository with existing data."""
        mock = AsyncMock(spec=L2MetadataRepositoryPort)
        existing_metadata = MemoryMetadata(
            memory_id=uuid4(),
            name="original",
            type="user",
            user_id="user123",
            description="original description",
            path="user/test.md",
            version=1,
        )
        mock.get_by_id = AsyncMock(return_value=existing_metadata)
        mock.save = AsyncMock()
        return mock

    @pytest.fixture
    def mock_history_repo(self):
        """Mock history repository."""
        mock = AsyncMock(spec=L2MetadataRepositoryPort)
        mock.save = AsyncMock()
        mock.get_by_memory_id = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def mock_l0_storage(self):
        """Mock L0 storage adapter."""
        mock = AsyncMock()
        mock.write = AsyncMock()
        return mock

    def test_update_modifies_memory(self, mock_metadata_repo_with_data, mock_history_repo, mock_l0_storage):
        """验证 update 修改记忆"""
        service = MemoryService(
            text_extractor=MockTextExtractor(),
            compressor=MockCompressor(),
            metadata_repository=mock_metadata_repo_with_data,
            history_repository=mock_history_repo,
            l0_storage=mock_l0_storage,
            event_publisher=None,
        )
        memory_id = mock_metadata_repo_with_data.get_by_id.return_value.memory_id
        request = MemoryUpdateRequest(
            memory_id=memory_id,
            user_id="user123",
            name="updated",
            content="改成新内容",
        )
        updated = run_async(service.update(request))

        assert updated.name == "updated"
        assert updated.version == 2

    def test_update_raises_not_found(self, mock_history_repo, mock_l0_storage):
        """验证更新不存在的记忆抛出异常"""
        mock_repo = AsyncMock(spec=L2MetadataRepositoryPort)
        mock_repo.get_by_id = AsyncMock(return_value=None)
        service = MemoryService(
            text_extractor=MockTextExtractor(),
            compressor=MockCompressor(),
            metadata_repository=mock_repo,
            history_repository=mock_history_repo,
            l0_storage=mock_l0_storage,
        )
        request = MemoryUpdateRequest(
            memory_id=uuid4(),
            user_id="user123",
        )
        with pytest.raises(MemoryNotFoundError):
            run_async(service.update(request))

    def test_update_content_only_changes_content(self, mock_metadata_repo_with_data, mock_history_repo, mock_l0_storage):
        """验证仅更新内容时其他字段不变"""
        service = MemoryService(
            text_extractor=MockTextExtractor(),
            compressor=MockCompressor(),
            metadata_repository=mock_metadata_repo_with_data,
            history_repository=mock_history_repo,
            l0_storage=mock_l0_storage,
            event_publisher=None,
        )
        memory_id = mock_metadata_repo_with_data.get_by_id.return_value.memory_id
        request = MemoryUpdateRequest(
            memory_id=memory_id,
            user_id="user123",
            content="改成仅内容变更",
        )
        updated = run_async(service.update(request))
        # content 被压缩后存储在 description 字段
        assert "compressed" in updated.description

    def test_update_name_only(self, mock_metadata_repo_with_data, mock_history_repo, mock_l0_storage):
        """验证仅更新名称"""
        service = MemoryService(
            text_extractor=MockTextExtractor(),
            compressor=MockCompressor(),
            metadata_repository=mock_metadata_repo_with_data,
            history_repository=mock_history_repo,
            l0_storage=mock_l0_storage,
            event_publisher=None,
        )
        memory_id = mock_metadata_repo_with_data.get_by_id.return_value.memory_id
        request = MemoryUpdateRequest(
            memory_id=memory_id,
            user_id="user123",
            name="new-name-only",
        )
        updated = run_async(service.update(request))
        assert updated.name == "new-name-only"

    def test_update_with_event_publisher(self, mock_metadata_repo_with_data, mock_history_repo, mock_l0_storage):
        """验证 update 发布事件"""
        publisher = MockEventPublisher()
        service = MemoryService(
            text_extractor=MockTextExtractor(),
            compressor=MockCompressor(),
            metadata_repository=mock_metadata_repo_with_data,
            history_repository=mock_history_repo,
            l0_storage=mock_l0_storage,
            event_publisher=publisher,
        )
        memory_id = mock_metadata_repo_with_data.get_by_id.return_value.memory_id
        request = MemoryUpdateRequest(
            memory_id=memory_id,
            user_id="user123",
            content="改成新内容",
        )
        run_async(service.update(request))

        assert len(publisher.published_events) == 1
        assert publisher.published_events[0].change_type == "update"


class TestMemoryServiceDelete:
    """MemoryService delete 操作测试"""

    @pytest.fixture
    def mock_metadata_repo_with_data(self):
        """Mock metadata repository with existing data."""
        mock = AsyncMock(spec=L2MetadataRepositoryPort)
        existing_metadata = MemoryMetadata(
            memory_id=uuid4(),
            name="to-delete",
            type="user",
            user_id="user123",
            description="description",
            path="user/test.md",
            version=1,
        )
        mock.get_by_id = AsyncMock(return_value=existing_metadata)
        mock.delete = AsyncMock()
        return mock

    @pytest.fixture
    def mock_history_repo(self):
        """Mock history repository."""
        mock = AsyncMock(spec=L2MetadataRepositoryPort)
        mock.save = AsyncMock()
        mock.get_by_memory_id = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def mock_l0_storage(self):
        """Mock L0 storage adapter."""
        mock = AsyncMock()
        mock.delete = AsyncMock()
        return mock

    def test_delete_removes_memory(self, mock_metadata_repo_with_data, mock_history_repo, mock_l0_storage):
        """验证 delete 删除记忆"""
        service = MemoryService(
            text_extractor=MockTextExtractor(),
            compressor=MockCompressor(),
            metadata_repository=mock_metadata_repo_with_data,
            history_repository=mock_history_repo,
            l0_storage=mock_l0_storage,
            event_publisher=None,
        )
        memory_id = mock_metadata_repo_with_data.get_by_id.return_value.memory_id
        request = MemoryDeleteRequest(
            memory_id=memory_id,
            user_id="user123",
        )
        run_async(service.delete(request))

        assert mock_metadata_repo_with_data.delete.called
        assert mock_l0_storage.delete.called

    def test_delete_raises_not_found(self, mock_history_repo, mock_l0_storage):
        """验证删除不存在的记忆抛出异常"""
        mock_repo = AsyncMock(spec=L2MetadataRepositoryPort)
        mock_repo.get_by_id = AsyncMock(return_value=None)
        service = MemoryService(
            text_extractor=MockTextExtractor(),
            compressor=MockCompressor(),
            metadata_repository=mock_repo,
            history_repository=mock_history_repo,
            l0_storage=mock_l0_storage,
        )
        request = MemoryDeleteRequest(
            memory_id=uuid4(),
            user_id="user123",
        )
        with pytest.raises(MemoryNotFoundError):
            run_async(service.delete(request))

    def test_delete_with_event_publisher(self, mock_metadata_repo_with_data, mock_history_repo, mock_l0_storage):
        """验证 delete 发布事件"""
        publisher = MockEventPublisher()
        service = MemoryService(
            text_extractor=MockTextExtractor(),
            compressor=MockCompressor(),
            metadata_repository=mock_metadata_repo_with_data,
            history_repository=mock_history_repo,
            l0_storage=mock_l0_storage,
            event_publisher=publisher,
        )
        memory_id = mock_metadata_repo_with_data.get_by_id.return_value.memory_id
        request = MemoryDeleteRequest(
            memory_id=memory_id,
            user_id="user123",
        )
        run_async(service.delete(request))

        assert len(publisher.published_events) == 1
        assert publisher.published_events[0].change_type == "delete"


class TestMemoryServiceList:
    """MemoryService list 操作测试"""

    @pytest.fixture
    def mock_metadata_repo(self):
        """Mock metadata repository."""
        mock = AsyncMock(spec=L2MetadataRepositoryPort)
        mock.list_by_user = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def mock_history_repo(self):
        """Mock history repository."""
        mock = AsyncMock(spec=L2MetadataRepositoryPort)
        return mock

    def test_list_returns_empty_for_new_user(self, mock_metadata_repo, mock_history_repo):
        """验证新用户返回空列表"""
        service = MemoryService(
            text_extractor=MockTextExtractor(),
            compressor=MockCompressor(),
            metadata_repository=mock_metadata_repo,
            history_repository=mock_history_repo,
        )
        memories = run_async(service.list("new-user"))
        assert memories == []

    def test_list_returns_user_memories(self, mock_history_repo):
        """验证 list 返回用户记忆"""
        memory_id = uuid4()
        mock_metadata_repo = AsyncMock(spec=L2MetadataRepositoryPort)
        mock_metadata_repo.list_by_user = AsyncMock(
            return_value=[
                MemoryMetadata(
                    memory_id=memory_id,
                    name="memory1",
                    type="user",
                    user_id="user123",
                    description="desc1",
                    path="user/test1.md",
                    version=1,
                )
            ]
        )
        mock_history_repo.get_by_memory_id = AsyncMock(
            return_value=[
                MemoryChangeHistory.create(
                    memory_id=memory_id,
                    version=1,
                    change_type="create",
                    changed_by="user123",
                    changed_fields={"content": "记忆内容1"},
                    diff_summary="创建记忆",
                )
            ]
        )
        service = MemoryService(
            text_extractor=MockTextExtractor(),
            compressor=MockCompressor(),
            metadata_repository=mock_metadata_repo,
            history_repository=mock_history_repo,
        )
        memories = run_async(service.list("user123"))

        assert len(memories) == 1
        assert memories[0].name == "memory1"


class TestMemoryServiceGet:
    """MemoryService get 操作测试"""

    @pytest.fixture
    def mock_metadata_repo(self):
        """Mock metadata repository."""
        mock = AsyncMock(spec=L2MetadataRepositoryPort)
        mock.get_by_id = AsyncMock(return_value=None)
        return mock

    @pytest.fixture
    def mock_history_repo(self):
        """Mock history repository."""
        mock = AsyncMock(spec=L2MetadataRepositoryPort)
        return mock

    def test_get_raises_not_found(self, mock_metadata_repo, mock_history_repo):
        """验证获取不存在的记忆抛出异常"""
        service = MemoryService(
            text_extractor=MockTextExtractor(),
            compressor=MockCompressor(),
            metadata_repository=mock_metadata_repo,
            history_repository=mock_history_repo,
        )
        with pytest.raises(MemoryNotFoundError):
            run_async(service.get(uuid4()))

    def test_get_returns_memory(self):
        """验证 get 返回记忆"""
        memory_id = uuid4()
        mock_metadata_repo = AsyncMock(spec=L2MetadataRepositoryPort)
        mock_metadata_repo.get_by_id = AsyncMock(
            return_value=MemoryMetadata(
                memory_id=memory_id,
                name="test-memory",
                type="user",
                user_id="user123",
                description="compressed content",
                path="user/test.md",
                version=1,
            )
        )
        mock_history_repo = AsyncMock(spec=L2MetadataRepositoryPort)
        mock_history_repo.get_by_memory_id = AsyncMock(
            return_value=[
                MemoryChangeHistory.create(
                    memory_id=memory_id,
                    version=1,
                    change_type="create",
                    changed_by="user123",
                    changed_fields={"content": "test content"},
                    diff_summary="创建记忆",
                )
            ]
        )
        service = MemoryService(
            text_extractor=MockTextExtractor(),
            compressor=MockCompressor(),
            metadata_repository=mock_metadata_repo,
            history_repository=mock_history_repo,
        )
        memory = run_async(service.get(memory_id))

        assert memory.memory_id == memory_id
        assert memory.name == "test-memory"


class TestMemoryServiceBuildMdContent:
    """MemoryService _build_md_content 方法测试"""

    def test_build_md_content_format(self):
        """验证 MD 内容格式"""
        mock_repo = AsyncMock(spec=L2MetadataRepositoryPort)
        mock_history = AsyncMock(spec=L2MetadataRepositoryPort)
        service = MemoryService(
            text_extractor=MockTextExtractor(),
            compressor=MockCompressor(),
            metadata_repository=mock_repo,
            history_repository=mock_history,
        )
        content = service._build_md_content(
            name="test-name",
            description="test description",
            memory_type="user",
            content="test memory content",
        )

        assert "---" in content
        assert "name: test-name" in content
        assert "description: test description" in content
        assert "type: user" in content
        assert "originSessionId:" in content
        assert "test memory content" in content
