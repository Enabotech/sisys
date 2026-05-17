"""SISYS 领域层权限仓储端口模块。

独立 Protocol（与 UserRepositoryPort、RoleRepositoryPort 模式一致）。
仓储通过 PostgreSQLAdapter 自动实现 L2RdbPort。

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from src.domain.entities.permission import Permission


@runtime_checkable
class PermissionRepositoryPort(Protocol):
    """权限仓储端口 — RBAC 子系统独立 Protocol."""

    async def get_by_name(self, name: str) -> Permission | None:
        """根据名称获取权限。

        Args:
            name: 权限名称

        Returns:
            Permission 实体，不存在则返回 None
        """

    async def get_by_id(self, id: UUID) -> Permission | None:
        """根据 ID 获取权限。

        Args:
            id: 权限 UUID

        Returns:
            Permission 实体，不存在则返回 None
        """

    async def save(self, permission: Permission) -> Permission:
        """保存权限（插入或更新）。

        Args:
            permission: Permission 实体

        Returns:
            持久化后的 Permission 实体
        """

    async def delete(self, id: UUID) -> None:
        """删除权限。

        Args:
            id: 权限 UUID
        """

    async def list_all(self) -> list[Permission]:
        """列出所有权限。

        Returns:
            Permission 实体列表
        """
