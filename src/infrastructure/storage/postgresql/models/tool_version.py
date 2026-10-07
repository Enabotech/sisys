"""基础设施层工具版本 SQLAlchemy 模型（Story 4-6）

对应 tool_versions 表（migration 016）：
- (tool_id, version) 复合唯一；平台级资源无 tenant_id（TOOL_CATALOG 语义一致）
- 2 个 partial unique index 硬守护单 STABLE / 单活跃 CANARY（并发不变量，
  postgresql_where 声明——Base.metadata.create_all 与 alembic 016 双路径一致）
- CHECK 值域与 ToolVersionStatus 小写枚举一一对应
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.storage.postgresql.models import Base


class ToolVersionModel(Base):
    """工具版本 SQLAlchemy 模型，对应 tool_versions 表。

    Attributes:
        version_id: 版本记录 UUID 主键
        tool_id: 所属工具 ID（无外键——011 先例，tools 表落地后补强）
        version: SemVer 版本号
        input_schema / output_schema: JSON Schema 快照
        status: 发布状态（pending/canary/stable/deprecated）
        traffic_weight: 承接流量比例 [0,100]
        required_rollout_mode: 发布模式（any/canary_only）
        last_stable_at: 曾为 STABLE 的时间戳（回滚候选依据；回滚降级清空）
        created_at / updated_at: 时间戳
    """

    __tablename__ = "tool_versions"

    __table_args__ = (
        # CHECK 约束与 migration 016 严格对齐（与 ToolVersionStatus 小写值域一致）
        CheckConstraint(
            "status IN ('pending', 'canary', 'stable', 'deprecated')",
            name="ck_tool_versions_status",
        ),
        CheckConstraint(
            "traffic_weight BETWEEN 0 AND 100",
            name="ck_tool_versions_traffic_weight",
        ),
        CheckConstraint(
            "required_rollout_mode IN ('any', 'canary_only')",
            name="ck_tool_versions_rollout_mode",
        ),
        # 复合唯一（注册幂等性）
        Index("uq_tool_versions_tool_version", "tool_id", "version", unique=True),
        # 单活跃不变量并发守护（partial unique index ×2——逐语句即时校验）
        Index(
            "uq_tool_versions_single_stable",
            "tool_id",
            unique=True,
            postgresql_where=text("status = 'stable'"),
        ),
        Index(
            "uq_tool_versions_single_canary",
            "tool_id",
            unique=True,
            postgresql_where=text("status = 'canary'"),
        ),
        # 查询索引
        Index("ix_tool_versions_tool_status", "tool_id", "status"),
        Index("ix_tool_versions_tool_last_stable", "tool_id", "last_stable_at"),
    )

    version_id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True, default=uuid.uuid4)
    tool_id: Mapped[uuid.UUID] = mapped_column(UUID(), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSONB(), nullable=False, default=dict)
    output_schema: Mapped[dict[str, Any]] = mapped_column(JSONB(), nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    traffic_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    required_rollout_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="any")
    last_stable_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    def __init__(  # noqa: PLR0913 — 与既有模型先例一致的显式构造器
        self,
        version_id: uuid.UUID | None = None,
        tool_id: uuid.UUID | None = None,
        version: str = "",
        input_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        status: str = "pending",
        traffic_weight: int = 0,
        required_rollout_mode: str = "any",
        last_stable_at: datetime | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        """显式构造器（mapped_column default 兜底）。"""
        self.version_id = version_id or uuid.uuid4()
        self.tool_id = tool_id or uuid.uuid4()
        self.version = version
        self.input_schema = input_schema or {}
        self.output_schema = output_schema or {}
        self.status = status
        self.traffic_weight = traffic_weight
        self.required_rollout_mode = required_rollout_mode
        self.last_stable_at = last_stable_at
        self.created_at = created_at or datetime.now(UTC)
        self.updated_at = updated_at or datetime.now(UTC)


__all__ = ["ToolVersionModel"]
