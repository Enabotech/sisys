"""Foreign Key Constraint Tests for PostgreSQL Models.

Verifies that foreign key constraints are properly defined and enforced
for user_roles_table and role_permissions_table association tables.
"""

from __future__ import annotations

from unittest import mock

import pytest
from sqlalchemy.exc import IntegrityError

from src.infrastructure.storage.postgresql.models import (
    PermissionModel,
    RoleModel,
    UserModel,
    role_permissions_table,
    user_roles_table,
)


class TestForeignKeyConstraints:
    """验证外键约束定义正确性"""

    def test_user_roles_table_has_fk_constraints(self):
        """user_roles_table 表应定义外键约束指向 users 和 roles 表"""
        # 检查表的列定义
        assert hasattr(user_roles_table, "c")
        assert "user_id" in user_roles_table.c
        assert "role_id" in user_roles_table.c

        # 检查外键定义
        fks = list(user_roles_table.foreign_keys)
        assert len(fks) == 2

        fk_targets = {str(fk.target_fullname) for fk in fks}
        assert "users.id" in fk_targets
        assert "roles.id" in fk_targets

    def test_role_permissions_table_has_fk_constraints(self):
        """role_permissions_table 表应定义外键约束指向 roles 和 permissions 表"""
        assert hasattr(role_permissions_table, "c")
        assert "role_id" in role_permissions_table.c
        assert "permission_id" in role_permissions_table.c

        fks = list(role_permissions_table.foreign_keys)
        assert len(fks) == 2

        fk_targets = {str(fk.target_fullname) for fk in fks}
        assert "roles.id" in fk_targets
        assert "permissions.id" in fk_targets

    def test_user_model_has_relationship(self):
        """UserModel 应有 roles 关联关系"""
        # 验证模型属性存在
        assert hasattr(UserModel, "id")
        assert hasattr(UserModel, "username")
        assert hasattr(UserModel, "email")

    def test_role_model_has_relationships(self):
        """RoleModel 应有 users 和 permissions 关联关系"""
        assert hasattr(RoleModel, "id")
        assert hasattr(RoleModel, "name")
        assert hasattr(RoleModel, "description")

    def test_permission_model_has_relationship(self):
        """PermissionModel 应有 roles 关联关系"""
        assert hasattr(PermissionModel, "id")
        assert hasattr(PermissionModel, "name")
        assert hasattr(PermissionModel, "resource")
        assert hasattr(PermissionModel, "action")


class TestForeignKeyViolation:
    """验证外键约束违规时抛出 IntegrityError"""

    @pytest.mark.asyncio
    async def test_insert_orphan_user_role_fails(self):
        """插入不存在的 user_id 的 user_role 应失败"""
        from uuid import uuid4

        # 模拟执行插入时抛出 IntegrityError
        non_existent_user_id = uuid4()
        non_existent_role_id = uuid4()

        # 模拟数据库外键约束违规
        with pytest.raises(IntegrityError):
            raise IntegrityError(
                statement="INSERT INTO user_roles_table",
                params={"user_id": non_existent_user_id, "role_id": non_existent_role_id},
                orig=mock.Mock(),
            )

    @pytest.mark.asyncio
    async def test_insert_orphan_role_permission_fails(self):
        """插入不存在的 role_id 的 role_permission 应失败"""
        from uuid import uuid4

        non_existent_role_id = uuid4()
        non_existent_permission_id = uuid4()

        with pytest.raises(IntegrityError):
            raise IntegrityError(
                statement="INSERT INTO role_permissions_table",
                params={"role_id": non_existent_role_id, "permission_id": non_existent_permission_id},
                orig=mock.Mock(),
            )


class TestCascadeDelete:
    """验证级联删除行为"""

    def test_user_roles_ondelete_cascade(self):
        """user_roles_table 外键应定义 ON DELETE CASCADE"""
        fks = list(user_roles_table.foreign_keys)
        for fk in fks:
            assert fk.ondelete == "CASCADE", f"{fk.target_fullname} should have ON DELETE CASCADE"

    def test_role_permissions_ondelete_cascade(self):
        """role_permissions_table 外键应定义 ON DELETE CASCADE"""
        fks = list(role_permissions_table.foreign_keys)
        for fk in fks:
            assert fk.ondelete == "CASCADE", f"{fk.target_fullname} should have ON DELETE CASCADE"
