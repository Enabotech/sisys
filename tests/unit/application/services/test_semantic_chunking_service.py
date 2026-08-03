"""语义分块应用服务测试

Mock SemanticChunkerPort 测试完整编排流程。
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.value_objects.semantic_chunk import ChunkBoundaryType, SemanticChunk


class TestSemanticChunkingService:
    """测试 SemanticChunkingService"""

    @pytest.fixture
    def mock_document_repository(self) -> AsyncMock:
        """Mock 文档仓储"""
        return AsyncMock()

    @pytest.fixture
    def mock_semantic_chunker(self) -> AsyncMock:
        """Mock 语义分块器"""
        mock = AsyncMock()
        mock.chunk = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def mock_event_publisher(self) -> AsyncMock:
        """Mock 事件发布器"""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_document_repository, mock_semantic_chunker, mock_event_publisher):
        """创建服务实例"""
        from src.application.services.semantic_chunking_service import SemanticChunkingService

        return SemanticChunkingService(
            document_repository=mock_document_repository,
            semantic_chunker=mock_semantic_chunker,
            event_publisher=mock_event_publisher,
        )

    def test_chunk_document_success(self, service, mock_document_repository, mock_semantic_chunker, mock_event_publisher):
        """成功分块流程"""
        doc_id = uuid.uuid4()
        tenant_id = "tenant-1"

        # Mock 文档实体
        mock_doc = MagicMock()
        mock_doc.metadata = {
            "parse_result": {
                "document_id": str(doc_id),
                "mime_type": "text/plain",
                "pages": [],
                "parse_status": "completed",
            }
        }
        mock_document_repository.find.return_value = mock_doc

        # Mock 分块结果
        chunks = [
            SemanticChunk(
                chunk_id=uuid.uuid4(),
                document_id=doc_id,
                content="测试内容",
                chunk_index=0,
                boundary_type=ChunkBoundaryType.PARAGRAPH,
                token_count=10,
                page_start=1,
                page_end=1,
                content_hash="abc123",
                metadata={"business_domain": "test"},
            )
        ]
        mock_semantic_chunker.chunk.return_value = chunks

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(service.chunk_document(document_id=doc_id, tenant_id=tenant_id))
        finally:
            loop.close()

        # 验证结果
        assert len(result) == 1
        assert result[0].document_id == doc_id

        # 验证仓储调用
        mock_document_repository.find.assert_called_once()

        # 验证分块器调用
        mock_semantic_chunker.chunk.assert_called_once()

        # 验证事件发布
        mock_event_publisher.publish.assert_called_once()

    def test_chunk_document_empty(self, service, mock_document_repository, mock_semantic_chunker, mock_event_publisher):
        """空文档分块"""
        doc_id = uuid.uuid4()
        tenant_id = "tenant-1"

        mock_doc = MagicMock()
        mock_doc.metadata = {
            "parse_result": {
                "document_id": str(doc_id),
                "mime_type": "text/plain",
                "pages": [],
                "parse_status": "completed",
            }
        }
        mock_document_repository.find.return_value = mock_doc
        mock_semantic_chunker.chunk.return_value = []

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(service.chunk_document(document_id=doc_id, tenant_id=tenant_id))
        finally:
            loop.close()

        assert result == []
        # 空文档也应该发布 RAGIndexed 事件（chunk_count=0）
        mock_event_publisher.publish.assert_called_once()

    def test_parsed_document_from_dict(self, service):
        """测试 from_dict 反序列化"""
        doc_id = str(uuid.uuid4())
        data = {
            "document_id": doc_id,
            "mime_type": "text/plain",
            "pages": [
                {
                    "page_number": 1,
                    "texts": [
                        {
                            "content": "测试",
                            "bbox": None,
                            "confidence": 1.0,
                            "metadata": {},
                        }
                    ],
                    "tables": [],
                    "images": [],
                }
            ],
            "parse_status": "completed",
            "error_message": None,
            "parse_timestamp": "",
        }

        result = service.parsed_document_from_dict(data)
        assert result.document_id == doc_id
        assert len(result.pages) == 1
        assert result.pages[0].page_number == 1
        assert len(result.pages[0].texts) == 1
        assert result.pages[0].texts[0].content == "测试"


class TestParsedDocumentFromDict:
    """测试 parsed_document_from_dict 静态方法"""

    def test_empty_pages(self):
        """空页面列表"""
        from src.application.services.semantic_chunking_service import SemanticChunkingService

        data = {
            "document_id": "doc-1",
            "mime_type": "text/plain",
            "pages": [],
            "parse_status": "completed",
        }
        result = SemanticChunkingService.parsed_document_from_dict(data)
        assert result.pages == []

    def test_with_bbox(self):
        """含 bbox 的页面"""
        from src.application.services.semantic_chunking_service import SemanticChunkingService

        data = {
            "document_id": "doc-1",
            "mime_type": "text/plain",
            "pages": [
                {
                    "page_number": 1,
                    "texts": [
                        {
                            "content": "测试",
                            "bbox": {"x": 0.0, "y": 0.0, "width": 100.0, "height": 50.0, "page": 1},
                            "confidence": 0.95,
                            "metadata": {"style": "h1"},
                        }
                    ],
                    "tables": [],
                    "images": [],
                }
            ],
            "parse_status": "completed",
        }
        result = SemanticChunkingService.parsed_document_from_dict(data)
        assert result.pages[0].texts[0].bbox is not None
        assert result.pages[0].texts[0].bbox.x == 0.0
        assert result.pages[0].texts[0].metadata["style"] == "h1"

    def test_with_tables(self):
        """含表格的页面"""
        from src.application.services.semantic_chunking_service import SemanticChunkingService

        data = {
            "document_id": "doc-1",
            "mime_type": "text/plain",
            "pages": [
                {
                    "page_number": 1,
                    "texts": [],
                    "tables": [
                        {
                            "rows": [["A", "B"], ["1", "2"]],
                            "bbox": None,
                            "confidence": 1.0,
                            "metadata": {},
                            "header": ["A", "B"],
                            "column_types": None,
                            "merged_cells": None,
                            "semantic_confidence": None,
                            "table_caption": None,
                        }
                    ],
                    "images": [],
                }
            ],
            "parse_status": "completed",
        }
        result = SemanticChunkingService.parsed_document_from_dict(data)
        assert len(result.pages[0].tables) == 1
        assert result.pages[0].tables[0].header == ["A", "B"]
