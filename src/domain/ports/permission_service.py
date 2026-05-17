"""领域层权限服务端口模块

领域层接口，定义权限检查的契约
遵循六边形架构：领域层零依赖，仅使用标准库

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class PermissionServicePort(Protocol):
    """权限服务端口（领域层定义，仅使用标准库）

    注意：角色分配/撤销是应用层 UseCase，不是领域层服务
    本接口仅负责权限检查，不包含角色管理逻辑
    """

    async def check_permission(self, user_id: UUID, resource: str, action: str, resource_id: UUID | None = None) -> bool:
        """检查用户权限

        Args:
            user_id: 用户 ID
            resource: 资源类型（如 "document", "agent", "plan"）
            action: 操作类型（如 "read", "write", "execute", "delete"）
            resource_id: 资源实例 ID（可选，用于实例级权限控制）

        Returns:
            True 如果有权限，False 否则
        """

    async def get_user_permissions(self, user_id: UUID) -> list[str]:
        """获取用户所有权限

        Args:
            user_id: 用户 ID

        Returns:
            权限字符串列表（如 ["document:read", "document:write", "agent:execute"]）
        """
