"""Tests for QdrantVectorAdapter — L3VectorPort implementation.

验证适配器正确委托存储操作，实现 L3VectorPort 接口。
架构意义：薄适配器层，仅做接口转换，不改变语义。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.ports.l3_vector import L3VectorPort
from src.infrastructure.storage.qdrant.qdrant_vector_adapter import QdrantVectorAdapter


class TestQdrantVectorAdapterInterface:
    """验证适配器实现 L3VectorPort 接口"""

    def test_implements_l3_vector_port(self):
        """验证 QdrantVectorAdapter 实现 L3VectorPort"""
        mock_storage = MagicMock()
        adapter = QdrantVectorAdapter(mock_storage)
        assert isinstance(adapter, L3VectorPort)

    def test_delegates_to_internal_storage(self):
        """验证适配器委托操作给内部存储"""
        mock_storage = MagicMock()
        adapter = QdrantVectorAdapter(mock_storage)
        assert adapter._storage is mock_storage


class TestQdrantVectorAdapterUpsertPoints:
    """upsert_points 方法验证"""

    @pytest.mark.asyncio
    async def test_upsert_points_converts_dict_to_vector_point(self):
        """验证 dict 转换为 VectorPoint"""
        mock_storage = MagicMock()
        mock_storage.upsert_points = AsyncMock(return_value=True)

        adapter = QdrantVectorAdapter(mock_storage)
        # VectorPoint requires 1024 dimensions (bge-m3 embedding model)
        points = [
            {"id": "mem-1", "vector": [0.1] * 1024, "payload": {"name": "test"}},
            {"id": "mem-2", "vector": [0.3] * 1024, "payload": {"name": "test2"}},
        ]

        result = await adapter.upsert_points("test-collection", points)

        assert result is True
        mock_storage.upsert_points.assert_called_once()
        call_args = mock_storage.upsert_points.call_args
        vector_points = call_args[0][1]
        assert len(vector_points) == 2
        assert vector_points[0].id == "mem-1"
        assert len(vector_points[0].vector) == 1024

    @pytest.mark.asyncio
    async def test_upsert_points_handles_empty_payload(self):
        """验证空 payload 使用默认空字典"""
        mock_storage = MagicMock()
        mock_storage.upsert_points = AsyncMock(return_value=True)

        adapter = QdrantVectorAdapter(mock_storage)
        points = [{"id": "mem-1", "vector": [0.1] * 1024}]

        await adapter.upsert_points("test-collection", points)

        call_args = mock_storage.upsert_points.call_args
        vector_points = call_args[0][1]
        assert vector_points[0].payload == {}


class TestQdrantVectorAdapterDeletePoints:
    """delete_points 方法验证"""

    @pytest.mark.asyncio
    async def test_delete_points_delegates_correctly(self):
        """验证 delete_points 正确委托"""
        mock_storage = AsyncMock()
        mock_storage.delete_points = AsyncMock(return_value=True)

        adapter = QdrantVectorAdapter(mock_storage)
        result = await adapter.delete_points("test-collection", ["id-1", "id-2"])

        assert result is True
        mock_storage.delete_points.assert_called_once_with("test-collection", ["id-1", "id-2"])


class TestQdrantVectorAdapterGetPoint:
    """get_point 方法验证"""

    @pytest.mark.asyncio
    async def test_get_point_returns_none_when_not_found(self):
        """验证不存在时返回 None"""
        mock_storage = AsyncMock()
        mock_storage.get_point = AsyncMock(return_value=None)

        adapter = QdrantVectorAdapter(mock_storage)
        result = await adapter.get_point("test-collection", "nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_point_returns_dict(self):
        """验证返回 dict 类型"""
        mock_storage = AsyncMock()
        expected = {"id": "mem-1", "vector": [0.1], "payload": {}}
        mock_storage.get_point = AsyncMock(return_value=expected)

        adapter = QdrantVectorAdapter(mock_storage)
        result = await adapter.get_point("test-collection", "mem-1")

        assert result == expected


class TestQdrantVectorAdapterSearch:
    """search 方法验证"""

    @pytest.mark.asyncio
    async def test_search_delegates_with_filter(self):
        """验证 search 正确委托"""
        mock_storage = AsyncMock()
        mock_storage.search = AsyncMock(return_value=[])

        adapter = QdrantVectorAdapter(mock_storage)
        await adapter.search("test-collection", [0.1, 0.2], limit=5, filter_payload={"type": "user"})

        mock_storage.search.assert_called_once_with("test-collection", [0.1, 0.2], limit=5, filter_payload={"type": "user"})

    @pytest.mark.asyncio
    async def test_search_returns_list_of_dict(self):
        """验证 search 返回 list[dict]"""
        mock_storage = AsyncMock()
        expected = [
            {"id": "mem-1", "score": 0.95, "payload": {}},
            {"id": "mem-2", "score": 0.85, "payload": {}},
        ]
        mock_storage.search = AsyncMock(return_value=expected)

        adapter = QdrantVectorAdapter(mock_storage)
        result = await adapter.search("test-collection", [0.1, 0.2])

        assert len(result) == 2
        assert result[0]["id"] == "mem-1"


class TestQdrantVectorAdapterSearchSparse:
    """search_sparse 方法验证"""

    @pytest.mark.asyncio
    async def test_search_sparse_converts_sparse_vector(self):
        """验证稀疏向量转换"""
        mock_storage = AsyncMock()
        mock_storage.search_sparse = AsyncMock(return_value=[])

        adapter = QdrantVectorAdapter(mock_storage)
        sparse_vector = {"indices": [0, 5, 10], "values": [1.0, 0.5, 0.8]}
        await adapter.search_sparse("test-collection", sparse_vector, limit=10)

        mock_storage.search_sparse.assert_called_once()
        call_args = mock_storage.search_sparse.call_args
        assert call_args[0][0] == "test-collection"
        # 第二参数是 SparseVector 对象
        sv = call_args[0][1]
        assert sv.indices == [0, 5, 10]
        assert sv.values == [1.0, 0.5, 0.8]

    @pytest.mark.asyncio
    async def test_search_sparse_returns_list(self):
        """验证返回 list[dict]"""
        mock_storage = AsyncMock()
        expected = [{"id": "mem-1", "score": 0.9, "payload": {}}]
        mock_storage.search_sparse = AsyncMock(return_value=expected)

        adapter = QdrantVectorAdapter(mock_storage)
        result = await adapter.search_sparse("test-collection", {"indices": [], "values": []})

        assert result == expected
