"""WORM 锁定与生命周期测试

TDD 测试覆盖 WORMManager 的所有公开方法
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from src.infrastructure.config.minio import MinIOConfig
from src.infrastructure.storage.minio.entities import LifecycleRule
from src.infrastructure.storage.minio.minio_manager import ComplianceLockError
from src.infrastructure.storage.minio.worm_lifecycle import (
    SOX_RETENTION_DAYS,
    WORMManager,
)


class TestEnableWormLock:
    """WORM 锁定启用测试"""

    def test_enable_worm_lock_success(self):
        """成功启用 WORM 锁定"""
        config = MinIOConfig()
        manager = WORMManager(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_adapter.client = mock_client
        manager._adapter = mock_adapter

        result = manager.enable_worm_lock("sisys-raw-docs-tenant1", "audit/report.pdf")

        assert result is True
        mock_client.set_object_retention.assert_called_once()
        call_args = mock_client.set_object_retention.call_args
        assert call_args[0][0] == "sisys-raw-docs-tenant1"
        assert call_args[0][1] == "audit/report.pdf"
        # 验证 Retention 对象
        retention = call_args[0][2]
        assert retention.mode == "GOVERNANCE"
        assert retention.retain_until_date > datetime.now(UTC)

    def test_enable_worm_lock_custom_retention(self):
        """自定义保留天数"""
        config = MinIOConfig()
        manager = WORMManager(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_adapter.client = mock_client
        manager._adapter = mock_adapter

        manager.enable_worm_lock("sisys-raw-docs-tenant1", "audit/report.pdf", retention_days=365)

        call_args = mock_client.set_object_retention.call_args
        retention = call_args[0][2]
        # 保留期应该在当前时间后约 365 天
        now = datetime.now(UTC)
        assert retention.retain_until_date > now + timedelta(days=360)
        assert retention.retain_until_date < now + timedelta(days=370)

    def test_enable_worm_lock_default_sox(self):
        """默认使用 SOX 保留天数"""
        assert SOX_RETENTION_DAYS == 2555


class TestArchiveObject:
    """对象归档测试"""

    def test_archive_object_success(self):
        """成功归档对象"""
        config = MinIOConfig()
        manager = WORMManager(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_adapter.client = mock_client
        manager._adapter = mock_adapter

        result = manager.archive_object("sisys-audit-archives-tenant1", "archive/2024/report.pdf")

        assert result is True
        mock_client.set_object_retention.assert_called_once()

    def test_archive_object_default_retention(self):
        """归档使用默认保留天数"""
        config = MinIOConfig()
        manager = WORMManager(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_adapter.client = mock_client
        manager._adapter = mock_adapter

        manager.archive_object("sisys-audit-archives-tenant1", "archive/2024/report.pdf")

        call_args = mock_client.set_object_retention.call_args
        retention = call_args[0][2]
        now = datetime.now(UTC)
        # 2555 天 = 7 年
        assert retention.retain_until_date > now + timedelta(days=2500)


class TestConfigureLifecycle:
    """生命周期配置测试"""

    def test_configure_lifecycle_success(self):
        """成功配置生命周期规则"""
        config = MinIOConfig()
        manager = WORMManager(config)

        rules = [
            LifecycleRule(
                rule_id="rule-1",
                status="Enabled",
                prefix="temp/",
                expiration_days=30,
            ),
            LifecycleRule(
                rule_id="rule-2",
                status="Enabled",
                prefix="archive/",
                transition_days=90,
                transition_storage_class="GLACIER",
            ),
        ]

        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_adapter.client = mock_client
        manager._adapter = mock_adapter

        result = manager.configure_lifecycle("sisys-raw-docs-tenant1", rules)

        assert result is True
        mock_client.set_bucket_lifecycle.assert_called_once()
        call_args = mock_client.set_bucket_lifecycle.call_args
        lifecycle_config = call_args[0][1]
        # 验证 LifecycleConfig 对象
        assert len(lifecycle_config.rules) == 2

    def test_configure_lifecycle_empty_rules(self):
        """配置空规则列表"""
        config = MinIOConfig()
        manager = WORMManager(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_adapter.client = mock_client
        manager._adapter = mock_adapter

        result = manager.configure_lifecycle("sisys-raw-docs-tenant1", [])

        assert result is True


class TestDeleteObjectWithWorm:
    """WORM 保护下删除对象测试"""

    def test_delete_object_success(self):
        """成功删除非锁定对象"""
        config = MinIOConfig()
        manager = WORMManager(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_adapter.client = mock_client
        manager._adapter = mock_adapter

        result = manager.delete_object("sisys-raw-docs-tenant1", "test/file.pdf")

        assert result is True
        mock_client.remove_object.assert_called_once()

    def test_delete_worm_locked_object_raises(self):
        """删除 WORM 锁定对象抛出 ComplianceLockError"""
        from minio.error import S3Error

        config = MinIOConfig()
        manager = WORMManager(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_client.remove_object.side_effect = S3Error(
            code="InvalidObjectState",
            message="Object is under WORM lock",
            resource="/sisys-raw-docs-tenant1/test/file.pdf",
            request_id="req-1",
            host_id="host-1",
            response=MagicMock(),
        )
        mock_adapter.client = mock_client
        manager._adapter = mock_adapter

        with pytest.raises(ComplianceLockError, match="WORM-locked"):
            manager.delete_object("sisys-raw-docs-tenant1", "test/file.pdf")

    def test_delete_object_not_exists(self):
        """对象不存在返回 False"""
        from minio.error import S3Error

        config = MinIOConfig()
        manager = WORMManager(config)
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
        manager._adapter = mock_adapter

        result = manager.delete_object("sisys-raw-docs-tenant1", "test/file.pdf")
        assert result is False

    def test_delete_object_invalid_state_raises(self):
        """InvalidObjectState 错误抛出 ComplianceLockError"""
        from minio.error import S3Error

        config = MinIOConfig()
        manager = WORMManager(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_client.remove_object.side_effect = S3Error(
            code="InvalidObjectState",
            message="Object is locked",
            resource="",
            request_id="",
            host_id="",
            response=MagicMock(),
        )
        mock_adapter.client = mock_client
        manager._adapter = mock_adapter

        with pytest.raises(ComplianceLockError):
            manager.delete_object("sisys-raw-docs-tenant1", "test/file.pdf")


class TestGetObjectRetention:
    """获取对象保留策略测试"""

    def test_get_object_retention(self):
        """获取对象保留策略"""
        config = MinIOConfig()
        manager = WORMManager(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_retention = MagicMock()
        mock_retention.mode = "GOVERNANCE"
        mock_retention.retain_until_date = datetime.now(UTC) + timedelta(days=2555)
        mock_client.get_object_retention.return_value = mock_retention
        mock_adapter.client = mock_client
        manager._adapter = mock_adapter

        result = manager.get_object_retention("sisys-raw-docs-tenant1", "test/file.pdf")

        assert result is not None
        assert result["mode"] == "GOVERNANCE"

    def test_get_object_retention_not_exists(self):
        """对象不存在返回 None"""
        from minio.error import S3Error

        config = MinIOConfig()
        manager = WORMManager(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_client.get_object_retention.side_effect = S3Error(
            code="NoSuchKey",
            message="No such key",
            resource="",
            request_id="",
            host_id="",
            response=MagicMock(),
        )
        mock_adapter.client = mock_client
        manager._adapter = mock_adapter

        result = manager.get_object_retention("sisys-raw-docs-tenant1", "test/file.pdf")
        assert result is None


class TestListLifecycleRules:
    """列出生命周期规则测试"""

    def test_list_lifecycle_rules(self):
        """列出生命周期规则"""
        from minio.lifecycleconfig import LifecycleConfig

        config = MinIOConfig()
        manager = WORMManager(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()

        # 创建 LifecycleConfig 对象
        mock_lifecycle = MagicMock(spec=LifecycleConfig)
        mock_lifecycle.rules = [
            MagicMock(id="rule-1", status="Enabled", rule_filter={}),
            MagicMock(id="rule-2", status="Disabled", rule_filter={}),
        ]
        mock_client.get_bucket_lifecycle.return_value = mock_lifecycle

        mock_adapter.client = mock_client
        manager._adapter = mock_adapter

        result = manager.list_lifecycle_rules("sisys-raw-docs-tenant1")

        assert len(result) == 2
        assert result[0]["ID"] == "rule-1"

    def test_list_lifecycle_rules_no_config(self):
        """无生命周期配置返回空列表"""
        from minio.error import S3Error

        config = MinIOConfig()
        manager = WORMManager(config)
        mock_adapter = MagicMock()
        mock_client = MagicMock()
        mock_client.get_bucket_lifecycle.side_effect = S3Error(
            code="NoSuchLifecycleConfiguration",
            message="No lifecycle configuration",
            resource="",
            request_id="",
            host_id="",
            response=MagicMock(),
        )
        mock_adapter.client = mock_client
        manager._adapter = mock_adapter

        result = manager.list_lifecycle_rules("sisys-raw-docs-tenant1")
        assert result == []
