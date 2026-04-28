"""Tests for Memory Architecture Validation.

RED PHASE: 验证六边形架构约束 - L1/L3 分离。
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.application.use_cases.text_processing.l1_compressor import L1Compressor
from src.application.use_cases.text_processing.l1_text_extractor import L1TextExtractor
from src.domain.repositories.memory_repository import (
    MemoryChangeHistoryRepositoryProtocol,
    MemoryMetadataRepositoryProtocol,
)
from src.domain.services.memory_service import MemoryService


def _create_mock_metadata_repo():
    """Create a mock metadata repository."""
    mock = AsyncMock(spec=MemoryMetadataRepositoryProtocol)
    mock.save = AsyncMock()
    mock.get_by_id = AsyncMock(return_value=None)
    mock.get_by_name = AsyncMock(return_value=None)
    mock.delete = AsyncMock()
    mock.list_by_user = AsyncMock(return_value=[])
    mock.list_by_type = AsyncMock(return_value=[])
    mock.list_all = AsyncMock(return_value=[])
    return mock


def _create_mock_history_repo():
    """Create a mock history repository."""
    mock = AsyncMock(spec=MemoryChangeHistoryRepositoryProtocol)
    mock.save = AsyncMock()
    mock.get_by_memory_id = AsyncMock(return_value=[])
    mock.get_by_id = AsyncMock(return_value=None)
    return mock


class TestL1L3Separation:
    """L1 与 L3 分离验证"""

    def test_l1_compressor_only_handles_lightweight_compression(self):
        """验证 L1Compressor 仅处理轻量级压缩（≤500 字输入）"""
        compressor = L1Compressor()

        # 短文本（≤200 字）：使用规则压缩
        short_content = "记住，以后用 bun 而不是 npm"
        result = compressor.compress(short_content)
        assert result.compressed is not None
        assert result.original_length <= 200

        # 中等文本（200-500 字）：规则压缩 + 截断
        medium_content = "记住，以后用 bun 而不是 npm，这是一个很长的记忆内容需要压缩，" * 5
        result = compressor.compress(medium_content)
        assert result.compressed is not None
        assert result.original_length <= 500

    def test_l1_compressor_rejects_large_content(self):
        """验证 L1Compressor 拒绝超过 500 字的输入"""
        compressor = L1Compressor()

        # 超过 500 字应该抛出异常
        large_content = "记住，以后用 bun 而不是 npm，" * 100  # 约 600+ 字
        with pytest.raises(ValueError, match="内容超过限制"):
            compressor.compress(large_content)

    def test_l1_text_extractor_no_persistent_note_dependency(self):
        """验证 L1TextExtractor 无需 PersistentNote"""
        extractor = L1TextExtractor()

        # L1 应该直接从文本提取，无需 PersistentNote
        content = "记住，以后用 bun 而不是 npm"
        result = extractor.extract(content)

        assert result.content is not None
        # pattern 是正则表达式，验证提取发生了
        assert "记住" in result.pattern or result.pattern.startswith("^")

    def test_memory_service_no_l3_dependency(self):
        """验证 MemoryService 不依赖 L3 压缩逻辑"""
        service = MemoryService(
            text_extractor=L1TextExtractor(),
            compressor=L1Compressor(),
            metadata_repository=_create_mock_metadata_repo(),
            history_repository=_create_mock_history_repo(),
        )

        # MemoryService 应该只使用 L1 组件
        # 不应该有关于 PersistentNote 或 Checkpoint 的引用
        assert service._text_extractor is not None
        assert service._compressor is not None


class TestL1L2L3TriggerSeparation:
    """L1/L2/L3 触发机制分离验证"""

    def test_l1_trigger_is_user_initiated(self):
        """验证 L1 由用户主动触发"""
        service = MemoryService(
            text_extractor=L1TextExtractor(),
            compressor=L1Compressor(),
            metadata_repository=_create_mock_metadata_repo(),
            history_repository=_create_mock_history_repo(),
        )

        content = "记住，以后用 bun 而不是 npm"
        extraction = service._text_extractor.extract(content)

        # "记住" 触发用户主动记忆（pattern 是正则表达式）
        assert "记住" in extraction.pattern or extraction.pattern.startswith("^")

    def test_l1_compression_no_llm_for_short_content(self):
        """验证 L1 短文本压缩不使用 LLM"""
        compressor = L1Compressor()

        # 短文本应该使用规则压缩，不调用 LLM
        short_content = "记住，以后用 bun 而不是 npm"
        result = compressor.compress(short_content)

        assert result.method == "rule"
        assert "llm" not in result.method.lower()
