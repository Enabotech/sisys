"""Qdrant VectorStorage 单元测试（Mock 版本）。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.storage.qdrant.models import SparseVector, VectorPoint
from src.infrastructure.storage.qdrant.vector_storage import QdrantVectorStorage


@pytest.fixture
def mock_client_wrapper():
    """模拟 QdrantClientWrapper。"""
    wrapper = MagicMock()
    mock_client = AsyncMock()
    wrapper.get_async_client.return_value = mock_client
    return wrapper, mock_client


class TestQdrantVectorStorage:
    """QdrantVectorStorage 测试类。"""

    @pytest.mark.asyncio
    async def test_upsert_points_success(self, mock_client_wrapper):
        """测试成功插入向量点。"""
        wrapper, mock_client = mock_client_wrapper
        mock_client.upsert = AsyncMock()

        storage = QdrantVectorStorage(wrapper)
        points = [
            VectorPoint(
                id="point-1",
                vector=[0.1] * 1024,
                payload={"document_id": "doc-1", "business_domain": "finance"},
            )
        ]
        result = await storage.upsert_points("sisys:documents:finance", points)

        assert result is True
        mock_client.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_dense(self, mock_client_wrapper):
        """测试 Dense 语义检索。"""
        wrapper, mock_client = mock_client_wrapper
        mock_point = MagicMock()
        mock_point.id = "point-1"
        mock_point.score = 0.95
        mock_point.payload = {"document_id": "doc-1"}
        mock_response = MagicMock()
        mock_response.points = [mock_point]
        mock_client.query_points = AsyncMock(return_value=mock_response)

        storage = QdrantVectorStorage(wrapper)
        query_vector = [0.1] * 1024
        results = await storage.search("sisys:documents:finance", query_vector, limit=5)

        assert len(results) == 1
        assert results[0]["id"] == "point-1"
        assert results[0]["score"] == 0.95

    @pytest.mark.asyncio
    async def test_search_dense_with_filter(self, mock_client_wrapper):
        """测试带过滤条件的 Dense 检索。"""
        wrapper, mock_client = mock_client_wrapper
        mock_client.search = AsyncMock(return_value=[])

        storage = QdrantVectorStorage(wrapper)
        query_vector = [0.1] * 1024
        results = await storage.search(
            "sisys:documents:finance",
            query_vector,
            limit=10,
            filter_payload={"business_domain": "finance"},
        )

        assert results == []
        mock_client.query_points.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_points(self, mock_client_wrapper):
        """测试删除向量点。"""
        wrapper, mock_client = mock_client_wrapper
        mock_client.delete = AsyncMock()

        storage = QdrantVectorStorage(wrapper)
        result = await storage.delete_points("sisys:documents:finance", ["point-1", "point-2"])

        assert result is True
        mock_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_point_exists(self, mock_client_wrapper):
        """测试获取存在的向量点。"""
        wrapper, mock_client = mock_client_wrapper
        mock_point = MagicMock()
        mock_point.id = "point-1"
        mock_point.vector = [0.1] * 1024
        mock_point.payload = {"document_id": "doc-1"}
        mock_client.retrieve = AsyncMock(return_value=[mock_point])

        storage = QdrantVectorStorage(wrapper)
        result = await storage.get_point("sisys:documents:finance", "point-1")

        assert result is not None
        assert result["id"] == "point-1"

    @pytest.mark.asyncio
    async def test_get_point_not_exists(self, mock_client_wrapper):
        """测试获取不存在的向量点。"""
        wrapper, mock_client = mock_client_wrapper
        mock_client.retrieve = AsyncMock(return_value=[])

        storage = QdrantVectorStorage(wrapper)
        result = await storage.get_point("sisys:documents:finance", "point-999")

        assert result is None

    @pytest.mark.asyncio
    async def test_search_sparse(self, mock_client_wrapper):
        """测试 Sparse 检索。"""
        wrapper, mock_client = mock_client_wrapper
        mock_point = MagicMock()
        mock_point.id = "point-1"
        mock_point.score = 0.85
        mock_point.payload = {"document_id": "doc-1"}
        mock_response = MagicMock()
        mock_response.points = [mock_point]
        mock_client.query_points = AsyncMock(return_value=mock_response)

        storage = QdrantVectorStorage(wrapper)
        sparse_vector = SparseVector(indices=[1, 2, 3], values=[0.5, 0.3, 0.2])
        results = await storage.search_sparse("sisys:documents:finance", sparse_vector, limit=10)

        assert len(results) == 1
        assert results[0]["id"] == "point-1"

    @pytest.mark.asyncio
    async def test_search_sparse_exception(self, mock_client_wrapper):
        """测试 Sparse 检索异常返回空列表。"""
        wrapper, mock_client = mock_client_wrapper
        mock_client.search = AsyncMock(side_effect=Exception("Search error"))

        storage = QdrantVectorStorage(wrapper)
        sparse_vector = SparseVector(indices=[1, 2, 3], values=[0.5, 0.3, 0.2])
        results = await storage.search_sparse("sisys:documents:finance", sparse_vector, limit=10)

        assert results == []
