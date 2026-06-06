"""索引管线任务单元测试

验证 generate_embedding 双向量生成和 index_document 真实 Qdrant upsert。
使用 mock 隔离 embedding_service / document_repository / Qdrant client。
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.ports.embedding_service import SparseEmbedding
from src.infrastructure.workflow.tasks.document_tasks import EmbeddingResult


@pytest.fixture
def mock_embedding_service() -> MagicMock:
    """Mock EmbeddingService — Dense + Sparse 均返回模拟数据"""
    service = MagicMock()
    service.embed_documents = MagicMock(return_value=[[0.1] * 1024])
    service.embed_sparse = MagicMock(return_value=[SparseEmbedding(indices=[0, 5, 10], values=[1.0, 0.5, 0.8])])
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


class TestGenerateEmbeddingExtended:
    """generate_embedding 双向量生成"""

    @pytest.mark.asyncio
    async def test_generate_embedding_returns_embedding_result(self, mock_resolver: MagicMock) -> None:
        """generate_embedding.fn() 应返回 EmbeddingResult TypedDict"""
        from src.infrastructure.workflow.tasks.document_tasks import generate_embedding

        parse_result = {
            "status": "completed",
            "document_id": str(uuid.uuid4()),
            "tenant_id": "test-tenant",
        }

        with patch("src.domain.ports.resolver.get_resolver", return_value=mock_resolver):
            result = await generate_embedding.fn(parse_result)

        assert isinstance(result, dict)
        assert "dense_vectors" in result
        assert "sparse_vectors" in result
        assert isinstance(result["dense_vectors"], list)
        assert isinstance(result["sparse_vectors"], list)

    @pytest.mark.asyncio
    async def test_generate_embedding_calls_embed_documents(
        self, mock_resolver: MagicMock, mock_embedding_service: MagicMock
    ) -> None:
        """generate_embedding 应调用 embed_documents"""
        from src.infrastructure.workflow.tasks.document_tasks import generate_embedding

        parse_result = {
            "status": "completed",
            "document_id": str(uuid.uuid4()),
            "tenant_id": "test-tenant",
        }

        with patch("src.domain.ports.resolver.get_resolver", return_value=mock_resolver):
            await generate_embedding.fn(parse_result)

        mock_embedding_service.embed_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_embedding_calls_embed_sparse(
        self, mock_resolver: MagicMock, mock_embedding_service: MagicMock
    ) -> None:
        """generate_embedding 应调用 embed_sparse"""
        from src.infrastructure.workflow.tasks.document_tasks import generate_embedding

        parse_result = {
            "status": "completed",
            "document_id": str(uuid.uuid4()),
            "tenant_id": "test-tenant",
        }

        with patch("src.domain.ports.resolver.get_resolver", return_value=mock_resolver):
            await generate_embedding.fn(parse_result)

        mock_embedding_service.embed_sparse.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_embedding_sparse_failure_degrades(
        self, mock_resolver: MagicMock, mock_embedding_service: MagicMock
    ) -> None:
        """embed_sparse 失败时降级 — sparse_vectors 为空列表，dense 正常"""
        from src.infrastructure.workflow.tasks.document_tasks import generate_embedding

        mock_embedding_service.embed_sparse.side_effect = RuntimeError("Sparse API 不可用")

        parse_result = {
            "status": "completed",
            "document_id": str(uuid.uuid4()),
            "tenant_id": "test-tenant",
        }

        with patch("src.domain.ports.resolver.get_resolver", return_value=mock_resolver):
            result = await generate_embedding.fn(parse_result)

        assert result["sparse_vectors"] == []
        assert len(result["dense_vectors"]) > 0

    @pytest.mark.asyncio
    async def test_generate_embedding_failed_parse_returns_empty(self, mock_resolver: MagicMock) -> None:
        """解析失败时返回空 EmbeddingResult"""
        from src.infrastructure.workflow.tasks.document_tasks import generate_embedding

        parse_result = {"status": "failed", "document_id": str(uuid.uuid4())}

        with patch("src.domain.ports.resolver.get_resolver", return_value=mock_resolver):
            result = await generate_embedding.fn(parse_result)

        assert result["dense_vectors"] == []
        assert result["sparse_vectors"] == []


class TestIndexDocumentReal:
    """index_document 真实 Qdrant upsert"""

    def _make_mock_l3_vector(self) -> AsyncMock:
        """构造 mock L3VectorPort"""
        mock = AsyncMock()
        mock.upsert_points = AsyncMock(return_value=True)
        return mock

    @pytest.mark.asyncio
    async def test_index_document_accepts_embedding_result(self) -> None:
        """index_document 应接受 EmbeddingResult 参数（非原 list[float]）"""
        from src.infrastructure.workflow.tasks.document_tasks import index_document

        embedding_result: EmbeddingResult = {
            "dense_vectors": [[0.1] * 1024],
            "sparse_vectors": [SparseEmbedding(indices=[0, 5], values=[1.0, 0.5])],
        }

        with patch("src.domain.ports.resolver.get_resolver", return_value=MagicMock()):
            result = await index_document.fn(embedding_result)

        assert isinstance(result, dict)
        assert "indexed" in result

    @pytest.mark.asyncio
    async def test_index_document_calls_upsert_points(self) -> None:
        """index_document 应调用 l3_vector.upsert_points"""
        from src.infrastructure.workflow.tasks.document_tasks import index_document

        mock_vector = self._make_mock_l3_vector()
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = mock_vector

        embedding_result: EmbeddingResult = {
            "dense_vectors": [[0.1] * 1024],
            "sparse_vectors": [SparseEmbedding(indices=[0, 5], values=[1.0, 0.5])],
        }

        with patch("src.domain.ports.resolver.get_resolver", return_value=mock_resolver):
            await index_document.fn(embedding_result)

        mock_vector.upsert_points.assert_called()

    @pytest.mark.asyncio
    async def test_index_document_passes_sparse_vector_to_upsert(self) -> None:
        """index_document 应在 upsert 的点中包含 sparse_vector 字段"""
        from src.infrastructure.workflow.tasks.document_tasks import index_document

        mock_vector = self._make_mock_l3_vector()
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = mock_vector

        embedding_result: EmbeddingResult = {
            "dense_vectors": [[0.1] * 1024],
            "sparse_vectors": [SparseEmbedding(indices=[0, 5], values=[1.0, 0.5])],
        }

        with patch("src.domain.ports.resolver.get_resolver", return_value=mock_resolver):
            await index_document.fn(embedding_result)

        # 验证传给 upsert_points 的点包含 sparse_vector
        call_args = mock_vector.upsert_points.call_args
        points = call_args[0][1]  # 第二个位置参数
        assert len(points) == 1
        assert "sparse_vector" in points[0], f"point 缺少 sparse_vector: {points[0].keys()}"
        assert points[0]["sparse_vector"]["indices"] == [0, 5]
        assert points[0]["sparse_vector"]["values"] == [1.0, 0.5]

    @pytest.mark.asyncio
    async def test_index_document_empty_vectors_returns_false(self) -> None:
        """空向量列表时返回 indexed=False"""
        from src.infrastructure.workflow.tasks.document_tasks import index_document

        embedding_result: EmbeddingResult = {
            "dense_vectors": [],
            "sparse_vectors": [],
        }

        result = await index_document.fn(embedding_result)

        assert result["indexed"] is False
        assert result["chunk_count"] == 0
