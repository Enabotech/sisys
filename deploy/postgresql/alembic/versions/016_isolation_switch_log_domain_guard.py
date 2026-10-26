"""Story 5.6 R1-F4: isolation_switch_logs 值域 CHECK + deny 策略 RESTRICTIVE 加固

Create Date: 2026-10-26

This migration hardens:
- 值域 CHECK: previous_level/target_level IN ('L1','L2','L3','L4')——对齐
  IsolationLevel 枚举全值域（.value 形态）而非 MVP 白名单（保 isolation_policy
  「V2 开放 L1 仅改 MVP_ALLOWED_LEVELS 一处」的单点生效承诺；MVP 约束由应用层
  446 白名单承载）。防御直插脏值行（RLS INSERT WITH CHECK(true) 放行任意字符串
  + _to_entity 枚举重建裸 ValueError 毒化整页检索——单条脏行使该页检索瘫痪）。
- deny UPDATE/DELETE 策略 permissive → RESTRICTIVE: PG 语义 permissive 策略间
  OR 合并——未来任何新增 permissive 放行策略会使 deny 形同虚设；RESTRICTIVE
  策略 AND 否决（restrictive(false) + permissive(true) 并存 → 仍 0 行），
  是 deny 语义的标准加固形态。⚠️ ALTER POLICY 不支持修改
  permissive/restrictive 属性（PG 语法错误——必须 DROP + CREATE）。

Migration chain:
001_initial (base)
    └── 002_audit_tables
        └── ... (003-015)
            └── 016_isolation_switch_log_domain_guard (this file)
"""

from __future__ import annotations

from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """值域 CHECK + deny 策略 RESTRICTIVE 化（DROP + CREATE——ALTER 不支持）."""
    op.execute(
        """
        ALTER TABLE isolation_switch_logs
        ADD CONSTRAINT ck_isolation_switch_logs_level_domain
        CHECK (previous_level IN ('L1','L2','L3','L4') AND target_level IN ('L1','L2','L3','L4'))
    """
    )
    # deny UPDATE → RESTRICTIVE（策略名与 015 逐字一致；ALTER POLICY 无法改属性）
    op.execute("DROP POLICY IF EXISTS isolation_switch_logs_deny_update ON isolation_switch_logs")
    op.execute(
        """
        CREATE POLICY isolation_switch_logs_deny_update ON isolation_switch_logs
        AS RESTRICTIVE
        FOR UPDATE
        USING (false)
        WITH CHECK (false)
    """
    )
    # deny DELETE → RESTRICTIVE（DELETE policy 仅 USING 子句——015 已修正的语法约束保持）
    op.execute("DROP POLICY IF EXISTS isolation_switch_logs_deny_delete ON isolation_switch_logs")
    op.execute(
        """
        CREATE POLICY isolation_switch_logs_deny_delete ON isolation_switch_logs
        AS RESTRICTIVE
        FOR DELETE
        USING (false)
    """
    )


def downgrade() -> None:
    """对称回滚: RESTRICTIVE → permissive 形态还原（015 原形态）+ DROP 值域约束."""
    op.execute("DROP POLICY IF EXISTS isolation_switch_logs_deny_update ON isolation_switch_logs")
    op.execute(
        """
        CREATE POLICY isolation_switch_logs_deny_update ON isolation_switch_logs
        FOR UPDATE
        USING (false)
        WITH CHECK (false)
    """
    )
    op.execute("DROP POLICY IF EXISTS isolation_switch_logs_deny_delete ON isolation_switch_logs")
    op.execute(
        """
        CREATE POLICY isolation_switch_logs_deny_delete ON isolation_switch_logs
        FOR DELETE
        USING (false)
    """
    )
    op.execute("ALTER TABLE isolation_switch_logs DROP CONSTRAINT IF EXISTS ck_isolation_switch_logs_level_domain")
