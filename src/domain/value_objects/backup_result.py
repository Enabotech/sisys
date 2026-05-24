"""领域层备份恢复结果值对象

定义备份恢复服务返回的结果类型，用于等保2.0三级备份恢复

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BackupType(str, Enum):
    """备份类型枚举"""

    POSTGRESQL = "postgresql"
    MINIO = "minio"
    REDIS = "redis"
    FULL = "full"


@dataclass(frozen=True)
class BackupResult:
    """备份操作结果

    Attributes:
        success: 备份是否成功
        backup_id: 备份唯一标识符
        backup_type: 备份类型
        size_bytes: 备份大小（字节）
        checksum: 备份校验和
        error_message: 错误信息
    """

    success: bool = False
    backup_id: str = ""
    backup_type: str = ""
    size_bytes: int = 0
    checksum: str = ""
    error_message: str = ""


@dataclass(frozen=True)
class RestoreResult:
    """恢复操作结果

    Attributes:
        success: 恢复是否成功
        backup_id: 源备份唯一标识符
        restored_items: 已恢复项数
        warnings: 警告信息列表
        error_message: 错误信息
    """

    success: bool = False
    backup_id: str = ""
    restored_items: int = 0
    warnings: list[str] = field(default_factory=list)
    error_message: str = ""


@dataclass(frozen=True)
class BackupStatus:
    """备份状态信息

    Attributes:
        backup_id: 备份唯一标识符
        status: 备份状态（pending/in_progress/completed/failed）
        backup_type: 备份类型
        size_bytes: 备份大小（字节）
        checksum: 备份校验和
    """

    backup_id: str = ""
    status: str = ""
    backup_type: str = ""
    size_bytes: int = 0
    checksum: str = ""
