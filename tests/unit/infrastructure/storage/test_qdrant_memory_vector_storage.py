"""Tests for QdrantMemoryVectorStorage — MemoryVectorPort implementation.

验证存储包装器正确委托 QdrantAdapter，并实现记忆向量特有语义。
架构意义：组合注入适配器，添加业务语义层。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.storage.qdrant.qdrant_memory_vector_storage import (
    MEMORY_COLLECTION,
    QdrantMemoryVectorStorage,
)


class TestQdrantMemoryVectorStorageInterface:
    """验证存储包装器正确初始化"""

    def test_delegates_to_internal_adapter(self):
        """验证适配器通过构造函数注入"""
        mock_adapter = MagicMock()
        storage = QdrantMemoryVectorStorage(mock_adapter)
        assert storage._adapter is mock_adapter

    def test_uses_default_collection_when_not_specified(self):
        """验证默认 collection 名称"""
        mock_adapter = MagicMock()
        storage = QdrantMemoryVectorStorage(mock_adapter)
        assert storage._collection == MEMORY_COLLECTION

    def test_uses_custom_collection_when_specified(self):
        """验证自定义 collection 名称"""
        mock_adapter = MagicMock()
        storage = QdrantMemoryVectorStorage(mock_adapter, collection="custom_collection")
        assert storage._collection == "custom_collection"

    def test_uses_default_embed_fn_when_not_specified(self):
        """验证默认使用确定性 hash embedding"""
        mock_adapter = MagicMock()
        storage = QdrantMemoryVectorStorage(mock_adapter)
        assert storage._embed_fn == storage._deterministic_embed

    def test_uses_custom_embed_fn_when_specified(self):
        """验证自定义 embedding 函数"""
        mock_adapter = MagicMock()

        def custom_embed(text: str) -> list[float]:
            return [0.5] * 64

        storage = QdrantMemoryVectorStorage(mock_adapter, embed_fn=custom_embed)
        assert storage._embed_fn is custom_embed


class TestDeterministicEmbed:
    """_deterministic_embed 静态方法验证"""

    def test_returns_128_dimension_vector(self):
        """验证返回 128 维向量"""
        vector = QdrantMemoryVectorStorage._deterministic_embed("test content")
        assert len(vector) == 128

    def test_returns_floats_in_valid_range(self):
        """验证返回值在 [-0.5, 0.5] 范围内"""
        vector = QdrantMemoryVectorStorage._deterministic_embed("test content")
        for val in vector:
            assert -0.5 <= val <= 0.5

    def test_deterministic_for_same_input(self):
        """验证相同输入产生相同输出"""
        vector1 = QdrantMemoryVectorStorage._deterministic_embed("same input")
        vector2 = QdrantMemoryVectorStorage._deterministic_embed("same input")
        assert vector1 == vector2

    def test_different_for_different_input(self):
        """验证不同输入产生不同输出"""
        vector1 = QdrantMemoryVectorStorage._deterministic_embed("input one")
        vector2 = QdrantMemoryVectorStorage._deterministic_embed("input two")
        assert vector1 != vector2

    def test_handles_empty_string(self):
        """验证空字符串返回有效向量"""
        vector = QdrantMemoryVectorStorage._deterministic_embed("")
        assert len(vector) == 128


class TestQdrantMemoryVectorStorageDelegation:
    """验证 L3VectorPort 方法正确委托给适配器"""

    @pytest.mark.asyncio
    async def test_upsert_points_delegates_to_adapter(self):
        """验证 upsert_points 正确委托"""
        mock_adapter = AsyncMock()
        mock_adapter.upsert_points = AsyncMock(return_value=True)

        storage = QdrantMemoryVectorStorage(mock_adapter)
        points = [{"id": "p1", "vector": [0.1] * 128, "payload": {}}]

        result = await storage.upsert_points("test-collection", points)

        assert result is True
        mock_adapter.upsert_points.assert_called_once_with("test-collection", points)

    @pytest.mark.asyncio
    async def test_delete_points_delegates_to_adapter(self):
        """验证 delete_points 正确委托"""
        mock_adapter = AsyncMock()
        mock_adapter.delete_points = AsyncMock(return_value=True)

        storage = QdrantMemoryVectorStorage(mock_adapter)
        result = await storage.delete_points("test-collection", ["id1", "id2"])

        assert result is True
        mock_adapter.delete_points.assert_called_once_with("test-collection", ["id1", "id2"])

    @pytest.mark.asyncio
    async def test_get_point_delegates_to_adapter(self):
        """验证 get_point 正确委托"""
        mock_adapter = AsyncMock()
        expected = {"id": "p1", "vector": [0.1], "payload": {}}
        mock_adapter.get_point = AsyncMock(return_value=expected)

        storage = QdrantMemoryVectorStorage(mock_adapter)
        result = await storage.get_point("test-collection", "p1")

        assert result == expected
        mock_adapter.get_point.assert_called_once_with("test-collection", "p1")

    @pytest.mark.asyncio
    async def test_search_delegates_to_adapter(self):
        """验证 search 正确委托"""
        mock_adapter = AsyncMock()
        expected = [{"id": "p1", "score": 0.9, "payload": {}}]
        mock_adapter.search = AsyncMock(return_value=expected)

        storage = QdrantMemoryVectorStorage(mock_adapter)
        result = await storage.search(
            "test-collection",
            [0.1] * 128,
            limit=5,
            filter_payload={"type": "user"},
        )

        assert result == expected
        mock_adapter.search.assert_called_once_with("test-collection", [0.1] * 128, 5, {"type": "user"})

    @pytest.mark.asyncio
    async def test_search_sparse_delegates_to_adapter(self):
        """验证 search_sparse 正确委托"""
        mock_adapter = AsyncMock()
        expected = [{"id": "p1", "score": 0.8, "payload": {}}]
        mock_adapter.search_sparse = AsyncMock(return_value=expected)

        storage = QdrantMemoryVectorStorage(mock_adapter)
        sparse_vector = {"indices": [0, 5], "values": [1.0, 0.5]}
        result = await storage.search_sparse(
            "test-collection",
            sparse_vector,
            limit=10,
            filter_payload={"owner": "user1"},
        )

        assert result == expected
        mock_adapter.search_sparse.assert_called_once_with("test-collection", sparse_vector, 10, {"owner": "user1"})

    @pytest.mark.asyncio
    async def test_create_collection_delegates_to_adapter(self):
        """验证 create_collection 正确委托"""
        mock_adapter = AsyncMock()
        mock_adapter.create_collection = AsyncMock(return_value=True)

        storage = QdrantMemoryVectorStorage(mock_adapter)
        result = await storage.create_collection("new-collection", vector_size=128, vector_params={"distance": "Cosine"})

        assert result is True
        mock_adapter.create_collection.assert_called_once_with("new-collection", 128, {"distance": "Cosine"})

    @pytest.mark.asyncio
    async def test_delete_collection_delegates_to_adapter(self):
        """验证 delete_collection 正确委托"""
        mock_adapter = AsyncMock()
        mock_adapter.delete_collection = AsyncMock(return_value=True)

        storage = QdrantMemoryVectorStorage(mock_adapter)
        result = await storage.delete_collection("old-collection")

        assert result is True
        mock_adapter.delete_collection.assert_called_once_with("old-collection")

    @pytest.mark.asyncio
    async def test_collection_exists_delegates_to_adapter(self):
        """验证 collection_exists 正确委托"""
        mock_adapter = AsyncMock()
        mock_adapter.collection_exists = AsyncMock(return_value=True)

        storage = QdrantMemoryVectorStorage(mock_adapter)
        result = await storage.collection_exists("test-collection")

        assert result is True
        mock_adapter.collection_exists.assert_called_once_with("test-collection")

    @pytest.mark.asyncio
    async def test_list_collections_delegates_to_adapter(self):
        """验证 list_collections 正确委托"""
        mock_adapter = AsyncMock()
        expected = ["coll1", "coll2"]
        mock_adapter.list_collections = AsyncMock(return_value=expected)

        storage = QdrantMemoryVectorStorage(mock_adapter)
        result = await storage.list_collections()

        assert result == expected
        mock_adapter.list_collections.assert_called_once_with()


class TestIndexMemory:
    """index_memory 方法验证（特有行为）"""

    @pytest.mark.asyncio
    async def test_generates_embedding_and_upserts(self):
        """验证自动生成 embedding 并存储"""
        mock_adapter = AsyncMock()
        mock_adapter.upsert_points = AsyncMock(return_value=True)

        storage = QdrantMemoryVectorStorage(mock_adapter)
        result = await storage.index_memory(
            memory_id="mem-123",
            content="This is a test memory",
            memory_type="conversation",
            owner_id="user-456",
        )

        assert result is True
        mock_adapter.upsert_points.assert_called_once()
        call_args = mock_adapter.upsert_points.call_args
        assert call_args[0][0] == MEMORY_COLLECTION

        points = call_args[0][1]
        assert len(points) == 1
        assert points[0]["id"] == "mem-123"
        assert len(points[0]["vector"]) == 128
        assert points[0]["payload"]["memory_type"] == "conversation"
        assert points[0]["payload"]["owner_id"] == "user-456"

    @pytest.mark.asyncio
    async def test_uses_custom_embed_fn(self) -> None:
        """验证使用自定义 embedding 函数"""
        mock_adapter = AsyncMock()
        mock_adapter.upsert_points = AsyncMock(return_value=True)

        custom_vector: list[float] = [0.7] * 256

        def custom_embed(text: str) -> list[float]:
            return custom_vector

        storage = QdrantMemoryVectorStorage(mock_adapter, embed_fn=custom_embed)
        await storage.index_memory(
            memory_id="mem-789",
            content="Custom embedding test",
            memory_type="note",
            owner_id="user-111",
        )

        call_args = mock_adapter.upsert_points.call_args
        points = call_args[0][1]
        assert points[0]["vector"] == custom_vector

    @pytest.mark.asyncio
    async def test_uses_custom_collection(self):
        """验证使用自定义 collection"""
        mock_adapter = AsyncMock()
        mock_adapter.upsert_points = AsyncMock(return_value=True)

        storage = QdrantMemoryVectorStorage(mock_adapter, collection="custom_memories")
        await storage.index_memory(
            memory_id="mem-001",
            content="Test",
            memory_type="test",
            owner_id="user-001",
        )

        call_args = mock_adapter.upsert_points.call_args
        assert call_args[0][0] == "custom_memories"


class TestSearchSimilarMemories:
    """search_similar_memories 方法验证（特有行为）"""

    @pytest.mark.asyncio
    async def test_generates_embedding_and_searches(self):
        """验证自动生成查询 embedding 并检索"""
        mock_adapter = AsyncMock()
        expected_results = [{"id": "mem-1", "score": 0.95, "payload": {}}]
        mock_adapter.search = AsyncMock(return_value=expected_results)

        storage = QdrantMemoryVectorStorage(mock_adapter)
        result = await storage.search_similar_memories(
            query="search query",
            limit=5,
        )

        assert result == expected_results
        mock_adapter.search.assert_called_once()
        call_args = mock_adapter.search.call_args
        assert call_args[0][0] == MEMORY_COLLECTION
        assert len(call_args[0][1]) == 128
        assert call_args[1]["limit"] == 5
        assert call_args[1]["filter_payload"] is None

    @pytest.mark.asyncio
    async def test_builds_filter_payload_with_owner_id(self):
        """验证构建 owner_id 过滤条件"""
        mock_adapter = AsyncMock()
        mock_adapter.search = AsyncMock(return_value=[])

        storage = QdrantMemoryVectorStorage(mock_adapter)
        await storage.search_similar_memories(
            query="test query",
            owner_id="user-123",
        )

        call_args = mock_adapter.search.call_args
        assert call_args[1]["filter_payload"] == {"owner_id": "user-123"}

    @pytest.mark.asyncio
    async def test_builds_filter_payload_with_memory_type(self):
        """验证构建 memory_type 过滤条件"""
        mock_adapter = AsyncMock()
        mock_adapter.search = AsyncMock(return_value=[])

        storage = QdrantMemoryVectorStorage(mock_adapter)
        await storage.search_similar_memories(
            query="test query",
            memory_type="conversation",
        )

        call_args = mock_adapter.search.call_args
        assert call_args[1]["filter_payload"] == {"memory_type": "conversation"}

    @pytest.mark.asyncio
    async def test_builds_filter_payload_with_both_filters(self):
        """验证同时构建 owner_id 和 memory_type 过滤条件"""
        mock_adapter = AsyncMock()
        mock_adapter.search = AsyncMock(return_value=[])

        storage = QdrantMemoryVectorStorage(mock_adapter)
        await storage.search_similar_memories(
            query="test query",
            owner_id="user-456",
            memory_type="note",
        )

        call_args = mock_adapter.search.call_args
        expected_filter = {"owner_id": "user-456", "memory_type": "note"}
        assert call_args[1]["filter_payload"] == expected_filter

    @pytest.mark.asyncio
    async def test_uses_custom_embed_fn_for_query(self) -> None:
        """验证查询使用自定义 embedding 函数"""
        mock_adapter = AsyncMock()
        mock_adapter.search = AsyncMock(return_value=[])

        custom_vector: list[float] = [0.3] * 64

        def custom_embed(text: str) -> list[float]:
            return custom_vector

        storage = QdrantMemoryVectorStorage(mock_adapter, embed_fn=custom_embed)
        await storage.search_similar_memories(query="custom embedding query")

        call_args = mock_adapter.search.call_args
        assert call_args[0][1] == custom_vector

    @pytest.mark.asyncio
    async def test_uses_custom_collection(self):
        """验证使用自定义 collection"""
        mock_adapter = AsyncMock()
        mock_adapter.search = AsyncMock(return_value=[])

        storage = QdrantMemoryVectorStorage(mock_adapter, collection="my_memories")
        await storage.search_similar_memories(query="test")

        call_args = mock_adapter.search.call_args
        assert call_args[0][0] == "my_memories"
