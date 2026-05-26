"""基础设施层权限服务模块

基于 PermissionServicePort 接口实现权限检查、角色分配和权限查询功能
"""

from __future__ import annotations

from uuid import UUID

from src.domain.ports.permission_service import PermissionServicePort
from src.domain.ports.role_repository import RoleRepositoryPort
from src.domain.ports.user_role_repository import UserRoleRepositoryPort


class PermissionServiceImpl(PermissionServicePort):
    """权限服务实现，负责权限检查和用户权限查询

    Attributes:
        _user_role_repo: 用户-角色关联仓储端口
        _role_repo: 角色仓储端口
        _event_publisher: 事件发布器（可选）
    """

    def __init__(
        self,
        user_role_repo: UserRoleRepositoryPort,
        role_repo: RoleRepositoryPort,
        event_publisher=None,  # EventPublisher (optional, for audit events)
    ):
        """初始化权限服务.

        Args:
            user_role_repo: 用户-角色关联仓储端口
            role_repo: 角色仓储端口
            event_publisher: 事件发布器（可选，用于审计事件）
        """
        self._user_role_repo = user_role_repo
        self._role_repo = role_repo
        self._event_publisher = event_publisher

    async def check_permission(
        self,
        user_id: UUID,
        resource: str,
        action: str,
        resource_id: UUID | None = None,
    ) -> bool:
        """检查用户是否拥有指定资源的操作权限.

        Args:
            user_id: 用户 ID
            resource: 资源类型（如 "document", "agent"）
            action: 操作类型（如 "read", "write", "execute"）
            resource_id: 资源实例 ID（可选，用于实例级权限控制）

        Returns:
            True 如果有权限，False 否则
        """
        roles = await self._user_role_repo.get_user_roles(user_id)
        for role in roles:
            if self._role_has_permission(role, resource, action):
                return True
        return False

    async def get_user_permissions(self, user_id: UUID) -> list[str]:
        """获取用户所有权限列表.

        Args:
            user_id: 用户 ID

        Returns:
            权限字符串列表（如 ["document:read", "document:write", "agent:execute"]）
        """
        roles = await self._user_role_repo.get_user_roles(user_id)
        permissions: set[str] = set()
        for role in roles:
            permissions.update(role.permissions)
        return list(permissions)

    def _role_has_permission(self, role, resource: str, action: str) -> bool:
        """检查角色是否拥有指定权限.

        Args:
            role: Role 领域实体
            resource: 资源类型
            action: 操作类型

        Returns:
            True 如果拥有权限，False 否则
        """
        for perm in role.permissions:
            if self._matches_permission(perm, resource, action):
                return True
        return False

    def _matches_permission(self, perm: str, resource: str, action: str) -> bool:
        """检查权限字符串是否匹配 resource:action.

        Args:
            perm: 权限字符串（如 "document:read", "*:*"）
            resource: 资源类型
            action: 操作类型

        Returns:
            True 如果匹配，False 否则
        """
        if perm == "*:*":
            return True
        if ":" in perm:
            perm_resource, perm_action = perm.split(":", 1)
            if perm_resource == resource and (perm_action == "*" or perm_action == action):
                return True
        return False

    async def assign_role(self, user_id: UUID, role_id: UUID, grant_actor: str) -> bool:
        """分配角色给用户

        Args:
            user_id: 用户 ID
            role_id: 角色 ID
            grant_actor: 授权操作者 ID

        Returns:
            True 如果成功
        """
        result = await self._user_role_repo.assign_role(user_id, role_id)

        # 发布审计事件 - 角色授予
        await self._publish_audit_event(
            action_type="authorization:grant",
            actor=grant_actor,
            target_resource=f"user/{user_id}/role/{role_id}",
            old_value={"user_id": str(user_id), "role_id": str(role_id)},
            new_value={"user_id": str(user_id), "role_id": str(role_id), "granted": result},
        )

        return result

    async def revoke_role(self, user_id: UUID, role_id: UUID, revoke_actor: str) -> bool:
        """撤销用户的角色

        Args:
            user_id: 用户 ID
            role_id: 角色 ID
            revoke_actor: 撤销操作者 ID

        Returns:
            True 如果成功
        """
        result = await self._user_role_repo.revoke_role(user_id, role_id)

        # 发布审计事件 - 角色撤销
        await self._publish_audit_event(
            action_type="authorization:revoke",
            actor=revoke_actor,
            target_resource=f"user/{user_id}/role/{role_id}",
            old_value={"user_id": str(user_id), "role_id": str(role_id), "revoked": result},
            new_value=None,
        )

        return result

    async def _publish_audit_event(
        self,
        action_type: str,
        actor: str,
        target_resource: str,
        old_value: dict | None = None,
        new_value: dict | None = None,
    ) -> None:
        """发布审计事件

        Args:
            action_type: 操作类型
            actor: 操作用户 ID
            target_resource: 目标资源
            old_value: 操作前状态
            new_value: 操作后状态
        """
        if self._event_publisher is None:
            return

        try:
            from src.domain.events.audit_events import AuditEvent

            event = AuditEvent(
                actor=actor,
                action_type=action_type,
                target_resource=target_resource,
                old_value=old_value or {},
                new_value=new_value or {},
            )
            await self._event_publisher.publish(event)
        except Exception:
            # 审计事件发布失败不应影响主流程
            pass
