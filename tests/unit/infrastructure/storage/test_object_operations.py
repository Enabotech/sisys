"""对象操作测试

TDD 测试覆盖 ObjectOperations 的所有公开方法
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.config.minio import MinIOConfig
from src.infrastructure.storage.minio.object_operations import (
    ObjectOperations,
    calculate_part_size,
)


class TestCalculatePartSize:
    """分片大小计算测试"""

    def test_small_file_no_multipart(self):
        """小文件不分片"""
        assert calculate_part_size(50 * 1024 * 1024) == 0

    def test_medium_file_10mb_parts(self):
        """中等文件 10MB 分片"""
        assert calculate_part_size(500 * 1024 * 1024) == 10 * 1024 * 1024

    def test_large_file_50mb_parts(self):
        """大文件 50MB 分片"""
        assert calculate_part_size(5 * 1024 * 1024 * 1024) == 50 * 1024 * 1024

    def test_xlarge_file_100mb_parts(self):
        """超大文件 100MB 分片"""
        assert calculate_part_size(50 * 1024 * 1024 * 1024) == 100 * 1024 * 1024

    def test_boundary_100mb(self):
        """100MB 边界"""
        size = 100 * 1024 * 1024
        # >= 100MB 需要分片
        assert calculate_part_size(size) == 10 * 1024 * 1024


class TestUploadObject:
    """上传对象测试"""

    def test_single_upload_small_file(self):
        """小文件单文件上传"""
        config = MinIOConfig()
        ops = ObjectOperations(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.version_id = "v1-abc123"
        mock_client.fput_object.return_value = mock_result
        mock_adapter.client = mock_client
        ops._adapter = mock_adapter

        with patch("os.path.getsize", return_value=50 * 1024 * 1024):
            result = ops.upload_object(
                "sisys-raw-docs-tenant1",
                "test/file.pdf",
                "/tmp/file.pdf",  # nosec B108
                "application/pdf",
            )

        assert result == "v1-abc123"
        mock_client.fput_object.assert_called_once()

    def test_multipart_upload_large_file(self):
        """大文件分片上传"""
        config = MinIOConfig()
        ops = ObjectOperations(config)

        with (
            patch("os.path.getsize", return_value=500 * 1024 * 1024),
            patch.object(ops, "_multipart_upload", return_value="v1-xyz789") as mock_mp,
        ):
            result = ops.upload_object(
                "sisys-raw-docs-tenant1",
                "test/large-file.zip",
                "/tmp/large-file.zip",  # nosec B108
                "application/zip",
            )

        assert result == "v1-xyz789"
        mock_mp.assert_called_once()


class TestDownloadObject:
    """下载对象测试"""

    async def test_download_object_streaming(self):
        """流式下载对象"""
        config = MinIOConfig()
        ops = ObjectOperations(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.read.side_effect = [b"chunk1", b"chunk2", b""]
        mock_response.close = MagicMock()
        mock_response.release_conn = MagicMock()
        mock_client.get_object.return_value = mock_response
        mock_adapter.client = mock_client
        ops._adapter = mock_adapter

        chunks = []
        async for chunk in ops.download_object("sisys-raw-docs-tenant1", "test/file.pdf"):
            chunks.append(chunk)

        assert chunks == [b"chunk1", b"chunk2"]
        mock_response.close.assert_called_once()

    async def test_download_object_with_version(self):
        """带版本 ID 下载"""
        config = MinIOConfig()
        ops = ObjectOperations(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.read.return_value = b""
        mock_response.close = MagicMock()
        mock_response.release_conn = MagicMock()
        mock_client.get_object.return_value = mock_response
        mock_adapter.client = mock_client
        ops._adapter = mock_adapter

        async for _ in ops.download_object("sisys-raw-docs-tenant1", "test/file.pdf", version_id="v1-abc"):
            pass

        mock_client.get_object.assert_called_once_with("sisys-raw-docs-tenant1", "test/file.pdf", version_id="v1-abc")


class TestGetObjectMetadata:
    """获取对象元数据测试"""

    def test_get_metadata(self):
        """获取对象元数据"""
        from datetime import UTC, datetime

        config = MinIOConfig()
        ops = ObjectOperations(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_stat = MagicMock()
        mock_stat.size = 1024
        mock_stat.etag = "abc123"
        mock_stat.content_type = "application/pdf"
        mock_stat.last_modified = datetime.now(UTC)
        mock_stat.version_id = "v1-abc"
        mock_client.stat_object.return_value = mock_stat
        mock_adapter.client = mock_client
        ops._adapter = mock_adapter

        result = ops.get_object_metadata("sisys-raw-docs-tenant1", "test/file.pdf")

        assert result["size"] == 1024
        assert result["etag"] == "abc123"
        assert result["content_type"] == "application/pdf"
        assert result["version_id"] == "v1-abc"


class TestDeleteObject:
    """删除对象测试"""

    def test_delete_object_success(self):
        """成功删除对象"""
        config = MinIOConfig()
        ops = ObjectOperations(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_adapter.client = mock_client
        ops._adapter = mock_adapter

        result = ops.delete_object("sisys-raw-docs-tenant1", "test/file.pdf")

        assert result is True
        mock_client.remove_object.assert_called_once()

    def test_delete_object_not_exists(self):
        """对象不存在返回 False"""
        from minio.error import S3Error

        config = MinIOConfig()
        ops = ObjectOperations(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_client.remove_object.side_effect = S3Error(
            code="NoSuchKey",
            message="No such key",
            resource="",
            request_id="",
            host_id="",
            response=MagicMock(),
        )
        mock_adapter.client = mock_client
        ops._adapter = mock_adapter

        result = ops.delete_object("sisys-raw-docs-tenant1", "test/file.pdf")
        assert result is False


class TestResumeMultipartUpload:
    """恢复分片上传测试"""

    async def test_resume_multipart_upload(self):
        """恢复分片上传 - all parts already uploaded, completes immediately."""
        from unittest.mock import mock_open

        config = MinIOConfig()
        ops = ObjectOperations(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_adapter.client = mock_client
        ops._adapter = mock_adapter

        mock_redis = AsyncMock()
        # State where both parts are already uploaded - should complete immediately
        state = {
            "upload_id": "upload-123",
            "file_path": "/tmp/file.pdf",  # nosec B108
            "content_type": "application/pdf",
            "part_size": 10 * 1024 * 1024,
            "uploaded_parts": [
                {"PartNumber": 1, "ETag": "etag-1"},
                {"PartNumber": 2, "ETag": "etag-2"},
            ],
        }
        mock_redis.get.return_value = json.dumps(state)

        # Mock open to return empty data (file already fully uploaded)
        mock_file = mock_open(read_data=b"")
        with patch("builtins.open", mock_file):
            await ops.resume_multipart_upload(
                "sisys-raw-docs-tenant1",
                "test/file.pdf",
                "upload-123",
                mock_redis,
            )

        # Verify _complete_multipart_upload was called
        mock_client._complete_multipart_upload.assert_called_once()
        # Verify Redis state was cleaned
        mock_redis.delete.assert_called_once()

    async def test_resume_multipart_no_state_raises(self):
        """无状态抛出 KeyError"""
        config = MinIOConfig()
        ops = ObjectOperations(config)
        mock_adapter = MagicMock()
        ops._adapter = mock_adapter

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        with pytest.raises(KeyError, match="No multipart upload state"):
            await ops.resume_multipart_upload(
                "sisys-raw-docs-tenant1",
                "test/file.pdf",
                "upload-nonexistent",
                mock_redis,
            )


class TestSaveMultipartState:
    """保存分片状态测试"""

    async def test_save_multipart_state(self):
        """保存分片上传状态到 Redis"""
        config = MinIOConfig()
        ops = ObjectOperations(config)
        mock_adapter = MagicMock()
        ops._adapter = mock_adapter

        mock_redis = AsyncMock()

        await ops.save_multipart_state(
            "upload-123",
            "/tmp/file.pdf",  # nosec B108
            "application/pdf",
            10 * 1024 * 1024,
            mock_redis,
        )

        mock_redis.set.assert_awaited_once()
        call_args = mock_redis.set.call_args
        key = call_args[0][0]
        value = json.loads(call_args[0][1])
        assert key == "minio:multipart:upload-123"
        assert value["file_path"] == "/tmp/file.pdf"  # nosec B108
        assert value["part_size"] == 10 * 1024 * 1024
