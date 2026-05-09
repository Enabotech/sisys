"""RoleModel TDD tests — Red phase."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import DeclarativeBase

from src.infrastructure.storage.postgresql.models.role import RoleModel


class TestRoleModel:
    """RoleModel tests (TDD red-green-refactor)."""

    def test_table_name(self):
        """Table name should be 'roles'."""
        assert RoleModel.__tablename__ == "roles"

    def test_has_id_column(self):
        """Should have id column as UUID primary key."""
        columns = {c.name: c for c in RoleModel.__table__.columns}
        assert "id" in columns
        assert columns["id"].primary_key

    def test_has_name_column(self):
        """Should have name column as String(50), unique."""
        columns = {c.name: c for c in RoleModel.__table__.columns}
        assert "name" in columns
        assert columns["name"].unique

    def test_has_description_column(self):
        """Should have description column as String(200)."""
        columns = {c.name: c for c in RoleModel.__table__.columns}
        assert "description" in columns

    def test_has_created_at_column(self):
        """Should have created_at column as DateTime."""
        columns = {c.name: c for c in RoleModel.__table__.columns}
        assert "created_at" in columns

    def test_can_instantiate(self):
        """Should be able to create a role instance."""
        instance = RoleModel(
            id=uuid4(),
            name="admin",
            description="Administrator role",
        )
        assert instance.name == "admin"
        assert instance.description == "Administrator role"

    def test_inherits_from_declarative_base(self):
        """RoleModel should inherit from a DeclarativeBase."""
        assert issubclass(RoleModel, DeclarativeBase) or hasattr(RoleModel, "__mapper__")

    def test_has_is_active_column(self):
        """Should have is_active column with default True."""
        columns = {c.name: c for c in RoleModel.__table__.columns}
        assert "is_active" in columns

    def test_has_is_system_reserved_column(self):
        """Should have is_system_reserved column with default False."""
        columns = {c.name: c for c in RoleModel.__table__.columns}
        assert "is_system_reserved" in columns

    def test_has_updated_at_column(self):
        """Should have updated_at column as nullable DateTime."""
        columns = {c.name: c for c in RoleModel.__table__.columns}
        assert "updated_at" in columns
        assert columns["updated_at"].nullable

    def test_updated_at_nullable(self):
        """updated_at should be None when not set."""
        instance = RoleModel(
            name="nullable_updated_at",
            description="Test nullable updated_at",
        )
        assert instance.updated_at is None
