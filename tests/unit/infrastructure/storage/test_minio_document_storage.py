"""Tests for MinIODocumentStorage — DocumentStoragePort implementation.

验证存储包装器正确委托 MinIOAdapter，并实现文档业务特有语义
架构意义：组合注入适配器，添加自动路径生成和文档管理语义
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from src.infrastructure.storage.minio.minio_document_storage import MinIODocumentStorage


class TestMinIODocumentStorageInterface:
    """验证存储包装器正确初始化"""

    def test_delegates_to_internal_adapter(self):
        """验证适配器通过构造函数注入"""
        mock_adapter = MagicMock()
        storage = MinIODocumentStorage(mock_adapter)
        assert storage._adapter is mock_adapter


class TestMinIODocumentStorageDelegation:
    """验证 L4ObjectPort 方法正确委托给适配器"""

    async def test_store_delegates_to_adapter(self):
        """验证 store 正确委托"""
        mock_adapter = AsyncMock()
        mock_adapter.store = AsyncMock(return_value="etag-123")

        storage = MinIODocumentStorage(mock_adapter)
        result = await storage.store(
            bucket_type="raw-documents",
            object_key="test/file.pdf",
            file_path="/tmp/file.pdf",
            content_type="application/pdf",
            tags={"key": "value"},
        )

        assert result == "etag-123"
        mock_adapter.store.assert_called_once_with(
            "raw-documents",
            "test/file.pdf",
            "/tmp/file.pdf",
            "application/pdf",
            {"key": "value"},
        )

    def test_retrieve_delegates_to_adapter(self):
        """验证 retrieve 正确委托（同步方法）"""
        mock_adapter = MagicMock()
        mock_stream = MagicMock()
        mock_adapter.retrieve = MagicMock(return_value=mock_stream)

        storage = MinIODocumentStorage(mock_adapter)
        result = storage.retrieve("raw-documents", "test/file.pdf", version_id="v1")

        assert result is mock_stream
        mock_adapter.retrieve.assert_called_once_with("raw-documents", "test/file.pdf", "v1")

    async def test_delete_delegates_to_adapter(self):
        """验证 delete 正确委托"""
        mock_adapter = AsyncMock()
        mock_adapter.delete = AsyncMock(return_value=True)

        storage = MinIODocumentStorage(mock_adapter)
        result = await storage.delete("raw-documents", "test/file.pdf", version_id="v1")

        assert result is True
        mock_adapter.delete.assert_called_once_with("raw-documents", "test/file.pdf", "v1")

    async def test_get_metadata_delegates_to_adapter(self):
        """验证 get_metadata 正确委托"""
        mock_adapter = AsyncMock()
        expected = {"Content-Type": "application/pdf", "Content-Length": 2048}
        mock_adapter.get_metadata = AsyncMock(return_value=expected)

        storage = MinIODocumentStorage(mock_adapter)
        result = await storage.get_metadata("raw-documents", "test/file.pdf")

        assert result == expected
        mock_adapter.get_metadata.assert_called_once_with("raw-documents", "test/file.pdf", None)

    async def test_archive_delegates_to_adapter(self):
        """验证 archive 正确委托"""
        mock_adapter = AsyncMock()
        mock_adapter.archive = AsyncMock(return_value="archived-etag")

        storage = MinIODocumentStorage(mock_adapter)
        result = await storage.archive(
            "raw-documents",
            "old/file.pdf",
            content=b"data",
            retention_days=365,
        )

        assert result == "archived-etag"
        mock_adapter.archive.assert_called_once_with("raw-documents", "old/file.pdf", b"data", 365)

    async def test_list_objects_delegates_to_adapter(self):
        """验证 list_objects 正确委托"""
        mock_adapter = AsyncMock()
        expected = [{"key": "file1.pdf"}, {"key": "file2.pdf"}]
        mock_adapter.list_objects = AsyncMock(return_value=expected)

        storage = MinIODocumentStorage(mock_adapter)
        result = await storage.list_objects("raw-documents", prefix="docs/", recursive=True)

        assert result == expected
        mock_adapter.list_objects.assert_called_once_with("raw-documents", "docs/", True)


class TestStoreDocument:
    """store_document 方法验证（特有行为）"""

    async def test_auto_generates_path_with_correct_format(self):
        """验证自动生成路径格式: documents/{user_id}/{doc_type}/{YYYY-MM}/{timestamp}"""
        mock_adapter = AsyncMock()
        mock_adapter.store = AsyncMock(return_value="etag-001")

        storage = MinIODocumentStorage(mock_adapter)
        object_key = await storage.store_document(
            user_id="user-123",
            doc_type="invoice",
            file_path="/tmp/invoice.pdf",
        )

        assert object_key.startswith("documents/user-123/invoice/")
        parts = object_key.split("/")
        assert len(parts) == 5
        assert parts[0] == "documents"
        assert parts[1] == "user-123"
        assert parts[2] == "invoice"
        now = datetime.now(UTC)
        assert parts[3] == now.strftime("%Y-%m")

    async def test_uses_raw_documents_bucket(self):
        """验证使用 raw-documents bucket 类型"""
        mock_adapter = AsyncMock()
        mock_adapter.store = AsyncMock(return_value="etag-002")

        storage = MinIODocumentStorage(mock_adapter)
        await storage.store_document(
            user_id="user-456",
            doc_type="report",
            file_path="/tmp/report.pdf",
        )

        mock_adapter.store.assert_called_once()
        call_args = mock_adapter.store.call_args
        assert call_args[0][0] == "raw-documents"

    async def test_adds_user_id_and_doc_type_tags(self):
        """验证自动添加 user_id 和 doc_type 标签"""
        mock_adapter = AsyncMock()
        mock_adapter.store = AsyncMock(return_value="etag-003")

        storage = MinIODocumentStorage(mock_adapter)
        await storage.store_document(
            user_id="user-789",
            doc_type="contract",
            file_path="/tmp/contract.pdf",
        )

        call_args = mock_adapter.store.call_args
        tags = call_args[1]["tags"]
        assert tags["user_id"] == "user-789"
        assert tags["doc_type"] == "contract"

    async def test_adds_metadata_as_prefixed_tags(self):
        """验证 metadata 以 meta_ 前缀添加到标签"""
        mock_adapter = AsyncMock()
        mock_adapter.store = AsyncMock(return_value="etag-004")

        storage = MinIODocumentStorage(mock_adapter)
        await storage.store_document(
            user_id="user-001",
            doc_type="pdf",
            file_path="/tmp/file.pdf",
            metadata={"department": "finance", "priority": "high"},
        )

        call_args = mock_adapter.store.call_args
        tags = call_args[1]["tags"]
        assert tags["meta_department"] == "finance"
        assert tags["meta_priority"] == "high"

    async def test_no_metadata_tags_when_metadata_is_none(self):
        """验证 metadata 为 None 时不添加额外标签"""
        mock_adapter = AsyncMock()
        mock_adapter.store = AsyncMock(return_value="etag-005")

        storage = MinIODocumentStorage(mock_adapter)
        await storage.store_document(
            user_id="user-002",
            doc_type="pdf",
            file_path="/tmp/file.pdf",
            metadata=None,
        )

        call_args = mock_adapter.store.call_args
        tags = call_args[1]["tags"]
        assert "meta_" not in str(tags.keys())

    async def test_returns_generated_object_key(self):
        """验证返回生成的 object_key"""
        mock_adapter = AsyncMock()
        mock_adapter.store = AsyncMock(return_value="etag-006")

        storage = MinIODocumentStorage(mock_adapter)
        result = await storage.store_document(
            user_id="user-abc",
            doc_type="memo",
            file_path="/tmp/memo.txt",
        )

        assert isinstance(result, str)
        assert "user-abc" in result
        assert "memo" in result


class TestListUserDocuments:
    """list_user_documents 方法验证（特有行为）"""

    async def test_builds_prefix_with_user_id_only(self):
        """验证仅 user_id 时构建前缀 documents/{user_id}/"""
        mock_adapter = AsyncMock()
        mock_adapter.list_objects = AsyncMock(return_value=[])

        storage = MinIODocumentStorage(mock_adapter)
        await storage.list_user_documents(user_id="user-123")

        mock_adapter.list_objects.assert_called_once()
        call_args = mock_adapter.list_objects.call_args
        assert call_args[0][0] == "raw-documents"
        assert call_args[1]["prefix"] == "documents/user-123/"

    async def test_builds_prefix_with_user_id_and_doc_type(self):
        """验证带 doc_type 时构建前缀 documents/{user_id}/{doc_type}/"""
        mock_adapter = AsyncMock()
        mock_adapter.list_objects = AsyncMock(return_value=[])

        storage = MinIODocumentStorage(mock_adapter)
        await storage.list_user_documents(user_id="user-456", doc_type="invoice")

        call_args = mock_adapter.list_objects.call_args
        assert call_args[1]["prefix"] == "documents/user-456/invoice/"

    async def test_returns_adapter_result(self):
        """验证返回适配器的结果"""
        mock_adapter = AsyncMock()
        expected = [
            {"key": "documents/user-789/report/2025-05/20250501120000"},
            {"key": "documents/user-789/report/2025-05/20250502140000"},
        ]
        mock_adapter.list_objects = AsyncMock(return_value=expected)

        storage = MinIODocumentStorage(mock_adapter)
        result = await storage.list_user_documents(user_id="user-789")

        assert result == expected

    async def test_uses_raw_documents_bucket(self):
        """验证使用 raw-documents bucket"""
        mock_adapter = AsyncMock()
        mock_adapter.list_objects = AsyncMock(return_value=[])

        storage = MinIODocumentStorage(mock_adapter)
        await storage.list_user_documents(user_id="user-001")

        call_args = mock_adapter.list_objects.call_args
        assert call_args[0][0] == "raw-documents"


class TestGetDocumentMetadata:
    """get_document_metadata 方法验证（特有行为）"""

    async def test_returns_metadata_on_success(self):
        """验证成功时返回元数据"""
        mock_adapter = AsyncMock()
        expected = {"Content-Type": "application/pdf", "size": 1024}
        mock_adapter.get_metadata = AsyncMock(return_value=expected)

        storage = MinIODocumentStorage(mock_adapter)
        result = await storage.get_document_metadata(user_id="user-123", document_id="documents/user-123/pdf/2025-05/file")

        assert result == expected
        mock_adapter.get_metadata.assert_called_once_with(
            "raw-documents",
            "documents/user-123/pdf/2025-05/file",
        )

    async def test_returns_none_on_exception(self):
        """验证异常时返回 None"""
        mock_adapter = AsyncMock()
        mock_adapter.get_metadata = AsyncMock(side_effect=Exception("not found"))

        storage = MinIODocumentStorage(mock_adapter)
        result = await storage.get_document_metadata(user_id="user-456", document_id="nonexistent-key")

        assert result is None

    async def test_returns_none_on_runtime_error(self):
        """验证运行时错误时返回 None"""
        mock_adapter = AsyncMock()
        mock_adapter.get_metadata = AsyncMock(side_effect=RuntimeError("connection lost"))

        storage = MinIODocumentStorage(mock_adapter)
        result = await storage.get_document_metadata(user_id="user-789", document_id="some-key")

        assert result is None
