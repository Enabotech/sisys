"""演进日志 ABORTED 中止态（技术债清偿 A 类——中止遥测）

Revision ID: 018
Revises: 017
Create Date: 2026-10-10

tool_evolution_logs 的 final_status CHECK 扩三值（+ABORTED）与
enhanced_retry_count CHECK 分支化（ABORTED 允许 0-3——中止可发生在
任意 attempt 消耗后；终态两值维持 1-3）。
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None

_OLD_FINAL_STATUS = "final_status IN ('RECOVERED', 'MARKED_INFEASIBLE')"
_NEW_FINAL_STATUS = "final_status IN ('RECOVERED', 'MARKED_INFEASIBLE', 'ABORTED')"
_OLD_RETRY_RANGE = "enhanced_retry_count BETWEEN 1 AND 3"
_NEW_RETRY_RANGE = (
    "(final_status = 'ABORTED' AND enhanced_retry_count BETWEEN 0 AND 3)"
    " OR (final_status IN ('RECOVERED', 'MARKED_INFEASIBLE') AND enhanced_retry_count BETWEEN 1 AND 3)"
)


def upgrade() -> None:
    """CHECK 约束 swap（drop + add——既有终态行零影响）。"""
    op.drop_constraint("ck_tool_evolution_logs_final_status", "tool_evolution_logs", type_="check")
    op.create_check_constraint(
        "ck_tool_evolution_logs_final_status",
        "tool_evolution_logs",
        _NEW_FINAL_STATUS,
    )
    op.drop_constraint("ck_tool_evolution_logs_retry_count_range", "tool_evolution_logs", type_="check")
    op.create_check_constraint(
        "ck_tool_evolution_logs_retry_count_range",
        "tool_evolution_logs",
        _NEW_RETRY_RANGE,
    )


def downgrade() -> None:
    """回滚约束（存在 ABORTED 行时回滚将被 CHECK 拒绝——需先清理中止行）。"""
    op.drop_constraint("ck_tool_evolution_logs_retry_count_range", "tool_evolution_logs", type_="check")
    op.create_check_constraint(
        "ck_tool_evolution_logs_retry_count_range",
        "tool_evolution_logs",
        _OLD_RETRY_RANGE,
    )
    op.drop_constraint("ck_tool_evolution_logs_final_status", "tool_evolution_logs", type_="check")
    op.create_check_constraint(
        "ck_tool_evolution_logs_final_status",
        "tool_evolution_logs",
        _OLD_FINAL_STATUS,
    )
