"""PostgreSQL models package."""

from src.infrastructure.storage.postgresql.models.association import (
    role_permissions_table,
    user_roles_table,
)
from src.infrastructure.storage.postgresql.models.outbox import (
    Base,
    OutboxModel,
    pg_registry,
)
from src.infrastructure.storage.postgresql.models.permission import PermissionModel
from src.infrastructure.storage.postgresql.models.role import RoleModel
from src.infrastructure.storage.postgresql.models.user import UserModel

__all__ = [
    "Base",
    "OutboxModel",
    "UserModel",
    "RoleModel",
    "PermissionModel",
    "user_roles_table",
    "role_permissions_table",
    "pg_registry",
]
