"""基础设施层演进日志 SQLAlchemy 模型（Story 4.7）

对应 tool_evolution_logs 表（migration 017）：
- (tenant_id, execution_id) 复合唯一——execution_id 幂等 upsert 的硬约束
- fix_attempts JSONB（FixAttempt 摘要数组，含 attempt_execution_id 回链）
- trigger_code / final_status CHECK 值域与枚举一一对应
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.storage.postgresql.models.outbox import Base


class EvolutionLogEntryModel(Base):
    """演进日志 SQLAlchemy 模型，对应 tool_evolution_logs 表。

    Attributes:
        log_id: 日志 UUID 主键
        tenant_id / tool_id / execution_id: 归属与幂等键
        tool_version: 工具版本快照
        trigger_code: 触发异常编码（EXCEPTION_389 / EXCEPTION_382）
        error_signature: 归一化错误签名（64 hex）
        enhanced_retry_count: 增强尝试总数（1-3）
        fix_attempts: FixAttempt 摘要 JSONB 数组
        duration_sec: 闭环墙钟时长（R8-21 口径）
        final_status: 终态（RECOVERED / MARKED_INFEASIBLE）
        created_at: 创建时间
    """

    __tablename__ = "tool_evolution_logs"

    __table_args__ = (
        CheckConstraint(
            "trigger_code IN ('EXCEPTION_389', 'EXCEPTION_382')",
            name="ck_tool_evolution_logs_trigger_code",
        ),
        CheckConstraint(
            "final_status IN ('RECOVERED', 'MARKED_INFEASIBLE')",
            name="ck_tool_evolution_logs_final_status",
        ),
        CheckConstraint(
            "enhanced_retry_count BETWEEN 1 AND 3",
            name="ck_tool_evolution_logs_retry_count_range",
        ),
        CheckConstraint("duration_sec >= 0", name="ck_tool_evolution_logs_duration_nonneg"),
        Index(
            "uq_tool_evolution_logs_execution",
            "tenant_id",
            "execution_id",
            unique=True,
        ),
        Index("ix_tool_evolution_logs_tool", "tenant_id", "tool_id", text("created_at DESC")),
    )

    log_id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(), nullable=False)
    tool_id: Mapped[uuid.UUID] = mapped_column(UUID(), nullable=False)
    execution_id: Mapped[uuid.UUID] = mapped_column(UUID(), nullable=False)
    tool_version: Mapped[str] = mapped_column(String(64), nullable=False, server_default="")
    trigger_code: Mapped[str] = mapped_column(String(16), nullable=False)
    error_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    enhanced_retry_count: Mapped[int] = mapped_column(Integer, nullable=False)
    fix_attempts: Mapped[list[dict[str, Any]]] = mapped_column(JSONB(), nullable=False, server_default=text("'[]'"))
    duration_sec: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False, server_default="0")
    final_status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
