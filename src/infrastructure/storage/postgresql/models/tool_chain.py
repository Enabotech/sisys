"""基础设施层工具链 SQLAlchemy 模型模块

定义 ToolChainModel ORM 模型，对应 tool_chains 表（migration 012）。
节点数组 nodes 使用 JSONB 存储（DAG 嵌套结构）。
GIN 索引 + 4 复合索引由 Alembic migration 创建。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as SA_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.storage.postgresql.models.outbox import Base


class ToolChainModel(Base):
    """工具链 DAG SQLAlchemy 模型，对应 tool_chains 表

    Attributes:
        chain_id: DAG UUID 主键
        tenant_id: 多租户隔离标识符
        name: DAG 名称（如 "pestel-to-swot-analysis"）
        description: DAG 业务说明
        nodes: 节点数组 JSONB（含 node_id / tool_slug / depends_on /
            arguments_template / failure_strategy / skip_on_upstream_failure）
        failure_strategy: DAG 级别失败策略（FAIL_FAST / CONTINUE_ON_ERROR / SKIP_DOWNSTREAM）
        max_concurrency: 最大并发节点数（≥ 1）
        created_at: 创建时间
        updated_at: 更新时间
    """

    __tablename__ = "tool_chains"

    __table_args__ = (
        # CHECK 约束与 migration 012 严格对齐
        CheckConstraint(
            "failure_strategy IN ('FAIL_FAST', 'CONTINUE_ON_ERROR', 'SKIP_DOWNSTREAM')",
            name="ck_tool_chains_failure_strategy",
        ),
        CheckConstraint("max_concurrency >= 1", name="ck_tool_chains_max_concurrency"),
        # 复合索引（与 migration 012 一致；GIN 索引需 op.execute 在 migration 中处理）
        Index("ix_tool_chains_tenant_id", "tenant_id"),
        Index("ix_tool_chains_tenant_name", "tenant_id", "name"),
        Index("ix_tool_chains_tenant_failure_strategy", "tenant_id", "failure_strategy"),
    )

    chain_id: Mapped[UUID] = mapped_column(SA_UUID, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(SA_UUID, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    nodes: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    failure_strategy: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="SKIP_DOWNSTREAM",
        server_default="SKIP_DOWNSTREAM",
    )
    max_concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=5, server_default="5")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="NOW()",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="NOW()",
    )

    def __init__(
        self,
        chain_id: UUID | None = None,
        tenant_id: UUID | None = None,
        name: str = "",
        description: str = "",
        nodes: list[dict[str, Any]] | None = None,
        failure_strategy: str = "SKIP_DOWNSTREAM",
        max_concurrency: int = 5,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        self.chain_id = chain_id or uuid4()
        self.tenant_id = tenant_id or uuid4()
        self.name = name
        self.description = description
        self.nodes = nodes or []
        self.failure_strategy = failure_strategy
        self.max_concurrency = max_concurrency
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()


__all__ = [
    "ToolChainModel",
]
