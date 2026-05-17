"""Permission 领域实体.

遵循六边形架构：领域层零依赖，仅使用标准库。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Permission:
    """权限领域实体（不可变）.

    属性:
        id: 权限 UUID
        name: 权限名称（唯一，如 "document:read"）
        resource: 资源类型（如 "document"）
        action: 操作类型（如 "read"）
        created_at: 创建时间
    """

    id: UUID | None = None
    name: str = ""
    resource: str | None = None
    action: str | None = None
    created_at: datetime | None = None
