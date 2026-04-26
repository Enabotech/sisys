"""MemoryAccessControl — 记忆访问控制。

负责 Private/Group 记忆的 RBAC 校验。
- Private 记忆：owner == user_id
- Group 记忆：user_id 是 group 成员（读取）或 group 管理员（写入）

架构来源: architecture.md §11.2.3
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.services.role_service import RoleService


class MemoryAccessDeniedError(Exception):
    """记忆访问被拒绝异常。"""

    def __init__(self, user_id: str, memory_id: str, action: str, reason: str):
        """初始化异常。

        Args:
            user_id: 用户 ID
            memory_id: 记忆 ID
            action: 操作类型 ('read' | 'write')
            reason: 拒绝原因 ('not_owner' | 'not_group_member' | 'not_admin')
        """
        self.user_id = user_id
        self.memory_id = memory_id
        self.action = action
        self.reason = reason
        super().__init__(f"Access denied: user={user_id}, memory={memory_id}, action={action}, reason={reason}")


class MemoryAccessControl:
    """记忆访问控制器。

    负责 Private/Group 记忆的 RBAC 校验。
    """

    def __init__(self, role_service: RoleService | None = None):
        """初始化访问控制器。

        Args:
            role_service: 角色服务（用于 Group 记忆成员校验）
        """
        self._role_service = role_service

    def check_read_access(
        self,
        user_id: str,
        memory_id: str,
        owner_id: str,
        is_group: bool = False,
        group_id: str | None = None,
    ) -> None:
        """检查读取访问权限。

        Args:
            user_id: 用户 ID
            memory_id: 记忆 ID
            owner_id: 记忆所有者 ID
            is_group: 是否为 Group 记忆
            group_id: 群组 ID（Group 记忆时需要）

        Raises:
            MemoryAccessDeniedError: 访问被拒绝时
        """
        if is_group:
            self._check_group_read_access(user_id, memory_id, group_id)
        else:
            self._check_private_read_access(user_id, memory_id, owner_id)

    def check_write_access(
        self,
        user_id: str,
        memory_id: str,
        owner_id: str,
        is_group: bool = False,
        group_id: str | None = None,
    ) -> None:
        """检查写入访问权限。

        Args:
            user_id: 用户 ID
            memory_id: 记忆 ID
            owner_id: 记忆所有者 ID
            is_group: 是否为 Group 记忆
            group_id: 群组 ID（Group 记忆时需要）

        Raises:
            MemoryAccessDeniedError: 访问被拒绝时
        """
        if is_group:
            self._check_group_write_access(user_id, memory_id, group_id)
        else:
            self._check_private_write_access(user_id, memory_id, owner_id)

    def _check_private_read_access(self, user_id: str, memory_id: str, owner_id: str) -> None:
        """检查 Private 记忆读取权限。"""
        if user_id != owner_id:
            raise MemoryAccessDeniedError(user_id, memory_id, "read", "not_owner")

    def _check_private_write_access(self, user_id: str, memory_id: str, owner_id: str) -> None:
        """检查 Private 记忆写入权限。"""
        if user_id != owner_id:
            raise MemoryAccessDeniedError(user_id, memory_id, "write", "not_owner")

    def _check_group_read_access(self, user_id: str, memory_id: str, group_id: str | None) -> None:
        """检查 Group 记忆读取权限。"""
        if group_id is None:
            raise MemoryAccessDeniedError(user_id, memory_id, "read", "not_group_member")

        if self._role_service is None:
            raise MemoryAccessDeniedError(user_id, memory_id, "read", "not_group_member")

        if not self._role_service.is_group_member(user_id, group_id):
            raise MemoryAccessDeniedError(user_id, memory_id, "read", "not_group_member")

    def _check_group_write_access(self, user_id: str, memory_id: str, group_id: str | None) -> None:
        """检查 Group 记忆写入权限。"""
        if group_id is None:
            raise MemoryAccessDeniedError(user_id, memory_id, "write", "not_group_member")

        if self._role_service is None:
            raise MemoryAccessDeniedError(user_id, memory_id, "write", "not_group_member")

        # 必须是组成员
        if not self._role_service.is_group_member(user_id, group_id):
            raise MemoryAccessDeniedError(user_id, memory_id, "write", "not_group_member")

        # 写入需要管理员权限
        if not self._role_service.is_group_admin(user_id, group_id):
            raise MemoryAccessDeniedError(user_id, memory_id, "write", "not_admin")
