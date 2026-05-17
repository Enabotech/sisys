"""基础设施层 PostgreSQL 模型包

定义所有 SQLAlchemy ORM 模型，映射到 PostgreSQL 数据库表

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from src.infrastructure.storage.postgresql.models.audit import AuditLogModel
from src.infrastructure.storage.postgresql.models.audit_outbox import AuditOutboxModel
from src.infrastructure.storage.postgresql.models.login_attempt import LoginAttemptModel
from src.infrastructure.storage.postgresql.models.memory import (
    MemoryChangeHistoryModel,
    MemoryMetadataModel,
)
from src.infrastructure.storage.postgresql.models.outbox import (
    Base,
    OutboxModel,
    pg_registry,
)
from src.infrastructure.storage.postgresql.models.permission import PermissionModel
from src.infrastructure.storage.postgresql.models.rbac_association import (
    role_permissions_table,
    user_roles_table,
)
from src.infrastructure.storage.postgresql.models.role import RoleModel
from src.infrastructure.storage.postgresql.models.user import UserModel

__all__ = [
    "Base",
    "OutboxModel",
    "UserModel",
    "RoleModel",
    "PermissionModel",
    "AuditLogModel",
    "AuditOutboxModel",
    "MemoryMetadataModel",
    "MemoryChangeHistoryModel",
    "LoginAttemptModel",
    "user_roles_table",
    "role_permissions_table",
    "pg_registry",
]
