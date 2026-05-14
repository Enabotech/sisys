"""Tests for MemoryService L0StoragePort dependency injection.

RED PHASE: 验证 MemoryService 使用 L0StoragePort 接口而非具体实现。
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from src.domain.ports.l0_storage import L0StoragePort
from src.domain.ports.memory_repository import (
    L2ChangeHistoryRepositoryPort,
    L2MetadataRepositoryPort,
)
from src.domain.services.memory_service import (
    MemoryDeleteRequest,
    MemorySaveRequest,
    MemoryService,
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


class TestMemoryServiceL0StoragePortInjection:
    """验证 MemoryService 使用 L0StoragePort 接口。"""

    def test_constructor_accepts_l0_storage_port(self) -> None:
        """验证构造函数接受 L0StoragePort 类型参数。"""
        mock_repo = AsyncMock(spec=L2MetadataRepositoryPort)
        mock_history = AsyncMock(spec=L2ChangeHistoryRepositoryPort)
        mock_l0 = AsyncMock(spec=L0StoragePort)

        service = MemoryService(
            text_extractor=MockTextExtractor(),
            compressor=MockCompressor(),
            metadata_repository=mock_repo,
            history_repository=mock_history,
            l0_storage=mock_l0,
        )

        assert service._l0_storage is not None
        # Verify it has the required methods (Protocol structural typing)
        assert hasattr(service._l0_storage, "write"), "l0_storage should have write method"
        assert hasattr(service._l0_storage, "read"), "l0_storage should have read method"
        assert hasattr(service._l0_storage, "delete"), "l0_storage should have delete method"

    def test_constructor_l0_storage_is_optional(self) -> None:
        """验证 l0_storage 参数是可选的。"""
        mock_repo = AsyncMock(spec=L2MetadataRepositoryPort)
        mock_history = AsyncMock(spec=L2ChangeHistoryRepositoryPort)

        service = MemoryService(
            text_extractor=MockTextExtractor(),
            compressor=MockCompressor(),
            metadata_repository=mock_repo,
            history_repository=mock_history,
        )

        assert service._l0_storage is None

    def test_l0_storage_write_called_when_saving(self, tmp_path: Any) -> None:
        """验证保存记忆时调用 L0StoragePort.write()。"""
        mock_repo = AsyncMock(spec=L2MetadataRepositoryPort)
        mock_repo.save = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)
        mock_history = AsyncMock(spec=L2ChangeHistoryRepositoryPort)
        mock_history.save = AsyncMock()
        mock_history.get_by_memory_id = AsyncMock(return_value=[])

        mock_l0 = AsyncMock(spec=L0StoragePort)

        service = MemoryService(
            text_extractor=MockTextExtractor(),
            compressor=MockCompressor(),
            metadata_repository=mock_repo,
            history_repository=mock_history,
            l0_storage=mock_l0,
        )

        request = MemorySaveRequest(
            user_id="test-user",
            name="test-memory",
            content="测试内容",
            memory_type="user",
            description="测试描述",
        )

        asyncio.run(service.save(request))

        mock_l0.write.assert_called_once()
        call_args = mock_l0.write.call_args
        assert call_args[0][0] is not None  # memory_id (UUID as str)

    def test_l0_storage_delete_called_when_deleting(self, tmp_path: Any) -> None:
        """验证删除记忆时调用 L0StoragePort.delete()。"""
        mock_repo = AsyncMock(spec=L2MetadataRepositoryPort)
        mock_history = AsyncMock(spec=L2ChangeHistoryRepositoryPort)

        mock_l0 = AsyncMock(spec=L0StoragePort)

        memory_id = uuid4()
        service = MemoryService(
            text_extractor=MockTextExtractor(),
            compressor=MockCompressor(),
            metadata_repository=mock_repo,
            history_repository=mock_history,
            l0_storage=mock_l0,
        )

        request = MemoryDeleteRequest(
            memory_id=memory_id,
            user_id="test-user",
        )

        asyncio.run(service.delete(request))

        mock_l0.delete.assert_called_once()
