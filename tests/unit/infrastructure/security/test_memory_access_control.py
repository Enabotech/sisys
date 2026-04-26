"""Tests for MemoryAccessControl.

RED PHASE: 验证 MemoryAccessControl RBAC 校验功能。
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from src.infrastructure.security.memory_access_control import (
    MemoryAccessControl,
    MemoryAccessDeniedError,
)


class TestMemoryAccessControlPrivate:
    """MemoryAccessControl Private 记忆校验验证"""

    def test_private_read_allowed_for_owner(self):
        """验证 Private 记忆所有者可以读取"""
        control = MemoryAccessControl()
        user_id = str(uuid.uuid4())
        memory_id = str(uuid.uuid4())

        # 不应抛出异常
        control.check_read_access(user_id, memory_id, owner_id=user_id, is_group=False)

    def test_private_read_denied_for_non_owner(self):
        """验证 Private 记忆非所有者读取被拒绝"""
        control = MemoryAccessControl()
        owner_id = str(uuid.uuid4())
        other_user_id = str(uuid.uuid4())
        memory_id = str(uuid.uuid4())

        with pytest.raises(MemoryAccessDeniedError) as exc_info:
            control.check_read_access(other_user_id, memory_id, owner_id=owner_id, is_group=False)

        assert exc_info.value.reason == "not_owner"
        assert exc_info.value.action == "read"

    def test_private_write_allowed_for_owner(self):
        """验证 Private 记忆所有者可以写入"""
        control = MemoryAccessControl()
        user_id = str(uuid.uuid4())
        memory_id = str(uuid.uuid4())

        # 不应抛出异常
        control.check_write_access(user_id, memory_id, owner_id=user_id, is_group=False)

    def test_private_write_denied_for_non_owner(self):
        """验证 Private 记忆非所有者写入被拒绝"""
        control = MemoryAccessControl()
        owner_id = str(uuid.uuid4())
        other_user_id = str(uuid.uuid4())
        memory_id = str(uuid.uuid4())

        with pytest.raises(MemoryAccessDeniedError) as exc_info:
            control.check_write_access(other_user_id, memory_id, owner_id=owner_id, is_group=False)

        assert exc_info.value.reason == "not_owner"
        assert exc_info.value.action == "write"


class TestMemoryAccessControlGroup:
    """MemoryAccessControl Group 记忆校验验证"""

    def test_group_read_allowed_for_member(self):
        """验证 Group 记忆成员可以读取"""
        control = MemoryAccessControl()
        user_id = str(uuid.uuid4())
        group_id = str(uuid.uuid4())
        memory_id = str(uuid.uuid4())

        # Mock role_service 返回 True (是组成员)
        control._role_service = MagicMock()
        control._role_service.is_group_member.return_value = True

        # 不应抛出异常
        control.check_read_access(user_id, memory_id, owner_id=user_id, is_group=True, group_id=group_id)

    def test_group_read_denied_for_non_member(self):
        """验证 Group 记忆非成员读取被拒绝"""
        control = MemoryAccessControl()
        user_id = str(uuid.uuid4())
        group_id = str(uuid.uuid4())
        memory_id = str(uuid.uuid4())

        # Mock role_service 返回 False (不是组成员)
        control._role_service = MagicMock()
        control._role_service.is_group_member.return_value = False

        with pytest.raises(MemoryAccessDeniedError) as exc_info:
            control.check_read_access(user_id, memory_id, owner_id=user_id, is_group=True, group_id=group_id)

        assert exc_info.value.reason == "not_group_member"
        assert exc_info.value.action == "read"

    def test_group_write_allowed_for_admin(self):
        """验证 Group 记忆管理员可以写入"""
        control = MemoryAccessControl()
        user_id = str(uuid.uuid4())
        group_id = str(uuid.uuid4())
        memory_id = str(uuid.uuid4())

        # Mock role_service 返回 True (是组成员且是管理员)
        control._role_service = MagicMock()
        control._role_service.is_group_member.return_value = True
        control._role_service.is_group_admin.return_value = True

        # 不应抛出异常
        control.check_write_access(user_id, memory_id, owner_id=user_id, is_group=True, group_id=group_id)

    def test_group_write_denied_for_non_member(self):
        """验证 Group 记忆非成员写入被拒绝"""
        control = MemoryAccessControl()
        user_id = str(uuid.uuid4())
        group_id = str(uuid.uuid4())
        memory_id = str(uuid.uuid4())

        # Mock role_service 返回 False (不是组成员)
        control._role_service = MagicMock()
        control._role_service.is_group_member.return_value = False

        with pytest.raises(MemoryAccessDeniedError) as exc_info:
            control.check_write_access(user_id, memory_id, owner_id=user_id, is_group=True, group_id=group_id)

        assert exc_info.value.reason == "not_group_member"
        assert exc_info.value.action == "write"

    def test_group_write_denied_for_member_non_admin(self):
        """验证 Group 记忆普通成员写入被拒绝（需要管理员权限）"""
        control = MemoryAccessControl()
        user_id = str(uuid.uuid4())
        group_id = str(uuid.uuid4())
        memory_id = str(uuid.uuid4())

        # Mock role_service 返回 True (是组成员但不是管理员)
        control._role_service = MagicMock()
        control._role_service.is_group_member.return_value = True
        control._role_service.is_group_admin.return_value = False

        with pytest.raises(MemoryAccessDeniedError) as exc_info:
            control.check_write_access(user_id, memory_id, owner_id=user_id, is_group=True, group_id=group_id)

        assert exc_info.value.reason == "not_admin"
        assert exc_info.value.action == "write"


class TestMemoryAccessDeniedError:
    """MemoryAccessDeniedError 异常验证"""

    def test_exception_attributes(self):
        """验证异常属性正确"""
        user_id = "user-123"
        memory_id = "memory-456"
        action = "read"
        reason = "not_owner"

        error = MemoryAccessDeniedError(user_id, memory_id, action, reason)

        assert error.user_id == user_id
        assert error.memory_id == memory_id
        assert error.action == action
        assert error.reason == reason

    def test_exception_string_representation(self):
        """验证异常字符串表示"""
        user_id = "user-123"
        memory_id = "memory-456"
        action = "read"
        reason = "not_owner"

        error = MemoryAccessDeniedError(user_id, memory_id, action, reason)
        error_str = str(error)

        assert user_id in error_str
        assert memory_id in error_str
        assert action in error_str
        assert reason in error_str
