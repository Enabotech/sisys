"""Bucket 管理器测试

TDD 测试覆盖 BucketManager 的所有公开方法
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from src.infrastructure.config.minio import MinIOConfig
from src.infrastructure.storage.minio.bucket_manager import (
    BucketManager,
    BucketNameValidationError,
)


class TestValidateBucketName:
    """Bucket 命名验证测试。"""

    def test_valid_bucket_name(self):
        """有效的 Bucket 名称。"""
        manager = BucketManager(MinIOConfig(bucket_prefix="sisys"))
        assert manager.validate_bucket_name("sisys-raw-documents-tenant1") is True

    def test_valid_bucket_name_with_numbers(self):
        """包含数字的有效名称。"""
        manager = BucketManager(MinIOConfig(bucket_prefix="sisys"))
        assert manager.validate_bucket_name("sisys-audit-logs-tenant-123") is True

    def test_empty_bucket_name_raises(self):
        """空名称抛出异常。"""
        manager = BucketManager(MinIOConfig())
        with pytest.raises(BucketNameValidationError, match="cannot be empty"):
            manager.validate_bucket_name("")

    def test_name_without_hyphens_raises(self):
        """缺少连字符的名称抛出异常。"""
        manager = BucketManager(MinIOConfig())
        with pytest.raises(BucketNameValidationError, match="at least 3 parts"):
            manager.validate_bucket_name("simplebucket")

    def test_name_with_uppercase_raises(self):
        """大写字母名称抛出异常。"""
        manager = BucketManager(MinIOConfig())
        with pytest.raises(BucketNameValidationError):
            manager.validate_bucket_name("Sisys-Raw-Documents")

    def test_name_with_special_chars_raises(self):
        """特殊字符名称抛出异常。"""
        manager = BucketManager(MinIOConfig())
        with pytest.raises(BucketNameValidationError):
            manager.validate_bucket_name("sisys_raw_documents_tenant1")


class TestBuildBucketName:
    """Bucket 名称构建测试。"""

    def test_build_bucket_name(self):
        """构建标准 Bucket 名称。"""
        config = MinIOConfig(bucket_prefix="sisys")
        manager = BucketManager(config)
        result = manager.build_bucket_name("raw-documents", "tenant1")
        assert result == "sisys-raw-documents-tenant1"

    def test_build_bucket_name_with_custom_prefix(self):
        """自定义前缀构建。"""
        config = MinIOConfig(bucket_prefix="myapp")
        manager = BucketManager(config)
        result = manager.build_bucket_name("audit-logs", "acme")
        assert result == "myapp-audit-logs-acme"

    def test_build_bucket_name_invalid_type_raises(self):
        """非法 bucket_type 抛出异常。"""
        config = MinIOConfig(bucket_prefix="sisys")
        manager = BucketManager(config)
        with pytest.raises(BucketNameValidationError):
            manager.build_bucket_name("RAW DOCUMENTS", "tenant1")


class TestCreateBucket:
    """Bucket 创建测试。"""

    def test_create_bucket_success(self):
        """成功创建 Bucket。"""
        config = MinIOConfig()
        manager = BucketManager(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_adapter.client = mock_client
        manager._adapter = mock_adapter

        result = manager.create_bucket("sisys-raw-docs-tenant1")

        assert result is True
        mock_client.make_bucket.assert_called_once_with("sisys-raw-docs-tenant1", object_lock=False)

    def test_create_bucket_with_versioning(self):
        """创建 Bucket 并启用版本控制。"""
        config = MinIOConfig()
        manager = BucketManager(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_adapter.client = mock_client
        manager._adapter = mock_adapter

        result = manager.create_bucket("sisys-raw-docs-tenant1", enable_versioning=True)

        assert result is True
        mock_client.make_bucket.assert_called_once()
        mock_client.set_bucket_versioning.assert_called_once()
        # 验证传入了 VersioningConfig 对象
        call_args = mock_client.set_bucket_versioning.call_args[0]
        assert call_args[0] == "sisys-raw-docs-tenant1"
        assert call_args[1].status == "Enabled"

    def test_create_bucket_with_object_lock(self):
        """创建 Bucket 并启用对象锁定。"""
        config = MinIOConfig()
        manager = BucketManager(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_adapter.client = mock_client
        manager._adapter = mock_adapter

        result = manager.create_bucket("sisys-raw-docs-tenant1", enable_object_lock=True)

        assert result is True
        mock_client.make_bucket.assert_called_once_with("sisys-raw-docs-tenant1", object_lock=True)

    def test_create_bucket_already_exists(self):
        """Bucket 已存在返回 False。"""
        from minio.error import S3Error

        config = MinIOConfig()
        manager = BucketManager(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_adapter.client = mock_client
        mock_adapter._map_error.return_value = S3Error(
            code="BucketAlreadyExists",
            message="Bucket already exists",
            resource="/sisys-raw-docs-tenant1",
            request_id="req-1",
            host_id="host-1",
            response=MagicMock(),
        )
        mock_client.make_bucket.side_effect = S3Error(
            code="BucketAlreadyExists",
            message="Bucket already exists",
            resource="/sisys-raw-docs-tenant1",
            request_id="req-1",
            host_id="host-1",
            response=MagicMock(),
        )
        manager._adapter = mock_adapter

        result = manager.create_bucket("sisys-raw-docs-tenant1")
        assert result is False


class TestEnableObjectLock:
    """对象锁定启用测试。"""

    def test_enable_object_lock_success(self):
        """成功启用对象锁定。"""
        config = MinIOConfig()
        manager = BucketManager(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_adapter.client = mock_client
        manager._adapter = mock_adapter

        result = manager.enable_object_lock("sisys-raw-docs-tenant1")

        assert result is True
        mock_client.set_object_lock_config.assert_called_once()

    def test_enable_object_lock_custom_retention(self):
        """自定义保留天数。"""
        config = MinIOConfig()
        manager = BucketManager(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_adapter.client = mock_client
        manager._adapter = mock_adapter

        result = manager.enable_object_lock("sisys-raw-docs-tenant1", retention_days=365)

        assert result is True
        call_args = mock_client.set_object_lock_config.call_args
        assert call_args[0][0] == "sisys-raw-docs-tenant1"
        # 验证 ObjectLockConfig 对象
        config_arg = call_args[0][1]
        assert config_arg.mode == "GOVERNANCE"
        assert config_arg.duration == 365
        assert config_arg.duration_unit == "Days"


class TestDeleteBucket:
    """Bucket 删除测试。"""

    def test_delete_bucket_success(self):
        """成功删除 Bucket。"""
        config = MinIOConfig()
        manager = BucketManager(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_adapter.client = mock_client
        manager._adapter = mock_adapter

        result = manager.delete_bucket("sisys-raw-docs-tenant1")

        assert result is True
        mock_client.remove_bucket.assert_called_once_with("sisys-raw-docs-tenant1")

    def test_delete_bucket_force(self):
        """强制删除 Bucket（先清空对象）。"""
        config = MinIOConfig()
        manager = BucketManager(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_adapter.client = mock_client
        mock_obj = MagicMock()
        mock_obj.object_name = "test-file.pdf"
        mock_client.list_objects.return_value = [mock_obj]
        manager._adapter = mock_adapter

        result = manager.delete_bucket("sisys-raw-docs-tenant1", force=True)

        assert result is True
        mock_client.list_objects.assert_called_once()
        mock_client.remove_object.assert_called_once()
        mock_client.remove_bucket.assert_called_once()

    def test_delete_bucket_not_exists(self):
        """Bucket 不存在返回 False。"""
        from minio.error import S3Error

        config = MinIOConfig()
        manager = BucketManager(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_adapter.client = mock_client
        mock_client.remove_bucket.side_effect = S3Error(
            code="NoSuchBucket",
            message="No such bucket",
            resource="",
            request_id="",
            host_id="",
            response=MagicMock(),
        )
        manager._adapter = mock_adapter

        result = manager.delete_bucket("sisys-raw-docs-tenant1")
        assert result is False


class TestBucketExists:
    """Bucket 存在性检查测试。"""

    def test_bucket_exists_true(self):
        """Bucket 存在。"""
        config = MinIOConfig()
        manager = BucketManager(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.name = "sisys-raw-docs-tenant1"
        mock_bucket.creation_date = datetime.now(UTC)
        mock_client.list_buckets.return_value = [mock_bucket]
        mock_adapter.client = mock_client
        manager._adapter = mock_adapter

        result = manager.bucket_exists("sisys-raw-docs-tenant1")
        assert result is True

    def test_bucket_exists_false(self):
        """Bucket 不存在。"""
        config = MinIOConfig()
        manager = BucketManager(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_client.list_buckets.return_value = []
        mock_adapter.client = mock_client
        manager._adapter = mock_adapter

        result = manager.bucket_exists("sisys-raw-docs-tenant1")
        assert result is False


class TestListBuckets:
    """列出 Bucket 测试。"""

    def test_list_buckets(self):
        """列出所有 Bucket。"""
        config = MinIOConfig()
        manager = BucketManager(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        now = datetime.now(UTC)
        mock_b1 = MagicMock()
        mock_b1.name = "sisys-raw-docs-tenant1"
        mock_b1.creation_date = now
        mock_b2 = MagicMock()
        mock_b2.name = "sisys-audit-logs-tenant1"
        mock_b2.creation_date = now
        mock_client.list_buckets.return_value = [mock_b1, mock_b2]
        mock_adapter.client = mock_client
        manager._adapter = mock_adapter

        result = manager.list_buckets()

        assert len(result) == 2
        assert result[0]["name"] == "sisys-raw-docs-tenant1"
        assert result[1]["name"] == "sisys-audit-logs-tenant1"
