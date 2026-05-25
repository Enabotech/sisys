"""Qdrant Collection Manager 单元测试（Mock 版本）"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.storage.qdrant.collection_manager import QdrantCollectionManager


@pytest.fixture
def mock_client():
    """模拟 AsyncQdrantClient"""
    return AsyncMock()


class TestQdrantManager:
    """QdrantCollectionManager 测试类"""

    async def test_create_collection_success(self, mock_client):
        """测试成功创建 Collection"""
        mock_client.get_collections = AsyncMock(return_value=MagicMock(collections=[]))

        manager = QdrantCollectionManager(mock_client)
        result = await manager.create_collection("sisys:documents:finance")

        assert result is True
        mock_client.create_collection.assert_called_once()

    async def test_create_collection_already_exists(self, mock_client):
        """测试 Collection 已存在时返回 False"""
        existing_collection = MagicMock()
        existing_collection.name = "sisys:documents:finance"
        mock_client.get_collections = AsyncMock(return_value=MagicMock(collections=[existing_collection]))

        manager = QdrantCollectionManager(mock_client)
        result = await manager.create_collection("sisys:documents:finance")

        assert result is False
        mock_client.create_collection.assert_not_called()

    async def test_delete_collection_success(self, mock_client):
        """测试成功删除 Collection"""
        existing_collection = MagicMock()
        existing_collection.name = "sisys:documents:finance"
        mock_client.get_collections = AsyncMock(return_value=MagicMock(collections=[existing_collection]))
        mock_client.delete_collection = AsyncMock()

        manager = QdrantCollectionManager(mock_client)
        result = await manager.delete_collection("sisys:documents:finance")

        assert result is True
        mock_client.delete_collection.assert_called_once_with(collection_name="sisys:documents:finance")

    async def test_delete_collection_not_exists(self, mock_client):
        """测试删除不存在的 Collection 返回 False"""
        mock_client.get_collections = AsyncMock(return_value=MagicMock(collections=[]))

        manager = QdrantCollectionManager(mock_client)
        result = await manager.delete_collection("sisys:documents:finance")

        assert result is False
        mock_client.delete_collection.assert_not_called()

    async def test_collection_exists_true(self, mock_client):
        """测试 Collection 存在时返回 True"""
        existing_collection = MagicMock()
        existing_collection.name = "sisys:documents:finance"
        mock_client.get_collections = AsyncMock(return_value=MagicMock(collections=[existing_collection]))

        manager = QdrantCollectionManager(mock_client)
        result = await manager.collection_exists("sisys:documents:finance")

        assert result is True

    async def test_collection_exists_false(self, mock_client):
        """测试 Collection 不存在时返回 False"""
        mock_client.get_collections = AsyncMock(return_value=MagicMock(collections=[]))

        manager = QdrantCollectionManager(mock_client)
        result = await manager.collection_exists("sisys:documents:finance")

        assert result is False

    async def test_collection_exists_exception(self, mock_client):
        """测试异常时返回 False"""
        mock_client.get_collections = AsyncMock(side_effect=Exception("Connection error"))

        manager = QdrantCollectionManager(mock_client)
        result = await manager.collection_exists("sisys:documents:finance")

        assert result is False

    async def test_list_collections(self, mock_client):
        """测试列出所有 Collection"""
        col1 = MagicMock()
        col1.name = "sisys:documents:finance"
        col2 = MagicMock()
        col2.name = "sisys:documents:hr"
        mock_client.get_collections = AsyncMock(return_value=MagicMock(collections=[col1, col2]))

        manager = QdrantCollectionManager(mock_client)
        result = await manager.list_collections()

        assert result == ["sisys:documents:finance", "sisys:documents:hr"]

    async def test_list_collections_exception(self, mock_client):
        """测试异常时返回空列表"""
        mock_client.get_collections = AsyncMock(side_effect=Exception("Connection error"))

        manager = QdrantCollectionManager(mock_client)
        result = await manager.list_collections()

        assert result == []

    async def test_create_collection_with_custom_config(self, mock_client):
        """测试使用自定义配置创建 Collection"""
        mock_client.get_collections = AsyncMock(return_value=MagicMock(collections=[]))

        manager = QdrantCollectionManager(mock_client)
        result = await manager.create_collection(
            "sisys:embeddings:main",
            vector_size=512,
            distance="Euclidean",
            shard_number=2,
        )

        assert result is True
        call_kwargs = mock_client.create_collection.call_args[1]
        assert call_kwargs["vectors_config"].size == 512
