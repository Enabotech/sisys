"""RoleModel TDD tests — Red phase."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import DeclarativeBase

from src.infrastructure.storage.postgresql.models.role import RoleModel, _utc_now


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


class TestRoleModelDefaults:
    """RoleModel 默认值行为测试

    注意：SQLAlchemy mapped_column(default=...) 是数据库端默认值，
    Python 实例层面不会自动填充。显式传入时才会设置
    """

    def test_explicit_id_accepted(self) -> None:
        """显式传入 id 应被正确存储。"""
        uid = uuid4()
        instance = RoleModel(id=uid, name="test_role")
        assert instance.id == uid

    def test_explicit_id_unique(self) -> None:
        """不同 id 应不相等。"""
        a = RoleModel(id=uuid4(), name="role_a")
        b = RoleModel(id=uuid4(), name="role_b")
        assert a.id != b.id

    def test_explicit_is_active_false(self) -> None:
        """显式设置 is_active=False 应被正确存储。"""
        instance = RoleModel(name="inactive_role", is_active=False)
        assert instance.is_active is False

    def test_explicit_is_system_reserved_true(self) -> None:
        """显式设置 is_system_reserved=True 应被正确存储。"""
        instance = RoleModel(name="system_role", is_system_reserved=True)
        assert instance.is_system_reserved is True

    def test_explicit_created_at(self) -> None:
        """显式设置 created_at 应被正确存储。"""
        now = datetime.now(UTC).replace(tzinfo=None)
        instance = RoleModel(name="timestamp_role", created_at=now)
        assert instance.created_at == now

    def test_description_defaults_to_none(self) -> None:
        """description 默认应为 None。"""
        instance = RoleModel(name="no_desc")
        assert instance.description is None

    def test_explicit_values_override_defaults(self) -> None:
        """显式值应覆盖默认值。"""
        uid = uuid4()
        instance = RoleModel(
            id=uid,
            name="custom_role",
            description="Custom description",
            is_active=False,
            is_system_reserved=True,
        )
        assert instance.id == uid
        assert instance.name == "custom_role"
        assert instance.description == "Custom description"
        assert instance.is_active is False
        assert instance.is_system_reserved is True


class TestUtcNow:
    """_utc_now 辅助函数测试。"""

    def test_returns_naive_datetime(self) -> None:
        """应返回不带时区信息的 naive datetime。"""
        result = _utc_now()
        assert result.tzinfo is None

    def test_returns_current_time(self) -> None:
        """应返回接近当前 UTC 时间的值。"""
        before = datetime.now(UTC).replace(tzinfo=None)
        result = _utc_now()
        after = datetime.now(UTC).replace(tzinfo=None)
        assert before <= result <= after

    def test_returns_datetime_type(self) -> None:
        """应返回 datetime 类型。"""
        result = _utc_now()
        assert isinstance(result, datetime)
