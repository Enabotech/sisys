"""RoleService — Role management service implementation.

Provides CRUD operations for roles and role-permission assignment.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.config.auth import AuthConfig, get_auth_config
from src.infrastructure.security.models import Role
from src.infrastructure.storage.postgresql.models.association import (
    role_permissions_table,
    user_roles_table,
)
from src.infrastructure.storage.postgresql.models.permission import PermissionModel
from src.infrastructure.storage.postgresql.models.role import RoleModel
from src.infrastructure.storage.postgresql.models.user import UserModel

if TYPE_CHECKING:
    pass


class RoleNotFoundError(Exception):
    """Role not found."""

    pass


class RoleAlreadyExistsError(Exception):
    """Role with same name already exists."""

    pass


class RoleService:
    """Role management service.

    Provides CRUD operations for roles and role-permission assignment.
    """

    def __init__(
        self,
        session: AsyncSession,
        config: AuthConfig | None = None,
    ) -> None:
        """Initialize RoleService.

        Args:
            session: Async database session.
            config: Auth configuration. If None, loads from environment.
        """
        self._session = session
        self._config = config or get_auth_config()

    async def create_role(
        self,
        name: str,
        description: str | None = None,
        permissions: list[str] | None = None,
    ) -> Role:
        """Create a new role.

        Args:
            name: Role name (must be unique).
            description: Role description.
            permissions: List of permission strings (format: "resource:action").

        Returns:
            Role: Created role.

        Raises:
            RoleAlreadyExistsError: If role with same name exists.
        """
        # Check if role already exists
        existing = await self._get_role_by_name(name)
        if existing:
            raise RoleAlreadyExistsError(f"Role '{name}' already exists")

        # Create role
        role_model = RoleModel(
            id=uuid4(),
            name=name,
            description=description,
        )
        self._session.add(role_model)

        # Add permissions
        if permissions:
            for perm_str in permissions:
                perm = await self._get_or_create_permission(perm_str)
                await self._session.execute(
                    role_permissions_table.insert().values(
                        role_id=role_model.id,
                        permission_id=perm.id,
                    )
                )

        await self._session.flush()

        # Return role object
        return await self._build_role_object(role_model)

    async def get_role_by_id(self, role_id: UUID) -> Role | None:
        """Get role by ID.

        Args:
            role_id: Role's UUID.

        Returns:
            Role | None: Role object or None if not found.
        """
        result = await self._session.get(RoleModel, role_id)
        if result is None:
            return None
        return await self._build_role_object(result)

    async def get_role_by_name(self, name: str) -> Role | None:
        """Get role by name.

        Args:
            name: Role name.

        Returns:
            Role | None: Role object or None if not found.
        """
        role_model = await self._get_role_by_name(name)
        if role_model is None:
            return None
        return await self._build_role_object(role_model)

    async def get_all_roles(self, include_inactive: bool = False) -> list[Role]:
        """Get all roles.

        Args:
            include_inactive: If True, include inactive (soft-deleted) roles.

        Returns:
            list[Role]: List of all active roles (or all roles if include_inactive=True).
        """
        from sqlalchemy import select

        query = select(RoleModel)
        if not include_inactive:
            query = query.where(RoleModel.is_active.is_(True))

        result = await self._session.execute(query)
        role_models = result.scalars().all()

        roles = []
        for role_model in role_models:
            roles.append(await self._build_role_object(role_model))

        return roles

    async def update_role(
        self,
        role_id: UUID,
        name: str | None = None,
        description: str | None = None,
    ) -> Role:
        """Update a role.

        Args:
            role_id: Role's UUID.
            name: New role name (optional).
            description: New role description (optional).

        Returns:
            Role: Updated role.

        Raises:
            RoleNotFoundError: If role doesn't exist.
            RoleAlreadyExistsError: If new name conflicts with existing role.
        """
        role_model = await self._session.get(RoleModel, role_id)
        if role_model is None:
            raise RoleNotFoundError(f"Role '{role_id}' not found")

        # Check for name conflict
        if name and name != role_model.name:
            existing = await self._get_role_by_name(name)
            if existing and existing.id != role_id:
                raise RoleAlreadyExistsError(f"Role '{name}' already exists")
            role_model.name = name

        if description is not None:
            role_model.description = description

        role_model.updated_at = datetime.now(UTC).replace(tzinfo=None)

        await self._session.flush()

        return await self._build_role_object(role_model)

    async def delete_role(self, role_id: UUID) -> bool:
        """Soft delete a role (marks as inactive).

        Args:
            role_id: Role's UUID.

        Returns:
            bool: True if deleted successfully.

        Raises:
            RoleNotFoundError: If role doesn't exist.
        """
        role_model = await self._session.get(RoleModel, role_id)
        if role_model is None:
            raise RoleNotFoundError(f"Role '{role_id}' not found")

        role_model.is_active = False
        role_model.updated_at = datetime.now(UTC).replace(tzinfo=None)

        await self._session.flush()
        return True

    async def assign_permission_to_role(self, role_id: UUID, permission_str: str) -> bool:
        """Assign a permission to a role.

        Args:
            role_id: Role's UUID.
            permission_str: Permission string (format: "resource:action").

        Returns:
            bool: True if assignment succeeded.

        Raises:
            RoleNotFoundError: If role doesn't exist.
        """
        role_model = await self._session.get(RoleModel, role_id)
        if role_model is None:
            raise RoleNotFoundError(f"Role '{role_id}' not found")

        # Get or create permission
        perm = await self._get_or_create_permission(permission_str)

        # Check if already assigned
        from sqlalchemy import select

        result = await self._session.execute(
            select(role_permissions_table.c.role_id)
            .where(role_permissions_table.c.role_id == role_id)
            .where(role_permissions_table.c.permission_id == perm.id)
        )
        if result.scalar_one_or_none():
            return True  # Already assigned

        # Assign permission
        await self._session.execute(
            role_permissions_table.insert().values(
                role_id=role_id,
                permission_id=perm.id,
            )
        )

        role_model.updated_at = datetime.now(UTC).replace(tzinfo=None)
        await self._session.flush()

        return True

    async def revoke_permission_from_role(self, role_id: UUID, permission_str: str) -> bool:
        """Revoke a permission from a role.

        Args:
            role_id: Role's UUID.
            permission_str: Permission string (format: "resource:action").

        Returns:
            bool: True if revocation succeeded.

        Raises:
            RoleNotFoundError: If role doesn't exist.
        """
        role_model = await self._session.get(RoleModel, role_id)
        if role_model is None:
            raise RoleNotFoundError(f"Role '{role_id}' not found")

        # Get permission
        perm = await self._get_permission_by_string(permission_str)
        if perm is None:
            return True  # Permission doesn't exist, consider it revoked

        # Delete assignment
        await self._session.execute(
            role_permissions_table.delete()
            .where(role_permissions_table.c.role_id == role_id)
            .where(role_permissions_table.c.permission_id == perm.id)
        )

        role_model.updated_at = datetime.now(UTC).replace(tzinfo=None)
        await self._session.flush()

        return True

    async def get_role_permissions(self, role_id: UUID) -> list[str]:
        """Get all permissions for a role.

        Args:
            role_id: Role's UUID.

        Returns:
            list[str]: List of permission strings.
        """
        from sqlalchemy import select

        result = await self._session.execute(
            select(PermissionModel.name)
            .join(role_permissions_table, PermissionModel.id == role_permissions_table.c.permission_id)
            .where(role_permissions_table.c.role_id == role_id)
        )
        return list(result.scalars().all())

    async def assign_role_to_user(self, user_id: UUID, role_id: UUID) -> bool:
        """Assign a role to a user.

        Args:
            user_id: User's UUID.
            role_id: Role's UUID.

        Returns:
            bool: True if assignment succeeded.
        """
        from sqlalchemy import select

        # Check if user exists
        user = await self._session.get(UserModel, user_id)
        if user is None:
            return False

        # Check if role exists
        role = await self._session.get(RoleModel, role_id)
        if role is None:
            return False

        # Check if already assigned
        result = await self._session.execute(
            select(user_roles_table.c.user_id)
            .where(user_roles_table.c.user_id == user_id)
            .where(user_roles_table.c.role_id == role_id)
        )
        if result.scalar_one_or_none():
            return True  # Already assigned

        # Check max roles per user limit
        max_roles_per_user = 10
        result = await self._session.execute(select(user_roles_table.c.user_id).where(user_roles_table.c.user_id == user_id))
        current_roles = len(result.scalars().all())
        if current_roles >= max_roles_per_user:
            raise ValueError(f"User already has maximum number of roles ({max_roles_per_user})")

        # Assign role
        await self._session.execute(
            user_roles_table.insert().values(
                user_id=user_id,
                role_id=role_id,
            )
        )

        await self._session.flush()
        return True

    async def revoke_role_from_user(self, user_id: UUID, role_id: UUID) -> bool:
        """Revoke a role from a user.

        Args:
            user_id: User's UUID.
            role_id: Role's UUID.

        Returns:
            bool: True if revocation succeeded.
        """
        await self._session.execute(
            user_roles_table.delete().where(user_roles_table.c.user_id == user_id).where(user_roles_table.c.role_id == role_id)
        )

        await self._session.flush()
        return True

    async def get_user_roles(self, user_id: UUID) -> list[Role]:
        """Get all roles for a user.

        Args:
            user_id: User's UUID.

        Returns:
            list[Role]: List of role objects.
        """
        from sqlalchemy import select

        result = await self._session.execute(
            select(RoleModel)
            .join(user_roles_table, RoleModel.id == user_roles_table.c.role_id)
            .where(user_roles_table.c.user_id == user_id)
        )
        role_models = result.scalars().all()

        roles = []
        for role_model in role_models:
            roles.append(await self._build_role_object(role_model))

        return roles

    # -------------------------------------------------------------------------
    # Private helper methods
    # -------------------------------------------------------------------------

    async def _get_role_by_name(self, name: str) -> RoleModel | None:
        """Get role model by name."""
        from sqlalchemy import select

        result = await self._session.execute(select(RoleModel).where(RoleModel.name == name))
        return result.scalar_one_or_none()

    async def _get_permission_by_string(self, permission_str: str) -> PermissionModel | None:
        """Get permission model by name (permission string)."""
        from sqlalchemy import select

        result = await self._session.execute(select(PermissionModel).where(PermissionModel.name == permission_str))
        return result.scalar_one_or_none()

    async def _get_or_create_permission(self, permission_str: str) -> PermissionModel:
        """Get or create a permission by string."""
        # Validate permission format
        if not permission_str or ":" not in permission_str or permission_str.startswith(":"):
            raise ValueError(f"Invalid permission format: '{permission_str}'. Expected 'resource:action'")

        perm = await self._get_permission_by_string(permission_str)
        if perm:
            return perm

        # Parse resource and action
        parts = permission_str.split(":", 1)
        resource = parts[0]
        action = parts[1]

        perm = PermissionModel(
            id=uuid4(),
            name=permission_str,
            resource=resource,
            action=action,
        )
        self._session.add(perm)
        await self._session.flush()
        return perm

    async def _build_role_object(self, role_model: RoleModel) -> Role:
        """Build Role object from RoleModel."""
        permissions = await self.get_role_permissions(role_model.id)
        return Role(
            id=role_model.id,
            name=role_model.name,
            description=role_model.description,
            permissions=permissions,
            is_active=getattr(role_model, "is_active", True),
            created_at=role_model.created_at,
            updated_at=role_model.updated_at,
        )
