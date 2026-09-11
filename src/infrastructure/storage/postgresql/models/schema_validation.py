"""基础设施层 Schema 验证记录 SQLAlchemy 模型模块

定义 SchemaValidationRecordModel ORM 模型，对应 schema_validation_records 表
（migration 013）。
violations 字段使用 JSONB 存储 SchemaViolation 列表（已脱敏）。
4 复合索引由 Alembic migration 创建（migration 013）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as SA_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.storage.postgresql.models.outbox import Base


class SchemaValidationRecordModel(Base):
    """Schema 验证记录 SQLAlchemy 模型，对应 schema_validation_records 表

    Attributes:
        record_id: 记录 UUID 主键
        execution_id: 关联 ToolExecution ID
        tool_id: 工具 ID
        tenant_id: 多租户隔离标识符
        validation_phase: 校验阶段（INPUT / OUTPUT / COMPATIBILITY）
        is_valid: 是否通过
        violations: 违规列表 JSONB（含 path / expected / actual / message）
        retry_attempt: 当前重试次数（1-based）
        validated_at: 校验时间戳
        schema_version: Tool.version 快照（用于 4.6 兼容性追踪）
        failure_reason: 失败原因（人类可读）
    """

    __tablename__ = "schema_validation_records"

    __table_args__ = (
        # CHECK 约束与 migration 013 严格对齐
        CheckConstraint(
            "validation_phase IN ('INPUT', 'OUTPUT', 'COMPATIBILITY')",
            name="ck_schema_validation_records_phase",
        ),
        CheckConstraint(
            "retry_attempt >= 1",
            name="ck_schema_validation_records_retry_attempt",
        ),
        # 复合索引（与 migration 013 一致）
        Index(
            "ix_schema_validation_records_tenant_execution",
            "tenant_id",
            "execution_id",
        ),
        Index(
            "ix_schema_validation_records_tenant_tool_time",
            "tenant_id",
            "tool_id",
        ),
        Index(
            "ix_schema_validation_records_tenant_phase_valid",
            "tenant_id",
            "validation_phase",
            "is_valid",
        ),
        Index(
            "ix_schema_validation_records_tenant_valid_time",
            "tenant_id",
            "is_valid",
        ),
    )

    record_id: Mapped[UUID] = mapped_column(SA_UUID, primary_key=True, default=uuid4)
    execution_id: Mapped[UUID] = mapped_column(SA_UUID, nullable=False)
    tool_id: Mapped[UUID] = mapped_column(SA_UUID, nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(SA_UUID, nullable=False)
    validation_phase: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    violations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    retry_attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    validated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="NOW()",
    )
    schema_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0.0",
        server_default="1.0.0",
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __init__(
        self,
        record_id: UUID | None = None,
        execution_id: UUID | None = None,
        tool_id: UUID | None = None,
        tenant_id: UUID | None = None,
        validation_phase: str = "INPUT",
        is_valid: bool = False,
        violations: list[dict[str, Any]] | None = None,
        retry_attempt: int = 1,
        validated_at: datetime | None = None,
        schema_version: str = "1.0.0",
        failure_reason: str | None = None,
    ) -> None:
        self.record_id = record_id or uuid4()
        self.execution_id = execution_id or uuid4()
        self.tool_id = tool_id or uuid4()
        self.tenant_id = tenant_id or uuid4()
        self.validation_phase = validation_phase
        self.is_valid = is_valid
        self.violations = violations or []
        self.retry_attempt = retry_attempt
        self.validated_at = validated_at or datetime.now()
        self.schema_version = schema_version
        self.failure_reason = failure_reason


__all__ = [
    "SchemaValidationRecordModel",
]
