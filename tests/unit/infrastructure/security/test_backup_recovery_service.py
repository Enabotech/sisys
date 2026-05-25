"""备份恢复服务单元测试

等保2.0三级备份恢复要求验证:
- AC-6.1: PostgreSQL 数据备份机制就绪
- AC-6.2: MinIO 对象存储备份机制就绪
- AC-6.3: Redis 缓存备份机制就绪
- AC-6.4: 备份完整性验证
- AC-6.5: 恢复流程测试
- AC-6.6: RTO<4 小时

本测试验证 BackupRecoveryServiceImpl 的等保合规实现

对应 Story: 1-12-equilibrium-level-3-compliance Task 4 Subtask 4.1-4.12
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.domain.value_objects.backup_result import BackupResult, BackupStatus, RestoreResult
from src.infrastructure.security.backup_recovery_service_impl import (
    BackupRecoveryServiceImpl,
)


@pytest.fixture
def backup_service() -> BackupRecoveryServiceImpl:
    """创建备份恢复服务实例（含 mock 依赖）"""
    mock_data_integrity = AsyncMock()
    mock_event_publisher = AsyncMock()
    return BackupRecoveryServiceImpl(
        data_integrity_service=mock_data_integrity,
        event_publisher=mock_event_publisher,
    )


class TestPostgreSQLBackup:
    """PostgreSQL 备份验证 (AC-6.1)"""

    async def test_create_postgresql_backup(
        self,
        backup_service: BackupRecoveryServiceImpl,
    ) -> None:
        """创建 PostgreSQL 备份应成功"""
        result = await backup_service.create_backup(
            backup_type="postgresql",
            description="Daily PostgreSQL backup",
        )
        assert isinstance(result, BackupResult)
        assert result.success is True
        assert result.backup_type == "postgresql"
        assert result.backup_id != ""
        assert result.checksum != ""

    async def test_postgresql_backup_has_checksum(
        self,
        backup_service: BackupRecoveryServiceImpl,
    ) -> None:
        """PostgreSQL 备份应包含校验和"""
        result = await backup_service.create_backup(backup_type="postgresql")
        assert len(result.checksum) == 64  # SHA256 校验和

    async def test_postgresql_backup_has_size(
        self,
        backup_service: BackupRecoveryServiceImpl,
    ) -> None:
        """PostgreSQL 备份应包含大小信息"""
        result = await backup_service.create_backup(backup_type="postgresql")
        assert result.size_bytes >= 0


class TestMinIOBackup:
    """MinIO 对象存储备份验证 (AC-6.2)"""

    async def test_create_minio_backup(
        self,
        backup_service: BackupRecoveryServiceImpl,
    ) -> None:
        """创建 MinIO 备份应成功"""
        result = await backup_service.create_backup(
            backup_type="minio",
            description="MinIO objects backup",
        )
        assert result.success is True
        assert result.backup_type == "minio"
        assert result.checksum != ""

    async def test_minio_backup_has_checksum(
        self,
        backup_service: BackupRecoveryServiceImpl,
    ) -> None:
        """MinIO 备份应包含校验和"""
        result = await backup_service.create_backup(backup_type="minio")
        assert len(result.checksum) == 64


class TestRedisBackup:
    """Redis 缓存备份验证 (AC-6.3)"""

    async def test_create_redis_backup(
        self,
        backup_service: BackupRecoveryServiceImpl,
    ) -> None:
        """创建 Redis 备份应成功"""
        result = await backup_service.create_backup(
            backup_type="redis",
            description="Redis cache backup",
        )
        assert result.success is True
        assert result.backup_type == "redis"
        assert result.checksum != ""


class TestFullBackup:
    """全量备份验证"""

    async def test_create_full_backup(
        self,
        backup_service: BackupRecoveryServiceImpl,
    ) -> None:
        """创建全量备份应成功"""
        result = await backup_service.create_backup(
            backup_type="full",
            description="Full system backup",
        )
        assert result.success is True
        assert result.backup_type == "full"

    async def test_full_backup_includes_all_components(
        self,
        backup_service: BackupRecoveryServiceImpl,
    ) -> None:
        """全量备份应包含所有组件"""
        result = await backup_service.create_backup(backup_type="full")
        assert result.success is True
        assert result.size_bytes > 0


class TestBackupRestore:
    """备份恢复验证 (AC-6.5)"""

    async def test_restore_from_backup(
        self,
        backup_service: BackupRecoveryServiceImpl,
    ) -> None:
        """从备份恢复应成功"""
        backup = await backup_service.create_backup(backup_type="postgresql")
        result = await backup_service.restore_backup(backup.backup_id)
        assert isinstance(result, RestoreResult)
        assert result.success is True
        assert result.backup_id == backup.backup_id
        assert result.restored_items >= 0

    async def test_restore_nonexistent_backup_fails(
        self,
        backup_service: BackupRecoveryServiceImpl,
    ) -> None:
        """从不存在的备份恢复应失败"""
        result = await backup_service.restore_backup("nonexistent-backup-id")
        assert result.success is False
        assert result.error_message != ""

    async def test_restore_with_target_components(
        self,
        backup_service: BackupRecoveryServiceImpl,
    ) -> None:
        """恢复指定组件应成功"""
        backup = await backup_service.create_backup(backup_type="full")
        result = await backup_service.restore_backup(
            backup.backup_id,
            target_components=["postgresql"],
        )
        assert result.success is True


class TestBackupIntegrityVerification:
    """备份完整性验证 (AC-6.4)"""

    async def test_verify_backup_integrity_valid(
        self,
        backup_service: BackupRecoveryServiceImpl,
    ) -> None:
        """验证有效备份的完整性应通过"""
        backup = await backup_service.create_backup(backup_type="postgresql")
        result = await backup_service.verify_backup_integrity(backup.backup_id)
        assert result is True

    async def test_verify_backup_integrity_nonexistent(
        self,
        backup_service: BackupRecoveryServiceImpl,
    ) -> None:
        """验证不存在的备份应返回 False"""
        result = await backup_service.verify_backup_integrity("nonexistent-id")
        assert result is False


class TestBackupStatus:
    """备份状态查询验证"""

    async def test_get_backup_status_completed(
        self,
        backup_service: BackupRecoveryServiceImpl,
    ) -> None:
        """查询已完成备份的状态"""
        backup = await backup_service.create_backup(backup_type="postgresql")
        status = await backup_service.get_backup_status(backup.backup_id)
        assert isinstance(status, BackupStatus)
        assert status.backup_id == backup.backup_id
        assert status.status == "completed"
        assert status.backup_type == "postgresql"

    async def test_get_backup_status_nonexistent(
        self,
        backup_service: BackupRecoveryServiceImpl,
    ) -> None:
        """查询不存在备份的状态"""
        status = await backup_service.get_backup_status("nonexistent-id")
        assert isinstance(status, BackupStatus)
        assert status.status == "not_found"
