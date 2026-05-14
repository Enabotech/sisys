"""UserRoleRepository Port - 用户-角色关联仓储端口.

领域层接口，定义用户-角色关联数据访问的契约。
遵循六边形架构：领域层零依赖，仅使用标准库。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from src.domain.entities.role import Role


@runtime_checkable
class UserRoleRepositoryPort(Protocol):
    """用户-角色关联仓储端口（领域层定义，仅使用标准库）

    负责用户和角色之间的关联关系。
    """

    async def assign_role(self, user_id: UUID, role_id: UUID) -> bool:
        """分配角色给用户。

        Args:
            user_id: 用户 UUID
            role_id: 角色 UUID

        Returns:
            True 分配成功，False 用户或角色不存在
        """

    async def revoke_role(self, user_id: UUID, role_id: UUID) -> bool:
        """撤销用户的角色。

        Args:
            user_id: 用户 UUID
            role_id: 角色 UUID

        Returns:
            True 撤销成功，False 关联不存在
        """

    async def get_user_roles(self, user_id: UUID) -> list[Role]:
        """获取用户的所有角色。

        Args:
            user_id: 用户 UUID

        Returns:
            Role 领域实体列表
        """

    async def get_role_users(self, role_id: UUID) -> list[UUID]:
        """获取拥有某角色的所有用户 ID。

        Args:
            role_id: 角色 UUID

        Returns:
            用户 UUID 列表
        """
