"""语义分块事件处理器测试

测试 SemanticChunkingHandler 监听 DocumentProcessed 事件并触发分块。
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock

import pytest

from src.domain.events.document_events import DocumentProcessed
from src.domain.value_objects.semantic_chunk import ChunkBoundaryType, SemanticChunk


class TestSemanticChunkingHandler:
    """测试 SemanticChunkingHandler"""

    @pytest.fixture
    def mock_service(self) -> AsyncMock:
        """Mock 语义分块服务"""
        return AsyncMock()

    @pytest.fixture
    def handler(self, mock_service):
        """创建处理器实例"""
        from src.application.event_handlers.semantic_chunking_handler import SemanticChunkingHandler

        return SemanticChunkingHandler(semantic_chunking_service=mock_service)

    def test_handle_document_processed_success(self, handler, mock_service):
        """成功处理 DocumentProcessed 事件"""
        doc_id = uuid.uuid4()
        event = DocumentProcessed(
            document_id=doc_id,
            tenant_id="tenant-1",
        )

        chunks = [
            SemanticChunk(
                chunk_id=uuid.uuid4(),
                document_id=doc_id,
                content="测试",
                chunk_index=0,
                boundary_type=ChunkBoundaryType.PARAGRAPH,
                token_count=10,
                page_start=1,
                page_end=1,
                content_hash="abc",
                metadata={},
            )
        ]
        mock_service.chunk_document.return_value = chunks

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(handler.handle_document_processed(event))
        finally:
            loop.close()

        # 验证调用了 chunk_document
        mock_service.chunk_document.assert_called_once_with(
            document_id=doc_id,
            tenant_id="tenant-1",
        )

    def test_handle_document_processed_service_error(self, handler, mock_service):
        """服务异常时不影响主流程"""
        doc_id = uuid.uuid4()
        event = DocumentProcessed(
            document_id=doc_id,
            tenant_id="tenant-1",
        )

        # 模拟服务异常
        mock_service.chunk_document.side_effect = ValueError("测试错误")

        loop = asyncio.new_event_loop()
        try:
            # 不应抛出异常
            loop.run_until_complete(handler.handle_document_processed(event))
        finally:
            loop.close()

        # 验证调用了 chunk_document
        mock_service.chunk_document.assert_called_once()

    def test_handle_document_processed_empty(self, handler, mock_service):
        """空文档事件处理"""
        doc_id = uuid.uuid4()
        event = DocumentProcessed(
            document_id=doc_id,
            tenant_id="tenant-1",
        )

        mock_service.chunk_document.return_value = []

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(handler.handle_document_processed(event))
        finally:
            loop.close()

        # 验证调用了 chunk_document（空文档也触发）
        mock_service.chunk_document.assert_called_once()
        args, kwargs = mock_service.chunk_document.call_args
        assert kwargs["document_id"] == doc_id
