"""Story 3.5 索引管道 payload 扩展单元测试

验证 index_document 任务的 payload 包含 parent_chunk_id 和 index_level 字段。
此测试是分块级索引重构（Task 1 TDD 循环 [A-1]）的红阶段验证。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.ports.embedding_service import SparseEmbedding
from src.infrastructure.workflow.tasks.document_tasks import EmbeddingResult


def _make_mock_l3_vector() -> AsyncMock:
    """构造 mock L3VectorPort"""
    mock = AsyncMock()
    mock.upsert_points = AsyncMock(return_value=True)
    return mock


class TestIndexDocumentPayloadExtended:
    """index_document 分块级索引 payload 验证"""

    @pytest.mark.asyncio
    async def test_index_document_payload_has_index_level_document(self) -> None:
        """文档级点 payload 应包含 index_level 字段"""
        from src.infrastructure.workflow.tasks.document_tasks import index_document

        mock_vector = _make_mock_l3_vector()
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = mock_vector

        embedding_result: EmbeddingResult = {
            "dense_vectors": [[0.1] * 1024],
            "sparse_vectors": [SparseEmbedding(indices=[0, 5], values=[1.0, 0.5])],
        }

        with patch("src.domain.ports.resolver.get_resolver", return_value=mock_resolver):
            await index_document.fn(embedding_result)

        call_args = mock_vector.upsert_points.call_args
        points = call_args[0][1]
        assert len(points) == 1
        assert "payload" in points[0]
        assert points[0]["payload"]["index_level"] == "document", "文档级点 payload 应包含 index_level='document'"

    @pytest.mark.asyncio
    async def test_index_document_payload_has_parent_chunk_id(self) -> None:
        """文档级点 payload 应包含 parent_chunk_id 字段（None 表示无父块）"""
        from src.infrastructure.workflow.tasks.document_tasks import index_document

        mock_vector = _make_mock_l3_vector()
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = mock_vector

        embedding_result: EmbeddingResult = {
            "dense_vectors": [[0.1] * 1024],
            "sparse_vectors": [],
        }

        with patch("src.domain.ports.resolver.get_resolver", return_value=mock_resolver):
            await index_document.fn(embedding_result)

        call_args = mock_vector.upsert_points.call_args
        points = call_args[0][1]
        assert len(points) == 1
        assert "parent_chunk_id" in points[0]["payload"]

    @pytest.mark.asyncio
    async def test_index_document_payload_has_chunk_id(self) -> None:
        """文档级点 payload 应包含 chunk_id 字段"""
        from src.infrastructure.workflow.tasks.document_tasks import index_document

        mock_vector = _make_mock_l3_vector()
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = mock_vector

        embedding_result: EmbeddingResult = {
            "dense_vectors": [[0.1] * 1024],
            "sparse_vectors": [],
        }

        with patch("src.domain.ports.resolver.get_resolver", return_value=mock_resolver):
            await index_document.fn(embedding_result)

        call_args = mock_vector.upsert_points.call_args
        points = call_args[0][1]
        assert len(points) == 1
        assert "chunk_id" in points[0]["payload"]


class TestChunkIndexingHandler:
    """ChunkIndexingHandler 分块索引处理器（Task 1 [A-1] 集成方案）"""

    @pytest.mark.asyncio
    async def test_handler_exists_in_application_event_handlers(self) -> None:
        """ChunkIndexingHandler 应存在于应用层事件处理器"""
        import importlib

        try:
            mod = importlib.import_module("src.application.event_handlers.chunk_indexing_handler")
        except ImportError:
            pytest.fail("src.application.event_handlers.chunk_indexing_handler 模块不存在")
        assert hasattr(mod, "ChunkIndexingHandler"), "ChunkIndexingHandler 类不存在"

    @pytest.mark.asyncio
    async def test_handler_has_handle_method(self) -> None:
        """ChunkIndexingHandler 应包含 handle 方法"""
        import importlib

        try:
            mod = importlib.import_module("src.application.event_handlers.chunk_indexing_handler")
            cls = getattr(mod, "ChunkIndexingHandler")
        except ImportError:
            pytest.fail("src.application.event_handlers.chunk_indexing_handler 模块不存在")
        assert hasattr(cls, "handle_chunk_indexed"), "ChunkIndexingHandler 应包含 handle_chunk_indexed 方法"
