"""索引管线任务单元测试

验证事件驱动分块索引（ChunkIndexingHandler）。
⚠️ 全文索引轨（generate_embedding/index_document）已废弃删除，
索引统一由 ChunkIndexingHandler 消费 RAGIndexed 事件执行。
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.ports.embedding_service import SparseEmbedding


@pytest.fixture
def mock_embedding_service() -> MagicMock:
    """Mock EmbeddingService — Dense + Sparse 均返回模拟数据"""
    service = MagicMock()
    service.embed_documents = AsyncMock(return_value=[[0.1] * 1024])
    service.embed_sparse = AsyncMock(return_value=[SparseEmbedding(indices=[0, 5, 10], values=[1.0, 0.5, 0.8])])
    return service


@pytest.fixture
def mock_document_repository() -> AsyncMock:
    """Mock DocumentRepository"""
    from src.domain.entities.document import Document, ParseStatus

    doc = Document(
        document_id=uuid.uuid4(),
        filename="test.pdf",
        mime_type="application/pdf",
        tenant_id="test-tenant",
    )
    doc.parse_status = ParseStatus.COMPLETED
    doc.metadata["parse_result"] = {"pages": [{"texts": [{"content": "测试文本"}]}]}

    repo = AsyncMock()
    repo.find = AsyncMock(return_value=doc)
    return repo


@pytest.fixture
def mock_resolver(mock_embedding_service: MagicMock, mock_document_repository: AsyncMock) -> MagicMock:
    """Mock DI Resolver"""
    resolver = MagicMock()
    resolver.resolve.side_effect = lambda name: {
        "embedding_service": mock_embedding_service,
        "document_repository": mock_document_repository,
    }.get(name)
    return resolver


class TestChunkIndexingHandler:
    """ChunkIndexingHandler 分块索引事件处理器（索引唯一入口）"""

    @pytest.mark.asyncio
    async def test_index_document_accepts_embedding_result(self) -> None:
        """ChunkIndexingHandler 接受 RAGIndexed 事件（替代 index_document 的 EmbeddingResult 参数）"""
        from src.application.event_handlers.chunk_indexing_handler import ChunkIndexingHandler

        assert hasattr(ChunkIndexingHandler, "handle_chunk_indexed"), "ChunkIndexingHandler 应包含 handle_chunk_indexed 方法"

    @pytest.mark.asyncio
    async def test_index_document_calls_upsert_points(self) -> None:
        """ChunkIndexingHandler.handle_chunk_indexed 调用 l3_vector.upsert_points"""
        from unittest.mock import AsyncMock, MagicMock

        from src.application.event_handlers.chunk_indexing_handler import ChunkIndexingHandler
        from src.domain.events.workflow_events import RAGIndexed

        mock_l3 = AsyncMock()
        mock_l3.upsert_points = AsyncMock(return_value=True)
        mock_embedding = AsyncMock()
        mock_embedding.embed_documents.return_value = [[0.1] * 1024]
        mock_repo = AsyncMock()
        mock_repo.find.return_value = MagicMock(
            metadata={"chunks": [{"chunk_id": "c1", "content": "块1", "index_level": "parent", "parent_chunk_id": None}]}
        )

        handler = ChunkIndexingHandler(
            embedding_service=mock_embedding,
            l3_vector=mock_l3,
            document_repository=mock_repo,
        )
        event = RAGIndexed(document_id=MagicMock(), chunk_count=1, tenant_id="test")
        await handler.handle_chunk_indexed(event)

        mock_l3.upsert_points.assert_called()

    @pytest.mark.asyncio
    async def test_index_document_passes_sparse_vector_to_upsert(self) -> None:
        """ChunkIndexingHandler 的 upsert 点包含 sparse_vector 字段"""
        from unittest.mock import AsyncMock, MagicMock

        from src.application.event_handlers.chunk_indexing_handler import ChunkIndexingHandler
        from src.domain.events.workflow_events import RAGIndexed

        mock_l3 = AsyncMock()
        mock_l3.upsert_points = AsyncMock(return_value=True)

        async def _embed_sparse(texts: list[str]) -> list[dict]:
            return [{"indices": [0, 5], "values": [1.0, 0.5]} for _ in texts]

        mock_embedding = AsyncMock()
        mock_embedding.embed_documents.return_value = [[0.1] * 1024]
        mock_embedding.embed_sparse = _embed_sparse
        mock_repo = AsyncMock()
        mock_repo.find.return_value = MagicMock(
            metadata={"chunks": [{"chunk_id": "c1", "content": "块1", "index_level": "parent", "parent_chunk_id": None}]}
        )

        handler = ChunkIndexingHandler(
            embedding_service=mock_embedding,
            l3_vector=mock_l3,
            document_repository=mock_repo,
        )
        event = RAGIndexed(document_id=MagicMock(), chunk_count=1, tenant_id="test")
        await handler.handle_chunk_indexed(event)

        call_args = mock_l3.upsert_points.call_args
        points = call_args[0][1]
        assert len(points) == 1
        assert "sparse_vector" in points[0], f"point 缺少 sparse_vector: {points[0].keys()}"

    @pytest.mark.asyncio
    async def test_index_document_empty_vectors_returns_false(self) -> None:
        """空 chunk_count 时 ChunkIndexingHandler 跳过索引"""
        from unittest.mock import AsyncMock, MagicMock

        from src.application.event_handlers.chunk_indexing_handler import ChunkIndexingHandler
        from src.domain.events.workflow_events import RAGIndexed

        mock_l3 = AsyncMock()
        handler = ChunkIndexingHandler(
            embedding_service=MagicMock(),
            l3_vector=mock_l3,
            document_repository=MagicMock(),
        )
        event = RAGIndexed(document_id=MagicMock(), chunk_count=0, tenant_id="test")
        await handler.handle_chunk_indexed(event)

        mock_l3.upsert_points.assert_not_called()
