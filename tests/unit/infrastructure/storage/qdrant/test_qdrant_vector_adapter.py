"""QdrantVectorAdapter 实现测试。

验证 QdrantVectorAdapter 实现了 L3VectorPort 接口。
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestQdrantVectorAdapterL3VectorPortCompliance:
    """验证 QdrantVectorAdapter 实现了 L3VectorPort 接口。"""

    def test_adapter_implements_l3_vector_port(self) -> None:
        """QdrantVectorAdapter 应实现 L3VectorPort。"""
        from src.domain.ports.l3_vector import L3VectorPort
        from src.infrastructure.storage.qdrant.qdrant_vector_adapter import QdrantVectorAdapter

        mock_storage = MagicMock()
        adapter = QdrantVectorAdapter(mock_storage)

        assert isinstance(adapter, L3VectorPort)

    def test_adapter_has_all_required_methods(self) -> None:
        """QdrantVectorAdapter 应有 L3VectorPort 的所有方法。"""
        from src.domain.ports.l3_vector import L3VectorPort
        from src.infrastructure.storage.qdrant.qdrant_vector_adapter import QdrantVectorAdapter

        mock_storage = MagicMock()
        adapter = QdrantVectorAdapter(mock_storage)

        for method_name in ["upsert_points", "delete_points", "get_point", "search", "search_sparse"]:
            assert hasattr(adapter, method_name)
            assert hasattr(L3VectorPort, method_name)

    def test_all_methods_are_async(self) -> None:
        """所有方法应为 async def。"""
        from src.infrastructure.storage.qdrant.qdrant_vector_adapter import QdrantVectorAdapter

        mock_storage = MagicMock()
        adapter = QdrantVectorAdapter(mock_storage)

        for method_name in ["upsert_points", "delete_points", "get_point", "search", "search_sparse"]:
            method = getattr(adapter, method_name)
            assert asyncio.iscoroutinefunction(method), f"{method_name} should be async"


class TestQdrantVectorAdapterBehavior:
    """QdrantVectorAdapter 行为测试。"""

    @pytest.fixture
    def mock_qdrant_storage(self):
        """创建模拟的 QdrantVectorStorage。"""
        mock = MagicMock()
        mock.upsert_points = AsyncMock(return_value=True)
        mock.delete_points = AsyncMock(return_value=True)
        mock.get_point = AsyncMock(return_value={"id": "mem-123", "vector": [0.1] * 1024, "payload": {}})
        mock.search = AsyncMock(return_value=[{"id": "mem-1", "score": 0.9, "payload": {}}])
        mock.search_sparse = AsyncMock(return_value=[{"id": "mem-1", "score": 0.8, "payload": {}}])
        return mock

    @pytest.fixture
    def adapter(self, mock_qdrant_storage):
        """创建 QdrantVectorAdapter 实例。"""
        from src.infrastructure.storage.qdrant.qdrant_vector_adapter import QdrantVectorAdapter

        return QdrantVectorAdapter(mock_qdrant_storage)

    @pytest.mark.asyncio
    async def test_upsert_points_delegates_to_storage(self, adapter, mock_qdrant_storage) -> None:
        """upsert_points 应委托给内部存储。"""
        points = [{"id": "mem-123", "vector": [0.1] * 1024, "payload": {"key": "value"}}]

        result = await adapter.upsert_points("test-collection", points)

        assert result is True
        mock_qdrant_storage.upsert_points.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_points_delegates_to_storage(self, adapter, mock_qdrant_storage) -> None:
        """delete_points 应委托给内部存储。"""
        result = await adapter.delete_points("test-collection", ["id1", "id2"])

        assert result is True
        mock_qdrant_storage.delete_points.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_point_delegates_to_storage(self, adapter, mock_qdrant_storage) -> None:
        """get_point 应委托给内部存储。"""
        expected = {"id": "mem-123", "vector": [0.1] * 1024, "payload": {}}
        result = await adapter.get_point("test-collection", "mem-123")

        assert result == expected
        mock_qdrant_storage.get_point.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_delegates_to_storage(self, adapter, mock_qdrant_storage) -> None:
        """search 应委托给内部存储。"""
        expected = [{"id": "mem-1", "score": 0.9, "payload": {}}]
        result = await adapter.search("test-collection", [0.1] * 1024, limit=10)

        assert result == expected
        mock_qdrant_storage.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_sparse_delegates_to_storage(self, adapter, mock_qdrant_storage) -> None:
        """search_sparse 应委托给内部存储。"""
        expected = [{"id": "mem-1", "score": 0.8, "payload": {}}]
        sparse_vector = {"indices": [0, 5, 10], "values": [1.0, 0.5, 0.8]}

        result = await adapter.search_sparse("test-collection", sparse_vector, limit=10)

        assert result == expected
        mock_qdrant_storage.search_sparse.assert_called_once()
