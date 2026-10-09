"""基础设施层错误案例 SQLAlchemy 模型（Story 4.7）

对应 error_cases 表（migration 017）：
- 自然键 (tenant_id, tool_id, error_signature) 复合唯一——精确查表的全部语义
- 分类计数拆分（recovered_count/infeasible_count）防不可行写回冲掉修复配方
- occurrence_count = recovered + infeasible（CHECK 守恒硬约束）
- fix_summary 仅 RECOVERED 路径覆写（应用层规则，列 DEFAULT ''）
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.storage.postgresql.models.outbox import Base


class ErrorCaseModel(Base):
    """错误案例 SQLAlchemy 模型，对应 error_cases 表。

    Attributes:
        case_id: 案例 UUID 主键
        tenant_id / tool_id / error_signature: 自然键三元组
        error_category: 错误分类（首写定格——SCHEMA_VIOLATION / LLM_TRANSIENT / 沙箱 error_code）
        stderr_excerpt: STDERR 摘录（≤2000）
        fix_summary: 修复配方摘要（≤2000，仅 RECOVERED 且非 LLM_TRANSIENT 覆写）
        outcome: 最近一次终态（RECOVERED / MARKED_INFEASIBLE）
        recovered_count / infeasible_count / occurrence_count: 分类计数与观测合计
        last_seen_at / created_at: 时间戳
    """

    __tablename__ = "error_cases"

    __table_args__ = (
        CheckConstraint(
            "outcome IN ('RECOVERED', 'MARKED_INFEASIBLE')",
            name="ck_error_cases_outcome",
        ),
        CheckConstraint("recovered_count >= 0", name="ck_error_cases_recovered_nonneg"),
        CheckConstraint("infeasible_count >= 0", name="ck_error_cases_infeasible_nonneg"),
        CheckConstraint(
            "occurrence_count = recovered_count + infeasible_count",
            name="ck_error_cases_occurrence_conservation",
        ),
        CheckConstraint("occurrence_count >= 1", name="ck_error_cases_occurrence_min"),
        Index(
            "uq_error_cases_natural_key",
            "tenant_id",
            "tool_id",
            "error_signature",
            unique=True,
        ),
        # 按「工具最近案例」排序的查询索引（last_seen_at DESC）
        Index("ix_error_cases_tool", "tenant_id", "tool_id", text("last_seen_at DESC")),
    )

    case_id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(), nullable=False)
    tool_id: Mapped[uuid.UUID] = mapped_column(UUID(), nullable=False)
    error_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    error_category: Mapped[str] = mapped_column(String(64), nullable=False)
    stderr_excerpt: Mapped[str] = mapped_column(String(2000), nullable=False, server_default="")
    fix_summary: Mapped[str] = mapped_column(String(2000), nullable=False, server_default="")
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    recovered_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    infeasible_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
