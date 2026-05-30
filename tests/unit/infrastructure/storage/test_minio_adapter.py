"""Tests for MinIOAdapter — L4ObjectPort implementation.

验证适配器正确委托仓储操作，实现 L4ObjectPort 接口
架构意义：薄适配器层，流式操作防 OOM
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from src.infrastructure.storage.minio.minio_adapter import MinIOAdapter


class TestMinIOAdapterInterface:
    """验证适配器实现 L4ObjectPort 接口"""

    def test_delegates_to_internal_repository(self):
        """验证适配器委托操作给内部仓储"""
        mock_repository = MagicMock()
        adapter = MinIOAdapter(mock_repository)
        assert adapter._repository is mock_repository


class TestMinIOAdapterStore:
    """store 方法验证"""

    async def test_store_delegates_with_all_params(self):
        """验证 store 正确委托所有参数"""
        mock_repository = AsyncMock()
        mock_repository.store = AsyncMock(return_value="etag-123")

        adapter = MinIOAdapter(mock_repository)
        result = await adapter.store(
            bucket_type="raw-documents",
            object_key="2025/05/test.pdf",
            file_path="/tmp/test.pdf",
            content_type="application/pdf",
            tags={"department": "engineering"},
        )

        assert result == "etag-123"
        mock_repository.store.assert_called_once_with(
            bucket_type="raw-documents",
            object_key="2025/05/test.pdf",
            file_path="/tmp/test.pdf",
            content_type="application/pdf",
            tags={"department": "engineering"},
        )

    async def test_store_returns_string_etag(self):
        """验证返回字符串类型 ETag"""
        mock_repository = AsyncMock()
        mock_repository.store = AsyncMock(return_value="version-abc-123")

        adapter = MinIOAdapter(mock_repository)
        result = await adapter.store(
            bucket_type="test",
            object_key="key",
            file_path="/tmp/file",
        )

        assert isinstance(result, str)


class TestMinIOAdapterRetrieve:
    """retrieve 方法验证"""

    def test_retrieve_returns_async_iterator(self):
        """验证 retrieve 返回 AsyncIterator[bytes]"""
        mock_repository = MagicMock()

        async def mock_stream():
            yield b"chunk1"
            yield b"chunk2"

        mock_repository.retrieve = MagicMock(return_value=mock_stream())

        adapter = MinIOAdapter(mock_repository)
        result = adapter.retrieve(
            bucket_type="test",
            object_key="key",
            version_id="v1",
        )

        import inspect

        assert inspect.isasyncgen(result) or hasattr(result, "__anext__")


class TestMinIOAdapterDelete:
    """delete 方法验证"""

    async def test_delete_delegates_correctly(self):
        """验证 delete 正确委托"""
        mock_repository = AsyncMock()
        mock_repository.delete = AsyncMock(return_value=True)

        adapter = MinIOAdapter(mock_repository)
        result = await adapter.delete(
            bucket_type="test",
            object_key="key",
            version_id="v1",
        )

        assert result is True
        mock_repository.delete.assert_called_once_with(
            bucket_type="test",
            object_key="key",
            version_id="v1",
        )


class TestMinIOAdapterGetMetadata:
    """get_metadata 方法验证"""

    async def test_get_metadata_returns_dict(self):
        """验证返回元数据字典"""
        mock_repository = AsyncMock()
        expected = {
            "Content-Length": 1024,
            "Content-Type": "application/pdf",
            "Last-Modified": "2025-05-01",
        }
        mock_repository.get_metadata = AsyncMock(return_value=expected)

        adapter = MinIOAdapter(mock_repository)
        result = await adapter.get_metadata("test", "key")

        assert result == expected

    async def test_get_metadata_delegates_with_params(self):
        """验证委托时传递所有参数"""
        mock_repository = AsyncMock()
        mock_repository.get_metadata = AsyncMock(return_value={})

        adapter = MinIOAdapter(mock_repository)
        await adapter.get_metadata("bucket", "path/to/file.txt", version_id="v2")

        mock_repository.get_metadata.assert_called_once_with(
            bucket_type="bucket",
            object_key="path/to/file.txt",
            version_id="v2",
        )


class TestMinIOAdapterArchive:
    """archive 方法验证"""

    async def test_archive_delegates_with_retention_days(self):
        """验证 archive 委托并传递 retention_days"""
        mock_repository = AsyncMock()
        mock_repository.archive = AsyncMock(return_value="archived-etag")

        adapter = MinIOAdapter(mock_repository)
        result = await adapter.archive(
            bucket_type="archive",
            object_key="old-document.pdf",
            retention_days=2555,
        )

        assert result == "archived-etag"
        mock_repository.archive.assert_called_once()
        call_kwargs = mock_repository.archive.call_args[1]
        assert call_kwargs["retention_days"] == 2555

    async def test_archive_with_content(self):
        """验证带内容的归档"""
        mock_repository = AsyncMock()
        mock_repository.archive = AsyncMock(return_value="etag-xyz")

        adapter = MinIOAdapter(mock_repository)
        result = await adapter.archive(
            bucket_type="test",
            object_key="file.bin",
            content=b"binary content here",
            retention_days=30,
        )

        assert result == "etag-xyz"


class TestMinIOAdapterMultipart:
    """multipart 分片上传方法验证"""

    async def test_init_multipart_upload_delegates(self):
        """验证 init_multipart_upload 委托"""
        mock_repository = AsyncMock()
        mock_repository.init_multipart_upload = AsyncMock(return_value="upload-id-123")

        adapter = MinIOAdapter(mock_repository)
        result = await adapter.init_multipart_upload(
            bucket_type="raw-documents",
            object_key="docs/test.pdf",
            content_type="application/pdf",
        )

        assert result == "upload-id-123"
        mock_repository.init_multipart_upload.assert_called_once_with(
            bucket_type="raw-documents",
            object_key="docs/test.pdf",
            content_type="application/pdf",
        )

    async def test_upload_part_delegates(self):
        """验证 upload_part 委托"""
        mock_repository = AsyncMock()
        mock_repository.upload_part = AsyncMock(return_value="etag-part-1")

        adapter = MinIOAdapter(mock_repository)
        result = await adapter.upload_part(
            bucket_type="raw-documents",
            object_key="docs/test.pdf",
            upload_id="upload-id-123",
            part_number=1,
            data=b"part data",
        )

        assert result == "etag-part-1"
        mock_repository.upload_part.assert_called_once_with(
            bucket_type="raw-documents",
            object_key="docs/test.pdf",
            upload_id="upload-id-123",
            part_number=1,
            data=b"part data",
        )

    async def test_complete_multipart_upload_delegates(self):
        """验证 complete_multipart_upload 委托"""
        mock_repository = AsyncMock()
        mock_repository.complete_multipart_upload = AsyncMock(return_value="version-id-1")

        adapter = MinIOAdapter(mock_repository)
        parts = [{"PartNumber": 1, "ETag": "etag-1"}, {"PartNumber": 2, "ETag": "etag-2"}]
        result = await adapter.complete_multipart_upload(
            bucket_type="raw-documents",
            object_key="docs/test.pdf",
            upload_id="upload-id-123",
            parts=parts,
        )

        assert result == "version-id-1"
        mock_repository.complete_multipart_upload.assert_called_once_with(
            bucket_type="raw-documents",
            object_key="docs/test.pdf",
            upload_id="upload-id-123",
            parts=parts,
        )

    async def test_abort_multipart_upload_delegates(self):
        """验证 abort_multipart_upload 委托"""
        mock_repository = AsyncMock()
        mock_repository.abort_multipart_upload = AsyncMock(return_value=None)

        adapter = MinIOAdapter(mock_repository)
        await adapter.abort_multipart_upload(
            bucket_type="raw-documents",
            object_key="docs/test.pdf",
            upload_id="upload-id-123",
        )

        mock_repository.abort_multipart_upload.assert_called_once_with(
            bucket_type="raw-documents",
            object_key="docs/test.pdf",
            upload_id="upload-id-123",
        )
