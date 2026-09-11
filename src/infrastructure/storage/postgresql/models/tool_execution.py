"""基础设施层工具执行 SQLAlchemy 模型模块

定义 ToolExecutionModel ORM 模型，对应 tool_executions 表（migration 011）。
状态机迁移 + 乐观锁 state_version 字段；L2/L4 双轨存储边界由列定义体现。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.dialects.postgresql import UUID as SA_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.storage.postgresql.models.outbox import Base


class ToolExecutionModel(Base):
    """工具执行 SQLAlchemy 模型，对应 tool_executions 表

    Attributes:
        execution_id: 执行 UUID 主键
        tenant_id: 多租户隔离标识符
        tool_id: 工具 ID（ID-only 弱引用，4.1a 设计）
        tool_version: 工具版本号
        state: 执行状态机（IDLE / PLANNING / EXECUTING / VALIDATING / COMPLETED / FAILED）
        started_at: 启动时间
        completed_at: 完成时间（可为空）
        retry_count: 重试次数（≥ 0）
        failure_reason: 失败原因（可为空）
        input_hash: 输入参数哈希（证据包结构化字段）
        rule_version: 业务规则版本（证据包结构化字段）
        confidence: 置信度（证据包结构化字段）
        evidence_storage_key: L4 MinIO 引用
        state_version: 乐观锁版本号（≥ 0）
        metadata: 扩展元数据 JSON
        created_at: 创建时间
        updated_at: 更新时间
    """

    __tablename__ = "tool_executions"

    __table_args__ = (
        # CHECK 约束与 migration 011 严格对齐
        CheckConstraint(
            "state IN ('IDLE', 'PLANNING', 'EXECUTING', 'VALIDATING', 'COMPLETED', 'FAILED')",
            name="ck_tool_executions_state",
        ),
        CheckConstraint("retry_count >= 0", name="ck_tool_executions_retry_count"),
        CheckConstraint("state_version >= 0", name="ck_tool_executions_state_version"),
        # 复合索引（与 migration 011 一致；部分索引 terminal_state 需 postgresql_where）
        Index("ix_tool_executions_tenant_id", "tenant_id"),
        Index(
            "ix_tool_executions_tenant_tool_state",
            "tenant_id",
            "tool_id",
            "state",
        ),
        Index(
            "ix_tool_executions_tenant_started_at",
            "tenant_id",
            "started_at",
        ),
    )

    execution_id: Mapped[UUID] = mapped_column(SA_UUID, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(SA_UUID, nullable=False)
    tool_id: Mapped[UUID] = mapped_column(SA_UUID, nullable=False)
    tool_version: Mapped[str] = mapped_column(String(50), nullable=False)
    state: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="IDLE",
        server_default="IDLE",
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failure_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rule_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    def __init__(
        self,
        execution_id: UUID | None = None,
        tenant_id: UUID | None = None,
        tool_id: UUID | None = None,
        tool_version: str = "",
        state: str = "IDLE",
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        retry_count: int = 0,
        failure_reason: str | None = None,
        input_hash: str | None = None,
        rule_version: str | None = None,
        confidence: float | None = None,
        evidence_storage_key: str | None = None,
        state_version: int = 0,
        metadata: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        self.execution_id = execution_id or uuid4()
        self.tenant_id = tenant_id or uuid4()
        self.tool_id = tool_id or uuid4()
        self.tool_version = tool_version
        self.state = state
        self.started_at = started_at or datetime.now()
        self.completed_at = completed_at
        self.retry_count = retry_count
        self.failure_reason = failure_reason
        self.input_hash = input_hash
        self.rule_version = rule_version
        self.confidence = confidence
        self.evidence_storage_key = evidence_storage_key
        self.state_version = state_version
        self.metadata_ = metadata or {}
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()


__all__ = [
    "ToolExecutionModel",
]
