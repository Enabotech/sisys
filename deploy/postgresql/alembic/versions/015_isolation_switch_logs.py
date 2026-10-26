"""Story 5.6: isolation_switch_logs table（隔离切换日志——FR-AC-06 审计留痕面）

Create Date: 2026-10-25

This migration creates:
- isolation_switch_logs table: 隔离等级切换的追加型审计日志
  （六字段 FR-AC-06 六要素 + worm_ref 预留 + created_at 行创建审计列）
- Row-Level Security policies for immutability
  （INSERT/SELECT 放行 + deny UPDATE/DELETE——002_audit_tables 模式照抄）
- FORCE ROW LEVEL SECURITY（表 owner 连接不绕过——DC-4）
- CheckConstraint previous_level != target_level（DB 层拒绝 no-op 日志）
- 索引五（level 双向命中 or_ 两臂皆索引化——previous/target 对称）

命名与列集（OD-4）: 表名复数 isolation_switch_logs（对齐 5.x 新表惯例）+
实体字段命名跟随事件 payload SSOT（previous_level/target_level/trigger_reason）
+ 无 tenant_id 列（对齐同域 audit_log 先例）+ worm_ref（非 worm_storage_ref）。

Migration chain:
001_initial (base)
    └── 002_audit_tables
        └── ... (003-014)
            └── 015_isolation_switch_logs (this file)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 isolation_switch_logs 表 + 索引五 + CheckConstraint + RLS 防篡改."""
    op.create_table(
        "isolation_switch_logs",
        sa.Column("log_id", UUID(), nullable=False),
        sa.Column("agent_id", UUID(), nullable=False),
        sa.Column("previous_level", sa.String(20), nullable=False),
        sa.Column("target_level", sa.String(20), nullable=False),
        sa.Column("trigger_reason", sa.Text(), nullable=False),
        sa.Column("approval_chain", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("switch_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("worm_ref", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("log_id", name="pk_isolation_switch_logs"),
        sa.CheckConstraint(
            "previous_level != target_level",
            name="ck_isolation_switch_logs_not_noop",
        ),
    )
    # 索引五：level 双向命中 or_ 两臂皆索引化（BitmapOr 可达——P95<500ms 结构性前提）
    op.create_index("ix_isolation_switch_logs_agent", "isolation_switch_logs", ["agent_id"])
    op.create_index("ix_isolation_switch_logs_switch_ts", "isolation_switch_logs", ["switch_timestamp"])
    op.create_index("ix_isolation_switch_logs_previous", "isolation_switch_logs", ["previous_level"])
    op.create_index("ix_isolation_switch_logs_target", "isolation_switch_logs", ["target_level"])
    op.create_index(
        "ix_isolation_switch_logs_agent_ts",
        "isolation_switch_logs",
        ["agent_id", "switch_timestamp"],
    )

    # =========================================================================
    # RLS 防篡改四件套（002_audit_tables 模式照抄）+ FORCE（DC-4）
    # =========================================================================
    op.execute("ALTER TABLE isolation_switch_logs ENABLE ROW LEVEL SECURITY")
    # FORCE: 表 owner 默认绕过 RLS——FORCE 后受约束（superuser/BYPASSRLS 属性仍绕过，
    # 环境敏感性由测试动态探测 skip 承载——AC-4.1）
    op.execute("ALTER TABLE isolation_switch_logs FORCE ROW LEVEL SECURITY")

    # 放行 INSERT（追加写入——审计日志只增）
    op.execute(
        """
        CREATE POLICY isolation_switch_logs_insert ON isolation_switch_logs
        FOR INSERT
        WITH CHECK (true)
    """
    )
    # 放行 SELECT（多维检索——审计读取面）
    op.execute(
        """
        CREATE POLICY isolation_switch_logs_select ON isolation_switch_logs
        FOR SELECT
        USING (true)
    """
    )
    # Deny UPDATE（追加型不可改写——002 先例：USING false + WITH CHECK false）
    op.execute(
        """
        CREATE POLICY isolation_switch_logs_deny_update ON isolation_switch_logs
        FOR UPDATE
        USING (false)
        WITH CHECK (false)
    """
    )
    # Deny DELETE（002 已修正的 PG 语法约束：DELETE policy 仅允许 USING 子句——
    # WITH CHECK 不能应用于 SELECT/DELETE，PG 语法错误）
    op.execute(
        """
        CREATE POLICY isolation_switch_logs_deny_delete ON isolation_switch_logs
        FOR DELETE
        USING (false)
    """
    )


def downgrade() -> None:
    """对称回滚：DROP POLICY 清单完整 → DISABLE RLS → 索引 → 表."""
    op.execute("DROP POLICY IF EXISTS isolation_switch_logs_insert ON isolation_switch_logs")
    op.execute("DROP POLICY IF EXISTS isolation_switch_logs_select ON isolation_switch_logs")
    op.execute("DROP POLICY IF EXISTS isolation_switch_logs_deny_update ON isolation_switch_logs")
    op.execute("DROP POLICY IF EXISTS isolation_switch_logs_deny_delete ON isolation_switch_logs")
    op.execute("ALTER TABLE isolation_switch_logs DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_isolation_switch_logs_agent_ts", table_name="isolation_switch_logs")
    op.drop_index("ix_isolation_switch_logs_target", table_name="isolation_switch_logs")
    op.drop_index("ix_isolation_switch_logs_previous", table_name="isolation_switch_logs")
    op.drop_index("ix_isolation_switch_logs_switch_ts", table_name="isolation_switch_logs")
    op.drop_index("ix_isolation_switch_logs_agent", table_name="isolation_switch_logs")
    op.drop_table("isolation_switch_logs")
