"""隔离切换日志 SQLAlchemy 模型（Story 5.6 — FR-AC-06 审计留痕面）

对应 isolation_switch_logs 表（migration 015）：
- 表名复数对齐 5.x 新表惯例（sandbox_sessions/tool_executions/tool_chains——
  OD-4 命名映射）；无 tenant_id 列（对齐同域 audit_log 先例——isolation/audit
  域均无租户维度）
- 索引五：agent_id / switch_timestamp / previous_level / target_level 单列 +
  (agent_id, switch_timestamp) 组合——previous_level 单列与 target_level 对称
  （level 双向命中 or_ 两臂皆索引化，PG BitmapOr 可达——单维 level 检索
  P95<500ms 的结构性前提）
- CheckConstraint previous_level != target_level（DB 层拒绝 no-op 日志——
  实体不变量 242 场景③的 DB 投影，双层防线）
- created_at 行创建审计列 server_default NOW()（与 switch_timestamp 语义分工：
  切换时刻 vs 入库时刻；实体八字段无此列——检索投影丢弃，ORM↔实体不对称是
  既定形态非错误）
- 索引/约束由 alembic 015 创建（__table_args__ 声明与 migration 双向一致——
  create_all 兜底路径同构）
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text, event, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.storage.postgresql.models.outbox import Base


class IsolationSwitchLogModel(Base):
    """隔离切换日志 SQLAlchemy 模型，对应 isolation_switch_logs 表.

    Attributes:
        log_id: 日志 UUID 主键（实体自铸 UUID4——from_event 工厂）。
        agent_id: 目标 Agent 实例 UUID（无外键——审计事实独立于 Agent 生命周期，
            Agent TTL 过期后日志仍可查）。
        previous_level: 原隔离等级（String(20)——IsolationLevel.value 投影）。
        target_level: 目标隔离等级（String(20)）。
        trigger_reason: 触发原因（Text 语义——自由文本）。
        approval_chain: 审批链（JSONB 数组——空数组是用户请求通道真实事实）。
        switch_timestamp: 切换时刻（timezone-aware——单钟纪律，事件投影）。
        worm_ref: WORM 归档引用（nullable 预留——OD-1，V1 Story 13-4）。
        created_at: 行创建时刻（server_default NOW()——入库审计列，不进实体投影）。
    """

    __tablename__ = "isolation_switch_logs"

    __table_args__ = (
        # CHECK: no-op 日志 DB 层拒绝（与实体不变量 242 场景③双层防线——直插旁路也被拦）
        CheckConstraint(
            "previous_level != target_level",
            name="ck_isolation_switch_logs_not_noop",
        ),
        # CHECK: 等级值域对齐 IsolationLevel 全枚举域（migration 016 同名镜像——
        # ORM/migration 双向一致；防直插越域脏行毒化检索面，R1-F4）
        CheckConstraint(
            "previous_level IN ('L1','L2','L3','L4') AND target_level IN ('L1','L2','L3','L4')",
            name="ck_isolation_switch_logs_level_domain",
        ),
        # 查询索引五（level 双向命中 or_ 两臂皆索引化）
        Index("ix_isolation_switch_logs_agent", "agent_id"),
        Index("ix_isolation_switch_logs_switch_ts", "switch_timestamp"),
        Index("ix_isolation_switch_logs_previous", "previous_level"),
        Index("ix_isolation_switch_logs_target", "target_level"),
        Index("ix_isolation_switch_logs_agent_ts", "agent_id", "switch_timestamp"),
    )

    log_id: Mapped[uuid.UUID] = mapped_column(UUID(), primary_key=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(), nullable=False)
    previous_level: Mapped[str] = mapped_column(String(20), nullable=False)
    target_level: Mapped[str] = mapped_column(String(20), nullable=False)
    # Text 对齐 migration 015（R1-F19——String 无长度与 Text 在 PG 等价但
    # DDL 形态漂移 create_all 兜底路径）
    trigger_reason: Mapped[str] = mapped_column(Text(), nullable=False)
    approval_chain: Mapped[list[str]] = mapped_column(JSONB(), nullable=False, default=list)
    switch_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    worm_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

    def __init__(  # 与既有模型先例（tool_version.py）一致的显式构造器
        self,
        log_id: uuid.UUID | None = None,
        agent_id: uuid.UUID | None = None,
        previous_level: str = "",
        target_level: str = "",
        trigger_reason: str = "",
        approval_chain: list[str] | None = None,
        switch_timestamp: datetime | None = None,
        worm_ref: str | None = None,
        created_at: datetime | None = None,
    ) -> None:
        """显式构造器（server_default 列兜底——created_at 交由 DB 填充时仍可显式注入）。"""
        self.log_id = log_id or uuid.uuid4()
        self.agent_id = agent_id or uuid.uuid4()
        self.previous_level = previous_level
        self.target_level = target_level
        self.trigger_reason = trigger_reason
        self.approval_chain = approval_chain if approval_chain is not None else []
        self.switch_timestamp = switch_timestamp or datetime.now(UTC)
        self.worm_ref = worm_ref
        if created_at is not None:
            self.created_at = created_at


# =============================================================================
# RLS 防篡改 DDL 的 create_all 路径对齐（after_create 钩子）
# =============================================================================
# 背景：ensure_alembic_migration 的 create_all 兜底路径（alembic 超时/失败时）
# 只执行 ORM 元数据（表/索引/CheckConstraint），不执行 migration 015 的
# op.execute RLS 语句——兜底建的表缺 RLS 策略，防篡改语义失真（CI 冷启动
# 超时实测形态，2026-10-25）。after_create 使 create_all 建表时同步执行同款
# RLS DDL，两条建表路径产出一致；对已存在的表（checkfirst 跳过）不触发，
# alembic 正规路径不受影响。

_RLS_CREATE_PATH_STATEMENTS = (
    "ALTER TABLE isolation_switch_logs ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE isolation_switch_logs FORCE ROW LEVEL SECURITY",
    """
    CREATE POLICY isolation_switch_logs_insert ON isolation_switch_logs
    FOR INSERT WITH CHECK (true)
    """,
    """
    CREATE POLICY isolation_switch_logs_select ON isolation_switch_logs
    FOR SELECT USING (true)
    """,
    """
    CREATE POLICY isolation_switch_logs_deny_update ON isolation_switch_logs
    AS RESTRICTIVE
    FOR UPDATE USING (false) WITH CHECK (false)
    """,
    """
    CREATE POLICY isolation_switch_logs_deny_delete ON isolation_switch_logs
    AS RESTRICTIVE
    FOR DELETE USING (false)
    """,
)


@event.listens_for(IsolationSwitchLogModel.__table__, "after_create")
def _apply_rls_on_create_all(target: Any, connection: Any, **kwargs: Any) -> None:
    """create_all 建表时同步应用 RLS 四策略 + FORCE（与 migration 015+016 终态同款——
    deny 策略 AS RESTRICTIVE，R2-F1：permissive deny 与 016 终态漂移会使未来
    permissive 放行策略经 OR 合并消解 deny）."""
    for statement in _RLS_CREATE_PATH_STATEMENTS:
        connection.exec_driver_sql(statement)


__all__ = ["IsolationSwitchLogModel"]
