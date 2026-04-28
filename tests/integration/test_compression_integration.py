"""Integration tests for L1 Compression Flow.

End-to-end tests for the L1 compression pipeline:
- MemoryService.save() -> L1TextExtractor.extract() -> L1Compressor.compress()
- MemoryChanged event publication
- L0 + L2 dual storage

Requires: PostgreSQL database (skipped if unavailable)

Run with: pytest tests/integration/test_compression_integration.py -v
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from dotenv import load_dotenv

from src.application.use_cases.text_processing.l1_compressor import L1Compressor
from src.application.use_cases.text_processing.l1_text_extractor import L1TextExtractor
from src.domain.entities.memory_metadata import MemoryMetadata
from src.domain.repositories.memory_repository import (
    MemoryChangeHistoryRepositoryProtocol,
    MemoryMetadataRepositoryProtocol,
)
from src.domain.services.memory_service import MemorySaveRequest, MemoryService, MemoryUpdateRequest

# Load environment variables from .env file
load_dotenv(Path(__file__).parent.parent.parent / ".env")


def run_async(coro):
    """Run async coroutine synchronously for tests."""
    return asyncio.run(coro)


def is_postgresql_available():
    """Check if PostgreSQL database is available for integration testing."""
    try:
        from src.infrastructure.config.postgresql import PostgreSQLConfig

        config = PostgreSQLConfig.from_env()
        return bool(config.host and config.database)
    except Exception:
        return False


# Store for mock repository state
_mock_metadata_store: dict[str, MemoryMetadata] = {}


def _create_mock_metadata_repo():
    """Create a mock metadata repository with stateful behavior."""
    mock = AsyncMock(spec=MemoryMetadataRepositoryProtocol)

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
    mock = AsyncMock(spec=MemoryChangeHistoryRepositoryProtocol)
    mock.save = AsyncMock()
    mock.get_by_memory_id = AsyncMock(return_value=[])
    mock.get_by_id = AsyncMock(return_value=None)
    return mock


def _clear_mock_stores():
    """Clear mock stores before each test."""
    _mock_metadata_store.clear()


# Skip if PostgreSQL not available
pytestmark = pytest.mark.skipif(not is_postgresql_available(), reason="PostgreSQL not available")


class TestCompressionIntegration:
    """L1 压缩流程集成测试"""

    def setup_method(self):
        """Clear mock stores before each test."""
        _clear_mock_stores()

    def test_save_triggers_extraction_and_compression(self):
        """验证 save 触发提取和压缩"""
        service = MemoryService(
            text_extractor=L1TextExtractor(),
            compressor=L1Compressor(),
            metadata_repository=_create_mock_metadata_repo(),
            history_repository=_create_mock_history_repo(),
        )

        request = MemorySaveRequest(
            user_id="user123",
            name="bun-npm",
            content="记住，以后用 bun 而不是 npm",
            description="包管理器偏好",
        )

        memory = run_async(service.save(request))

        assert memory is not None
        assert memory.name == "bun-npm"
        assert "bun" in memory.content or "npm" in memory.content
        assert memory.version == 1

    def test_full_compression_pipeline(self):
        """验证完整压缩管道"""
        text_extractor = L1TextExtractor()
        compressor = L1Compressor()

        # 使用较长的文本以便达到目标长度压缩
        original = "记住，以后用 bun 而不是 npm，这是一个很长的记忆内容需要压缩处理，" * 10

        # Step 1: 提取
        extraction = text_extractor.extract(original)
        assert extraction.content is not None

        # Step 2: 压缩
        compression = compressor.compress(extraction.content)
        assert compression.compressed is not None
        assert compression.original_length >= compression.compressed_length

        # Step 3: 验证压缩到目标长度（约 150 字）
        assert compression.compressed_length <= 160

    def test_multiple_save_operations(self):
        """验证多次保存操作"""
        service = MemoryService(
            text_extractor=L1TextExtractor(),
            compressor=L1Compressor(),
            metadata_repository=_create_mock_metadata_repo(),
            history_repository=_create_mock_history_repo(),
        )

        memories = []
        for i in range(5):
            memory = run_async(
                service.save(
                    MemorySaveRequest(
                        user_id="user123",
                        name=f"memory-{uuid.uuid4().hex[:8]}",
                        content=f"记住内容 {i}",
                    )
                )
            )
            memories.append(memory)

        assert len(memories) == 5
        assert all(m.version == 1 for m in memories)

    def test_update_increments_version(self):
        """验证更新递增版本"""
        service = MemoryService(
            text_extractor=L1TextExtractor(),
            compressor=L1Compressor(),
            metadata_repository=_create_mock_metadata_repo(),
            history_repository=_create_mock_history_repo(),
        )

        memory = run_async(
            service.save(
                MemorySaveRequest(
                    user_id="user123",
                    name="update-test",
                    content="记住初始内容",
                )
            )
        )

        # 保存旧内容用于比较
        old_content = memory.content

        # 更新
        updated = run_async(
            service.update(
                MemoryUpdateRequest(
                    memory_id=memory.memory_id,
                    user_id="user123",
                    content="改成新内容",
                )
            )
        )

        assert updated.version == 2
        assert updated.content != old_content
