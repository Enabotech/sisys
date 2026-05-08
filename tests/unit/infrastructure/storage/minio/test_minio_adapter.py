"""MinIOAdapter 实现测试。

验证 MinIOAdapter 实现了 L4ObjectPort 接口。
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestMinIOAdapterL4ObjectPortCompliance:
    """验证 MinIOAdapter 实现了 L4ObjectPort 接口。"""

    def test_adapter_implements_l4_object_port(self) -> None:
        """MinIOAdapter 应实现 L4ObjectPort。"""
        from src.domain.ports.l4_object import L4ObjectPort
        from src.infrastructure.storage.minio.minio_adapter import MinIOAdapter

        mock_repository = MagicMock()
        adapter = MinIOAdapter(mock_repository)

        assert isinstance(adapter, L4ObjectPort)

    def test_adapter_has_all_required_methods(self) -> None:
        """MinIOAdapter 应有 L4ObjectPort 的所有方法。"""
        from src.domain.ports.l4_object import L4ObjectPort
        from src.infrastructure.storage.minio.minio_adapter import MinIOAdapter

        mock_repository = MagicMock()
        adapter = MinIOAdapter(mock_repository)

        for method_name in ["store", "retrieve", "delete", "get_metadata", "archive"]:
            assert hasattr(adapter, method_name)
            assert hasattr(L4ObjectPort, method_name)

    def test_crud_methods_are_async(self) -> None:
        """store, delete, get_metadata, archive 应是 async。"""
        from src.infrastructure.storage.minio.minio_adapter import MinIOAdapter

        mock_repository = MagicMock()
        adapter = MinIOAdapter(mock_repository)

        for method_name in ["store", "delete", "get_metadata", "archive"]:
            method = getattr(adapter, method_name)
            assert asyncio.iscoroutinefunction(method), f"{method_name} should be async"

    def test_retrieve_is_sync_iterator(self) -> None:
        """retrieve 应是同步迭代器。"""
        from src.infrastructure.storage.minio.minio_adapter import MinIOAdapter

        mock_repository = MagicMock()
        adapter = MinIOAdapter(mock_repository)

        method = adapter.retrieve
        assert not asyncio.iscoroutinefunction(method)


class TestMinIOAdapterBehavior:
    """MinIOAdapter 行为测试。"""

    @pytest.fixture
    def mock_minio_repository(self):
        """创建模拟的 MinIORepository。"""
        mock = MagicMock()
        mock.store = AsyncMock(return_value="version-id-123")
        mock.delete = AsyncMock(return_value=True)
        mock.get_metadata = AsyncMock(return_value={"size": 1024, "content_type": "application/pdf"})
        mock.archive = AsyncMock(return_value="archived-id")
        return mock

    @pytest.fixture
    def adapter(self, mock_minio_repository):
        """创建 MinIOAdapter 实例。"""
        from src.infrastructure.storage.minio.minio_adapter import MinIOAdapter

        return MinIOAdapter(mock_minio_repository)

    @pytest.mark.asyncio
    async def test_store_delegates_to_repository(self, adapter, mock_minio_repository) -> None:
        """store 应委托给内部仓储。"""
        result = await adapter.store(
            bucket_type="raw-documents",
            object_key="docs/test.pdf",
            file_path="/tmp/test.pdf",
            content_type="application/pdf",
        )

        assert result == "version-id-123"
        mock_minio_repository.store.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_delegates_to_repository(self, adapter, mock_minio_repository) -> None:
        """delete 应委托给内部仓储。"""
        result = await adapter.delete(
            bucket_type="raw-documents",
            object_key="docs/test.pdf",
        )

        assert result is True
        mock_minio_repository.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_metadata_delegates_to_repository(self, adapter, mock_minio_repository) -> None:
        """get_metadata 应委托给内部仓储。"""
        expected = {"size": 1024, "content_type": "application/pdf"}
        result = await adapter.get_metadata(
            bucket_type="raw-documents",
            object_key="docs/test.pdf",
        )

        assert result == expected
        mock_minio_repository.get_metadata.assert_called_once()

    @pytest.mark.asyncio
    async def test_archive_delegates_to_repository(self, adapter, mock_minio_repository) -> None:
        """archive 应委托给内部仓储。"""
        result = await adapter.archive(
            bucket_type="raw-documents",
            object_key="docs/test.pdf",
            retention_days=2555,
        )

        assert result == "archived-id"
        mock_minio_repository.archive.assert_called_once()

    def test_retrieve_delegates_to_repository(self, adapter, mock_minio_repository) -> None:
        """retrieve 应委托给内部仓储。"""

        # 创建一个同步的生成器函数
        def mock_retrieve():
            yield b"chunk1"
            yield b"chunk2"

        mock_minio_repository.retrieve.return_value = mock_retrieve()

        result = adapter.retrieve(
            bucket_type="raw-documents",
            object_key="docs/test.pdf",
        )

        # 验证返回的是迭代器
        assert hasattr(result, "__iter__")
        assert hasattr(result, "__next__")
