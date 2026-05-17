"""UserRoleRepository — 用户-角色关联仓储实现

实现 UserRoleRepositoryPort 端口，从 user_roles 关联表操作数据
遵循六边形架构：基础设施层实现，可以导入外部库

Session 来源：
- Session 通过 ContextVar 由 middleware 或 test fixture 提供
- 无需构造器注入 session 参数
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.role import Role
from src.domain.ports.user_role_repository import UserRoleRepositoryPort
from src.infrastructure.storage.postgresql.models import RoleModel, UserModel
from src.infrastructure.storage.postgresql.models.rbac_association import user_roles_table as user_roles
from src.infrastructure.storage.postgresql.session_context import get_session


class UserRoleRepository(UserRoleRepositoryPort):
    """用户-角色关联仓储实现

    负责用户和角色之间的关联关系，实现 UserRoleRepositoryPort 端口
    """

    @property
    def _session(self) -> AsyncSession:
        return get_session()

    async def assign_role(self, user_id: UUID, role_id: UUID) -> bool:
        """分配角色给用户

        Args:
            user_id: 用户 UUID
            role_id: 角色 UUID

        Returns:
            True 分配成功，False 用户或角色不存在
        """
        # 验证用户存在
        user = await self._session.get(UserModel, user_id)
        if not user:
            return False

        # 验证角色存在
        role = await self._session.get(RoleModel, role_id)
        if not role:
            return False

        # 插入关联记录
        await self._session.execute(user_roles.insert().values(user_id=user_id, role_id=role_id))
        await self._session.flush()
        return True

    async def revoke_role(self, user_id: UUID, role_id: UUID) -> bool:
        """撤销用户的角色

        Args:
            user_id: 用户 UUID
            role_id: 角色 UUID

        Returns:
            True 撤销成功，False 关联不存在
        """
        from typing import cast

        from sqlalchemy import delete
        from sqlalchemy.engine import CursorResult

        stmt = delete(user_roles).where(user_roles.c.user_id == user_id, user_roles.c.role_id == role_id)
        result = await self._session.execute(stmt)
        await self._session.flush()
        cursor_result = cast(CursorResult, result)
        return cursor_result.rowcount > 0

    async def get_user_roles(self, user_id: UUID) -> list["Role"]:
        """获取用户的所有角色

        Args:
            user_id: 用户 UUID

        Returns:
            Role 领域实体列表
        """
        from src.domain.entities.role import Role

        # 查询用户的角色 ID
        result = await self._session.execute(
            select(RoleModel).join(user_roles, RoleModel.id == user_roles.c.role_id).where(user_roles.c.user_id == user_id)
        )
        role_models = result.scalars().all()

        # 转换为领域实体
        roles = []
        for model in role_models:
            # 加载角色权限
            permissions = await self._get_permissions_for_role(model.id)
            role = Role(
                id=model.id,
                name=model.name,
                description=model.description or "",
                permissions=permissions,
                is_system_reserved=model.is_system_reserved,
                is_active=model.is_active,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            roles.append(role)
        return roles

    async def _get_permissions_for_role(self, role_id: UUID) -> tuple[str, ...]:
        """从关联表获取角色的权限字符串元组

        Args:
            role_id: 角色 UUID

        Returns:
            权限字符串元组
        """
        from src.infrastructure.storage.postgresql.models import PermissionModel
        from src.infrastructure.storage.postgresql.models.rbac_association import (
            role_permissions_table as role_permissions,
        )

        result = await self._session.execute(
            select(PermissionModel.name)
            .join(role_permissions, PermissionModel.id == role_permissions.c.permission_id)
            .where(role_permissions.c.role_id == role_id)
        )
        return tuple(r[0] for r in result.fetchall())

    async def get_role_users(self, role_id: UUID) -> list[UUID]:
        """获取拥有某角色的所有用户 ID

        Args:
            role_id: 角色 UUID

        Returns:
            用户 UUID 列表
        """
        result = await self._session.execute(
            select(UserModel.id).join(user_roles, UserModel.id == user_roles.c.user_id).where(user_roles.c.role_id == role_id)
        )
        return [row[0] for row in result.fetchall()]
