"""PermissionModel TDD tests — Red phase."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import DeclarativeBase

from src.infrastructure.storage.postgresql.models.permission import PermissionModel


class TestPermissionModel:
    """PermissionModel tests (TDD red-green-refactor)."""

    def test_table_name(self):
        """Table name should be 'permissions'."""
        assert PermissionModel.__tablename__ == "permissions"

    def test_has_id_column(self):
        """Should have id column as UUID primary key."""
        columns = {c.name: c for c in PermissionModel.__table__.columns}
        assert "id" in columns
        assert columns["id"].primary_key

    def test_has_name_column(self):
        """Should have name column as String(50), unique."""
        columns = {c.name: c for c in PermissionModel.__table__.columns}
        assert "name" in columns
        assert columns["name"].unique

    def test_has_resource_column(self):
        """Should have resource column as String(50)."""
        columns = {c.name: c for c in PermissionModel.__table__.columns}
        assert "resource" in columns

    def test_has_action_column(self):
        """Should have action column as String(50)."""
        columns = {c.name: c for c in PermissionModel.__table__.columns}
        assert "action" in columns

    def test_has_created_at_column(self):
        """Should have created_at column as DateTime."""
        columns = {c.name: c for c in PermissionModel.__table__.columns}
        assert "created_at" in columns

    def test_can_instantiate(self):
        """Should be able to create a permission instance."""
        instance = PermissionModel(
            id=uuid4(),
            name="user.create",
            resource="user",
            action="create",
        )
        assert instance.name == "user.create"
        assert instance.resource == "user"
        assert instance.action == "create"

    def test_inherits_from_declarative_base(self):
        """PermissionModel should inherit from a DeclarativeBase."""
        assert issubclass(PermissionModel, DeclarativeBase) or hasattr(PermissionModel, "__mapper__")
