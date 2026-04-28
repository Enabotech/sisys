"""QdrantClient 单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.storage.qdrant.client import QdrantClientWrapper


@pytest.fixture
def mock_async_client():
    """模拟异步 Qdrant 客户端。"""
    client = AsyncMock()
    return client


class TestQdrantClientWrapper:
    """QdrantClientWrapper 测试类。"""

    def test_default_initialization(self):
        """测试默认初始化。"""
        wrapper = QdrantClientWrapper()
        assert wrapper._host == "localhost"
        assert wrapper._port == 6333
        assert wrapper._grpc_port == 6334
        assert wrapper._api_key is None
        assert wrapper._https is False
        assert wrapper._timeout == 30.0
        assert wrapper._max_retries == 3
        assert wrapper._client is None

    def test_custom_initialization(self):
        """测试自定义初始化。"""
        wrapper = QdrantClientWrapper(
            host="qdrant.example.com",
            port=8000,
            grpc_port=8001,
            api_key="test-key",  # pragma: allowlist secret
            https=True,
            timeout=60.0,
            max_retries=5,
        )
        assert wrapper._host == "qdrant.example.com"
        assert wrapper._port == 8000
        assert wrapper._grpc_port == 8001
        assert wrapper._api_key == "test-key"  # pragma: allowlist secret
        assert wrapper._https is True
        assert wrapper._timeout == 60.0
        assert wrapper._max_retries == 5

    @patch("src.infrastructure.storage.qdrant.client.AsyncQdrantClient")
    def test_lazy_initialization(self, mock_client: MagicMock, mock_async_client: AsyncMock):
        """测试懒初始化。"""
        mock_client.return_value = mock_async_client
        wrapper = QdrantClientWrapper()
        assert wrapper._client is None

        client = wrapper.get_async_client()
        assert client is not None
        assert wrapper._client is mock_async_client
        mock_client.assert_called_once()

        client2 = wrapper.get_async_client()
        assert client2 is client
        assert mock_client.call_count == 1

    @patch("src.infrastructure.storage.qdrant.client.AsyncQdrantClient")
    async def test_health_check_success(self, mock_client: MagicMock, mock_async_client: AsyncMock):
        """测试健康检查成功。"""
        mock_client.return_value = mock_async_client
        mock_async_client.get_collections = AsyncMock(return_value=MagicMock())

        wrapper = QdrantClientWrapper()
        result = await wrapper.health_check()
        assert result is True

    @patch("src.infrastructure.storage.qdrant.client.AsyncQdrantClient")
    async def test_health_check_failure(self, mock_client: MagicMock, mock_async_client: AsyncMock):
        """测试健康检查失败。"""
        mock_client.return_value = mock_async_client
        mock_async_client.get_collections = AsyncMock(side_effect=Exception("Connection refused"))

        wrapper = QdrantClientWrapper()
        result = await wrapper.health_check()
        assert result is False

    @patch("src.infrastructure.storage.qdrant.client.AsyncQdrantClient")
    async def test_close(self, mock_client: MagicMock, mock_async_client: AsyncMock):
        """测试关闭连接。"""
        mock_client.return_value = mock_async_client
        mock_async_client.close = AsyncMock()

        wrapper = QdrantClientWrapper()
        wrapper.get_async_client()
        await wrapper.close()

        mock_async_client.close.assert_called_once()
        assert wrapper._client is None

    @patch("src.infrastructure.storage.qdrant.client.AsyncQdrantClient")
    async def test_close_without_client(self, mock_client: MagicMock):
        """测试未初始化客户端时关闭连接。"""
        wrapper = QdrantClientWrapper()
        await wrapper.close()
        mock_client.assert_not_called()
