"""Story 4.4: Alembic migration 015 sandbox_sessions 静态断言测试

对齐 001 先例(test_integration_postgresql.py)的静态文本断言形态。
完整执行型 round-trip(upgrade 015 → downgrade 014)登记为后续改进项,
可复用 tests/acceptance/test_acceptance_postgresql_relational_layer.py 的
ensure_alembic_migration fixture(subprocess alembic + 测试 schema 隔离)。
"""

from __future__ import annotations

from pathlib import Path

_MIGRATION = Path(__file__).parents[2] / "deploy" / "postgresql" / "alembic" / "versions" / "015_sandbox_sessions.py"


class TestMigration015SandboxSessions:
    """migration 015 静态断言(AC-4 验证项)"""

    def test_migration_file_exists(self) -> None:
        """015_sandbox_sessions.py 应存在"""
        assert _MIGRATION.exists()

    def test_revision_chain(self) -> None:
        """revision=015 + down_revision=014(数字 ID 链)"""
        content = _MIGRATION.read_text()
        assert 'revision = "015"' in content or "revision = '015'" in content
        assert 'down_revision = "014"' in content or "down_revision = '014'" in content

    def test_upgrade_creates_sandbox_sessions_table(self) -> None:
        """upgrade 应创建 sandbox_sessions 表 + 3 索引"""
        content = _MIGRATION.read_text()
        upgrade_part = content.split("def downgrade()")[0]
        assert "def upgrade()" in content
        assert "op.create_table(" in upgrade_part and '"sandbox_sessions"' in upgrade_part
        assert upgrade_part.count("op.create_index") == 3
        # 复合索引 (tenant_id, state) + (state, last_activity_at) + container_id UNIQUE 部分索引
        assert "tenant_id" in upgrade_part and "state" in upgrade_part
        assert "last_activity_at" in upgrade_part
        assert "container_id" in upgrade_part

    def test_downgrade_drops_table(self) -> None:
        """downgrade 应 drop 3 索引 + sandbox_sessions 表(round-trip 可回滚)"""
        content = _MIGRATION.read_text()
        assert "def downgrade()" in content
        assert content.count("op.drop_index") == 3
        assert 'op.drop_table("sandbox_sessions"' in content
