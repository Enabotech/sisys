"""MinIO 客户端适配器测试。

TDD 红→绿→重构循环 A + B。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from minio.error import S3Error

from src.infrastructure.config.minio import MinIOConfig
from src.infrastructure.storage.minio.client_adapter import (
    BucketNotFoundError,
    MinioClientAdapter,
    PermissionDeniedError,
)


class TestMinioClientAdapterInit:
    """MinioClientAdapter 初始化测试。"""

    def test_init_with_config(self):
        """使用配置对象初始化。"""
        config = MinIOConfig(
            endpoint="test.minio:9000",
            access_key="test-key",
            secret_key="test-secret",  # pragma: allowlist secret
            secure=True,
        )
        adapter = MinioClientAdapter(config)
        assert adapter._config.endpoint == "test.minio:9000"
        assert adapter._client is None

    def test_client_property_creates_once(self):
        """客户端属性创建一次。"""
        config = MinIOConfig(
            endpoint="test.minio:9000",
            access_key="key",
            secret_key="secret",  # pragma: allowlist secret
            secure=False,
        )
        adapter = MinioClientAdapter(config)

        with patch("src.infrastructure.storage.minio.client_adapter.Minio") as mock_minio:
            mock_client = MagicMock()
            mock_minio.return_value = mock_client

            client1 = adapter.client
            client2 = adapter.client

            assert client1 is client2
            mock_minio.assert_called_once()


class TestMinioClientAdapterConnection:
    """MinioClientAdapter 连接测试。"""

    def test_get_client_lazy_loading(self):
        """客户端懒加载。"""
        config = MinIOConfig()
        adapter = MinioClientAdapter(config)
        assert adapter._client is None

        with patch("src.infrastructure.storage.minio.client_adapter.Minio") as mock_minio:
            mock_client = MagicMock()
            mock_minio.return_value = mock_client

            client = adapter._get_client()
            assert client is not None
            mock_minio.assert_called_once()

    def test_get_client_reuses_existing(self):
        """客户端复用。"""
        config = MinIOConfig()
        adapter = MinioClientAdapter(config)
        adapter._client = MagicMock()

        client = adapter._get_client()
        assert client == adapter._client


class TestMinioClientAdapterErrorHandling:
    """MinioClientAdapter 错误处理测试。"""

    def test_map_s3_error_bucket_not_found(self):
        """映射桶不存在错误。"""
        error = S3Error(
            code="NoSuchBucket",
            message="Bucket not found",
            resource="/test-bucket",
            request_id="req-123",
            host_id="host-123",
            response=MagicMock(),
        )
        mapped = MinioClientAdapter._map_error(error)
        assert isinstance(mapped, BucketNotFoundError)

    def test_map_s3_error_permission_denied(self):
        """映射权限不足错误。"""
        error = S3Error(
            code="AccessDenied",
            message="Access denied",
            resource="/test-bucket",
            request_id="req-123",
            host_id="host-123",
            response=MagicMock(),
        )
        mapped = MinioClientAdapter._map_error(error)
        assert isinstance(mapped, PermissionDeniedError)

    def test_map_s3_error_forbidden(self):
        """映射 Forbidden 错误。"""
        error = S3Error(
            code="Forbidden",
            message="Forbidden",
            resource="/test-bucket",
            request_id="req-123",
            host_id="host-123",
            response=MagicMock(),
        )
        mapped = MinioClientAdapter._map_error(error)
        assert isinstance(mapped, PermissionDeniedError)

    def test_map_s3_error_unknown(self):
        """映射未知错误。"""
        error = S3Error(
            code="SomeUnknownError",
            message="Unknown",
            resource="/test-bucket",
            request_id="req-123",
            host_id="host-123",
            response=MagicMock(),
        )
        mapped = MinioClientAdapter._map_error(error)
        assert isinstance(mapped, S3Error)

    def test_health_check_success(self):
        """健康检查成功。"""
        config = MinIOConfig()
        adapter = MinioClientAdapter(config)
        adapter._client = MagicMock()
        adapter._client.list_buckets.return_value = []

        result = adapter.health_check()
        assert result is True

    def test_health_check_failure(self):
        """健康检查失败。"""
        config = MinIOConfig()
        adapter = MinioClientAdapter(config)
        adapter._client = MagicMock()
        adapter._client.list_buckets.side_effect = S3Error(
            code="ConnectionError",
            message="Cannot connect",
            resource="",
            request_id="",
            host_id="",
            response=MagicMock(),
        )

        result = adapter.health_check()
        assert result is False
