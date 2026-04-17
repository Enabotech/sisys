"""Qdrant 端到端集成测试（Mock 版本）。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.storage.qdrant.bm25_builder import BM25Builder
from src.infrastructure.storage.qdrant.client import QdrantClientWrapper
from src.infrastructure.storage.qdrant.collection_manager import QdrantCollectionManager
from src.infrastructure.storage.qdrant.models import VectorPoint
from src.infrastructure.storage.qdrant.vector_storage import QdrantVectorStorage


@pytest.fixture
def mock_qdrant_setup():
    """模拟 Qdrant 环境设置。"""
    wrapper = MagicMock(spec=QdrantClientWrapper)
    mock_client = AsyncMock()
    wrapper.get_async_client.return_value = mock_client

    collection_manager = QdrantCollectionManager(wrapper)
    vector_storage = QdrantVectorStorage(wrapper)
    bm25_builder = BM25Builder()

    return {
        "wrapper": wrapper,
        "mock_client": mock_client,
        "collection_manager": collection_manager,
        "vector_storage": vector_storage,
        "bm25_builder": bm25_builder,
    }


class TestQdrantIntegration:
    """Qdrant 集成测试类。"""

    @pytest.mark.asyncio
    async def test_collection_lifecycle(self, mock_qdrant_setup):
        """测试 Collection 生命周期（创建→验证→删除）。"""
        setup = mock_qdrant_setup
        mock_client = setup["mock_client"]
        manager = setup["collection_manager"]

        # 使用 side_effect 模拟动态 Collection 列表
        collections_list = []

        def make_collection(name):
            c = MagicMock()
            c.name = name
            return c

        async def mock_get_collections():
            return MagicMock(collections=[make_collection(n) for n in collections_list])

        mock_client.get_collections = AsyncMock(side_effect=mock_get_collections)
        mock_client.create_collection = AsyncMock()
        mock_client.delete_collection = AsyncMock()

        # 初始无 Collection
        exists_before = await manager.collection_exists("sisys:documents:finance")
        assert exists_before is False

        # 创建 Collection（创建前检查时不存在，创建后添加到列表）
        async def mock_create_and_add(**kwargs):
            collections_list.append(kwargs.get("collection_name", ""))

        mock_client.create_collection = AsyncMock(side_effect=mock_create_and_add)
        result = await manager.create_collection("sisys:documents:finance")
        assert result is True

        # 验证存在
        exists_after = await manager.collection_exists("sisys:documents:finance")
        assert exists_after is True

        # 删除 Collection
        result = await manager.delete_collection("sisys:documents:finance")
        assert result is True
        assert mock_client.delete_collection.called

    @pytest.mark.asyncio
    async def test_vector_point_storage(self, mock_qdrant_setup):
        """测试向量点存储端到端流程。"""
        setup = mock_qdrant_setup
        mock_client = setup["mock_client"]
        storage = setup["vector_storage"]

        mock_client.upsert = AsyncMock()
        mock_client.retrieve = AsyncMock(return_value=[])

        # 插入向量点
        points = [
            VectorPoint(
                id="point-1",
                vector=[0.1] * 1024,
                payload={"document_id": "doc-1", "chunk_id": "chunk-1"},
            )
        ]
        result = await storage.upsert_points("sisys:documents:finance", points)
        assert result is True

        # 查询向量点
        await storage.get_point("sisys:documents:finance", "point-1")
        mock_client.retrieve.assert_called()

    @pytest.mark.asyncio
    async def test_dense_search_flow(self, mock_qdrant_setup):
        """测试 Dense 语义检索端到端流程。"""
        setup = mock_qdrant_setup
        mock_client = setup["mock_client"]
        storage = setup["vector_storage"]

        mock_point = MagicMock()
        mock_point.id = "point-1"
        mock_point.score = 0.95
        mock_point.payload = {"document_id": "doc-1"}
        # search 返回 list，不再是 response.points
        mock_client.search = AsyncMock(return_value=[mock_point])

        query_vector = [0.1] * 1024
        results = await storage.search("sisys:documents:finance", query_vector, limit=5)

        assert len(results) == 1
        assert results[0]["score"] == 0.95

    @pytest.mark.asyncio
    async def test_bm25_sparse_search_flow(self, mock_qdrant_setup):
        """测试 BM25 稀疏检索端到端流程。"""
        setup = mock_qdrant_setup
        mock_client = setup["mock_client"]
        storage = setup["vector_storage"]
        builder = setup["bm25_builder"]

        mock_point = MagicMock()
        mock_point.id = "point-1"
        mock_point.score = 0.85
        mock_point.payload = {"document_id": "doc-1"}
        # search 返回 list，不再是 response.points
        mock_client.search = AsyncMock(return_value=[mock_point])

        # 从文本构建稀疏向量
        sparse_vector = builder.build_sparse_vector("financial report analysis")
        assert len(sparse_vector.indices) > 0

        # 执行稀疏检索
        results = await storage.search_sparse("sisys:documents:finance", sparse_vector)
        assert len(results) == 1
        assert results[0]["id"] == "point-1"

    @pytest.mark.asyncio
    async def test_multi_tenant_isolation(self, mock_qdrant_setup):
        """测试多租户隔离。"""
        setup = mock_qdrant_setup
        mock_client = setup["mock_client"]
        manager = setup["collection_manager"]

        # 创建两个 Collection
        mock_client.get_collections = AsyncMock(return_value=MagicMock(collections=[]))
        await manager.create_collection("sisys:documents:finance")
        await manager.create_collection("sisys:documents:hr")

        assert mock_client.create_collection.call_count == 2

        # 验证 Collection 名称
        call_names = [call.kwargs["collection_name"] for call in mock_client.create_collection.call_args_list]
        assert "sisys:documents:finance" in call_names
        assert "sisys:documents:hr" in call_names
