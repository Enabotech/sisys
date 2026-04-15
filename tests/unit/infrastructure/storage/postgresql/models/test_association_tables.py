"""Association tables TDD tests — Red phase."""

from __future__ import annotations

from sqlalchemy import ForeignKey

from src.infrastructure.storage.postgresql.models.association import (
    role_permissions_table,
    user_roles_table,
)


class TestUserRolesAssociation:
    """user_roles association table tests."""

    def test_table_name(self):
        """Table name should be 'user_roles'."""
        assert user_roles_table.name == "user_roles"

    def test_has_user_id_column(self):
        """Should have user_id column as FK to users.id."""
        columns = {c.name: c for c in user_roles_table.columns}
        assert "user_id" in columns
        assert any(isinstance(fk, ForeignKey) and "users" in str(fk.column.table) for fk in columns["user_id"].foreign_keys)

    def test_has_role_id_column(self):
        """Should have role_id column as FK to roles.id."""
        columns = {c.name: c for c in user_roles_table.columns}
        assert "role_id" in columns
        assert any(isinstance(fk, ForeignKey) and "roles" in str(fk.column.table) for fk in columns["role_id"].foreign_keys)

    def test_composite_primary_key(self):
        """Should have composite primary key (user_id, role_id)."""
        pk_columns = [c.name for c in user_roles_table.primary_key.columns]
        assert "user_id" in pk_columns
        assert "role_id" in pk_columns

    def test_cascade_delete(self):
        """FKs should have ondelete='CASCADE'."""
        columns = {c.name: c for c in user_roles_table.columns}
        for col_name in ("user_id", "role_id"):
            for fk in columns[col_name].foreign_keys:
                assert fk.ondelete == "CASCADE"


class TestRolePermissionsAssociation:
    """role_permissions association table tests."""

    def test_table_name(self):
        """Table name should be 'role_permissions'."""
        assert role_permissions_table.name == "role_permissions"

    def test_has_role_id_column(self):
        """Should have role_id column as FK to roles.id."""
        columns = {c.name: c for c in role_permissions_table.columns}
        assert "role_id" in columns
        assert any(isinstance(fk, ForeignKey) and "roles" in str(fk.column.table) for fk in columns["role_id"].foreign_keys)

    def test_has_permission_id_column(self):
        """Should have permission_id column as FK to permissions.id."""
        columns = {c.name: c for c in role_permissions_table.columns}
        assert "permission_id" in columns
        assert any(
            isinstance(fk, ForeignKey) and "permissions" in str(fk.column.table) for fk in columns["permission_id"].foreign_keys
        )

    def test_composite_primary_key(self):
        """Should have composite primary key (role_id, permission_id)."""
        pk_columns = [c.name for c in role_permissions_table.primary_key.columns]
        assert "role_id" in pk_columns
        assert "permission_id" in pk_columns

    def test_cascade_delete(self):
        """FKs should have ondelete='CASCADE'."""
        columns = {c.name: c for c in role_permissions_table.columns}
        for col_name in ("role_id", "permission_id"):
            for fk in columns[col_name].foreign_keys:
                assert fk.ondelete == "CASCADE"
