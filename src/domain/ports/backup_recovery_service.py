"""领域层备份恢复服务端口模块

定义备份恢复服务的抽象接口，遵循六边形架构端口协议
用于等保2.0三级备份恢复合规

设计原则：
- create_backup(): 创建备份（支持 PostgreSQL/MinIO/Redis/全量）
- restore_backup(): 恢复备份
- verify_backup_integrity(): 验证备份完整性
- get_backup_status(): 查询备份状态

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.value_objects.backup_result import (
    BackupResult,
    BackupStatus,
    RestoreResult,
)


@runtime_checkable
class BackupRecoveryServicePort(Protocol):
    """备份恢复服务抽象端口

    等保2.0三级备份恢复要求的核心服务端口，负责：
    - PostgreSQL/MinIO/Redis 数据备份
    - 备份恢复流程
    - 备份完整性验证
    - RTO < 4 小时达标验证

    实现类必须遵循此接口契约，确保端口的可替换性
    """

    async def create_backup(
        self,
        backup_type: str = "full",
        description: str = "",
    ) -> BackupResult:
        """创建数据备份

        Args:
            backup_type: 备份类型（postgresql/minio/redis/full）
            description: 备份描述

        Returns:
            BackupResult 包含备份结果、备份ID、校验和等
        """
        ...

    async def restore_backup(
        self,
        backup_id: str,
        target_components: list[str] | None = None,
    ) -> RestoreResult:
        """恢复指定备份

        Args:
            backup_id: 备份唯一标识符
            target_components: 目标恢复组件列表（可选）

        Returns:
            RestoreResult 包含恢复结果、已恢复项数、警告信息等
        """
        ...

    async def verify_backup_integrity(
        self,
        backup_id: str,
    ) -> bool:
        """验证备份完整性

        Args:
            backup_id: 备份唯一标识符

        Returns:
            True 表示备份完整性验证通过
        """
        ...

    async def get_backup_status(
        self,
        backup_id: str,
    ) -> BackupStatus:
        """查询备份状态

        Args:
            backup_id: 备份唯一标识符

        Returns:
            BackupStatus 包含备份状态、大小、校验和等
        """
        ...
