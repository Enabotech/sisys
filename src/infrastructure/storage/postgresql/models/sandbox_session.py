"""基础设施层 SandboxSession SQLAlchemy 模型模块

Story 4.4 — Docker 沙箱执行。

定义 SandboxSessionModel ORM 模型，对应 sandbox_sessions 表（migration 015）。

设计要点:
- 字符串主键 session_id(VARCHAR(64), 业务标识符,匹配 ^[A-Za-z0-9_-]{1,64}$)
- 不使用 UUID 主键（与 SandboxSession 业务主键保持一致）
- tenant_id UUID 多租户隔离
- container_id 字符串可空（启动后填充）
- resource_limits JSONB 容器资源限制字典
- state VARCHAR(16) + CHECK 约束(RUNNING / TERMINATED / FAILED)
- state_version 乐观锁版本号
- 3 复合/唯一索引由 Alembic migration 015 创建

与 schema_validation.py / tool_execution.py 模式一致。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as SA_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.storage.postgresql.models.outbox import Base


class SandboxSessionModel(Base):
    """沙箱会话 SQLAlchemy 模型，对应 sandbox_sessions 表

    Attributes:
        session_id: 业务会话标识符字符串主键
        tenant_id: 多租户隔离 UUID
        container_id: Docker container ID（启动后填充）
        image_digest: 实际启动的镜像 digest
        started_at: 启动时间
        last_activity_at: 最后活动时间（用于 30 分钟 TTL 计算）
        terminated_at: 终止时间（终态时填充）
        resource_limits: 容器资源限制 JSONB
        state: 状态字符串（RUNNING / TERMINATED / FAILED）
        state_version: 乐观锁版本号
    """

    __tablename__ = "sandbox_sessions"

    __table_args__ = (
        # CHECK 约束与 migration 015 严格对齐
        CheckConstraint(
            "state IN ('RUNNING', 'TERMINATED', 'FAILED')",
            name="ck_sandbox_sessions_state",
        ),
        # 索引由 Alembic migration 015 创建（避免 ORM 与 migration 双重声明）
        # ix_sandbox_sessions_tenant_state
        # ix_sandbox_sessions_state_last_activity
        # ix_sandbox_sessions_container_id_unique
    )

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True, nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(SA_UUID(as_uuid=True), nullable=False)
    container_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    image_digest: Mapped[str] = mapped_column(String(512), nullable=False, server_default="")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="NOW()",
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="NOW()",
    )
    terminated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resource_limits: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    state: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default="RUNNING",
    )
    state_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    def __init__(
        self,
        session_id: str,
        tenant_id: uuid.UUID | None = None,
        container_id: str | None = None,
        image_digest: str = "",
        started_at: datetime | None = None,
        last_activity_at: datetime | None = None,
        terminated_at: datetime | None = None,
        resource_limits: dict[str, Any] | None = None,
        state: str = "RUNNING",
        state_version: int = 0,
    ) -> None:
        now = datetime.now(UTC)
        self.session_id = session_id
        self.tenant_id = tenant_id or uuid.uuid4()
        self.container_id = container_id
        self.image_digest = image_digest
        self.started_at = started_at or now
        self.last_activity_at = last_activity_at or now
        self.terminated_at = terminated_at
        self.resource_limits = resource_limits or {}
        self.state = state
        self.state_version = state_version


__all__ = ["SandboxSessionModel"]
