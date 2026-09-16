"""Add GIN index on violations JSONB column for Story 4.3 Round 2.

Revision ID: 014
Revises: 013
Create Date: 2026-09-16

Story 4.3 Round 2: 4.6 工具版本管理与 4.7 Validation Feedback 订阅场景下,
按 violations JSONB 内具体字段查询(如 path、expected)时,缺 GIN 索引导致全表扫描。
本迁移添加 GIN 索引(对标 PostgreSQL JSONB 最佳实践)。

CLAUDE.md §5 硬约束:已合入 migration 禁止修改,本迁移为新增 014,不修改 013。

设计决策:
- GIN 索引 vs BTREE:JSONB 内 nested fields(数组、对象)的高频查询必须用 GIN
- 选择 jsonb_path_ops 操作符类(比 default 节省 ~30% 空间,代价是不支持 ?/?? 操作符)
- 仅针对 violations 列,其他 JSONB 列暂不需要

参考:
- PostgreSQL 文档: https://www.postgresql.org/docs/current/datatype-json.html#JSON-INDEXING
- 业界实践: AWS RDS / Confluent Schema Registry / Stripe payments 表
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """添加 violations JSONB 列的 GIN 索引

    jsonb_path_ops 操作符类支持:
    - @> (contains)
    - <@ (contained by)
    - @@ (jsonpath match)
    不支持 ?/?? 等存在性操作符(本 Story 不需要)
    """
    op.create_index(
        "ix_schema_validation_records_violations_gin",
        "schema_validation_records",
        ["violations"],
        postgresql_using="gin",
        postgresql_ops={"violations": "jsonb_path_ops"},
    )


def downgrade() -> None:
    """回滚 GIN 索引"""
    op.drop_index(
        "ix_schema_validation_records_violations_gin",
        table_name="schema_validation_records",
    )
