"""RBAC Models - 基于 SQLAlchemy 的角色权限模型.

基于 PostgreSQL 存储的角色、权限、用户角色关联模型。
遵循六边形架构：基础设施层模型。
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.storage.postgresql.base_repository import BaseRepository
from src.infrastructure.storage.postgresql.models.user import UserModel


class RoleModel(BaseRepository):
    """角色模型 (SQLAlchemy).

    属性:
        id: 角色 UUID (主键)
        name: 角色名称 (唯一)
        description: 角色描述
        permissions: 权限 JSON 列表
        is_system_reserved: 是否系统保留
        is_active: 是否激活
        created_at: 创建时间
        updated_at: 更新时间
    """

    __tablename__ = "roles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    permissions: Mapped[list[str]] = mapped_column(default=list)
    is_system_reserved: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    user_roles: Mapped[list[UserRoleModel]] = relationship("UserRoleModel", back_populates="role")


class PermissionModel(BaseRepository):
    """权限模型 (SQLAlchemy).

    属性:
        id: 权限 UUID (主键)
        resource: 资源类型 (如 "document", "agent")
        action: 操作类型 (如 "read", "write", "execute")
        description: 权限描述
        created_at: 创建时间
    """

    __tablename__ = "permissions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    resource: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Relationships
    role_permissions: Mapped[list[RolePermissionModel]] = relationship("RolePermissionModel", back_populates="permission")

    @property
    def full_name(self) -> str:
        """返回完整权限名称 (resource:action)。"""
        return f"{self.resource}:{self.action}"


class UserRoleModel(BaseRepository):
    """用户-角色关联模型 (SQLAlchemy).

    多对多关系表，关联用户和角色。
    """

    __tablename__ = "user_roles"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role_id: Mapped[UUID] = mapped_column(ForeignKey("roles.id"), primary_key=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    assigned_by: Mapped[UUID | None] = mapped_column(nullable=True)

    # Relationships
    user: Mapped[UserModel] = relationship("UserModel", back_populates="user_roles")
    role: Mapped[RoleModel] = relationship("RoleModel", back_populates="user_roles")


class RolePermissionModel(BaseRepository):
    """角色-权限关联模型 (SQLAlchemy).

    多对多关系表，关联角色和权限。
    """

    __tablename__ = "role_permissions"

    role_id: Mapped[UUID] = mapped_column(ForeignKey("roles.id"), primary_key=True)
    permission_id: Mapped[UUID] = mapped_column(ForeignKey("permissions.id"), primary_key=True)

    # Relationships
    role: Mapped["RoleModel"] = relationship("RoleModel")
    permission: Mapped["PermissionModel"] = relationship("PermissionModel", back_populates="role_permissions")
