"""MinIO 客户端适配器测试。

TDD 红→绿→重构循环 A + B。
"""

from __future__ import annotations

from unittest.mock import MagicMock

from minio.error import S3Error

from src.domain.exceptions.external_exceptions import ThirdPartyError
from src.infrastructure.config.minio import MinIOConfig
from src.infrastructure.storage.minio.minio_manager import (
    BucketNotFoundError,
    MinioManager,
    PermissionDeniedError,
)


class TestMinioClientAdapterInit:
    """MinioManager 初始化测试。"""

    def test_init_with_client(self):
        """使用客户端实例初始化。"""
        mock_client = MagicMock()
        adapter = MinioManager(mock_client)
        assert adapter._client is mock_client

    def test_from_config(self):
        """从配置创建适配器。"""
        config = MinIOConfig(
            host="test.minio",
            port=9000,
            access_key="test-key",
            secret_key="test-secret",  # pragma: allowlist secret
            secure=True,
        )
        adapter = MinioManager.from_config(config)
        assert adapter._client is not None

    def test_client_property_returns_injected(self):
        """client 属性返回注入的实例。"""
        mock_client = MagicMock()
        adapter = MinioManager(mock_client)
        assert adapter.client is mock_client
        assert adapter.client is adapter.client


class TestMinioClientAdapterErrorHandling:
    """MinioManager 错误处理测试。"""

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
        mapped = MinioManager._map_error(error)
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
        mapped = MinioManager._map_error(error)
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
        mapped = MinioManager._map_error(error)
        assert isinstance(mapped, PermissionDeniedError)

    def test_map_s3_error_unknown(self):
        """映射未知错误 - 未知错误应转换为 ThirdPartyError。"""
        error = S3Error(
            code="SomeUnknownError",
            message="Unknown",
            resource="/test-bucket",
            request_id="req-123",
            host_id="host-123",
            response=MagicMock(),
        )
        mapped = MinioManager._map_error(error)
        assert isinstance(mapped, ThirdPartyError)

    def test_health_check_success(self):
        """健康检查成功。"""
        mock_client = MagicMock()
        mock_client.list_buckets.return_value = []
        adapter = MinioManager(mock_client)

        result = adapter.health_check()
        assert result is True

    def test_health_check_failure(self):
        """健康检查失败。"""
        mock_client = MagicMock()
        mock_client.list_buckets.side_effect = S3Error(
            code="ConnectionError",
            message="Cannot connect",
            resource="",
            request_id="",
            host_id="",
            response=MagicMock(),
        )
        adapter = MinioManager(mock_client)

        result = adapter.health_check()
        assert result is False
