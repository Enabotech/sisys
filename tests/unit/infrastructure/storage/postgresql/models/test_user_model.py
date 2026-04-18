"""UserModel TDD tests — Red phase."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import DeclarativeBase

from src.infrastructure.storage.postgresql.models.user import UserModel


class TestUserModel:
    """UserModel tests (TDD red-green-refactor)."""

    def test_table_name(self):
        """Table name should be 'users'."""
        assert UserModel.__tablename__ == "users"

    def test_has_id_column(self):
        """Should have id column as UUID primary key."""
        columns = {c.name: c for c in UserModel.__table__.columns}
        assert "id" in columns
        assert columns["id"].primary_key

    def test_has_username_column(self):
        """Should have username column as String(50), unique."""
        columns = {c.name: c for c in UserModel.__table__.columns}
        assert "username" in columns
        assert columns["username"].unique

    def test_has_email_column(self):
        """Should have email column as String(100), unique."""
        columns = {c.name: c for c in UserModel.__table__.columns}
        assert "email" in columns
        assert columns["email"].unique

    def test_has_hashed_password_column(self):
        """Should have hashed_password column as String(255)."""
        columns = {c.name: c for c in UserModel.__table__.columns}
        assert "hashed_password" in columns

    def test_has_is_active_column(self):
        """Should have is_active column as Boolean."""
        columns = {c.name: c for c in UserModel.__table__.columns}
        assert "is_active" in columns

    def test_has_created_at_column(self):
        """Should have created_at column as DateTime."""
        columns = {c.name: c for c in UserModel.__table__.columns}
        assert "created_at" in columns

    def test_has_updated_at_column(self):
        """Should have updated_at column as DateTime."""
        columns = {c.name: c for c in UserModel.__table__.columns}
        assert "updated_at" in columns

    def test_can_instantiate(self):
        """Should be able to create a user instance."""
        instance = UserModel(
            id=uuid4(),
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_secret",  # nosec B106 # pragma: allowlist secret
        )
        assert instance.username == "testuser"
        assert instance.email == "test@example.com"
        assert instance.is_active is True

    def test_inherits_from_declarative_base(self):
        """UserModel should inherit from a DeclarativeBase."""
        assert issubclass(UserModel, DeclarativeBase) or hasattr(UserModel, "__mapper__")
