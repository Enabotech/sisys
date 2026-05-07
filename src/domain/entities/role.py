"""Role 领域实体.

遵循六边形架构：领域层零依赖，仅使用标准库。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Role:
    """角色领域实体（不可变）.

    属性:
        id: 角色 UUID
        name: 角色名称（唯一，如 "admin", "analyst", "viewer"）
        description: 角色描述
        permissions: 权限元组（如 ("document:read", "document:write")）
        is_system_reserved: 是否为系统保留角色（不可删除）
        is_active: 角色是否激活
        created_at: 角色创建时间
        updated_at: 角色最后更新时间
    """

    id: UUID | None = None  # None 表示新建角色（未保存）
    name: str = ""
    description: str = ""
    permissions: tuple[str, ...] = ()
    is_system_reserved: bool = False
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def has_permission(self, permission: str) -> bool:
        """检查角色是否拥有指定权限."""
        # 支持通配符：system:* 匹配所有 system:xxx 权限
        if permission in self.permissions:
            return True
        resource = permission.split(":")[0] if ":" in permission else ""
        action = permission.split(":")[1] if ":" in permission else "*"
        for p in self.permissions:
            if p == "*:*":
                return True
            if ":" in p:
                p_resource, p_action = p.split(":", 1)
                if (p_resource == "*" or p_resource == resource) and (p_action == "*" or p_action == action):
                    return True
        return False
