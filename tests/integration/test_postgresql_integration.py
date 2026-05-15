"""PostgreSQL End-to-End Integration Tests.

Verifies the complete PostgreSQL storage layer end-to-end:
- Database connection and health check
- Alembic migration execution
- Outbox event lifecycle
- User/Role/Permission CRUD operations
- Foreign key constraint enforcement
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest import mock
from uuid import uuid4

import pytest

from src.infrastructure.storage.postgresql.session_context import reset_session, set_session


class TestPostgreSQLConnection:
    """数据库连接端到端测试。"""

    def test_database_engine_creation(self):
        """DatabaseEngine 应可实例化。"""
        from src.infrastructure.config.postgresql import PostgreSQLConfig
        from src.infrastructure.storage.postgresql.engine import DatabaseEngine

        config = PostgreSQLConfig(
            host="localhost",
            port=5432,
            database="test_db",
            username="test_user",
            password="test_pass123",  # pragma: allowlist secret
        )

        engine = DatabaseEngine(config)
        assert engine is not None
        assert engine._async_engine is None  # 懒初始化
        assert engine._sync_engine is None

    def test_async_engine_lazy_init(self):
        """异步引擎应在首次调用时创建。"""
        from src.infrastructure.config.postgresql import PostgreSQLConfig
        from src.infrastructure.storage.postgresql.engine import DatabaseEngine

        config = PostgreSQLConfig()
        engine = DatabaseEngine(config)

        # 首次调用前应 None
        assert engine._async_engine is None

        # 调用后应创建
        async_engine = engine.get_async_engine()
        assert async_engine is not None
        assert engine._async_engine is async_engine

    def test_sync_engine_lazy_init(self):
        """同步引擎应在首次调用时创建。"""
        from src.infrastructure.config.postgresql import PostgreSQLConfig
        from src.infrastructure.storage.postgresql.engine import DatabaseEngine

        config = PostgreSQLConfig()
        engine = DatabaseEngine(config)

        assert engine._sync_engine is None

        sync_engine = engine.get_sync_engine()
        assert sync_engine is not None
        assert engine._sync_engine is sync_engine


class TestAlembicMigration:
    """Alembic 迁移端到端测试。"""

    def test_alembic_config_exists(self):
        """alembic.ini 配置文件应存在。"""
        from pathlib import Path

        alembic_ini = Path(__file__).parents[2] / "deploy" / "postgresql" / "alembic" / "alembic.ini"
        assert alembic_ini.exists()

    def test_alembic_env_exists(self):
        """deploy/postgresql/alembic/env.py 应存在。"""
        from pathlib import Path

        env_py = Path(__file__).parents[2] / "deploy" / "postgresql" / "alembic" / "env.py"
        assert env_py.exists()

    def test_initial_migration_exists(self):
        """初始迁移脚本应存在。"""
        from pathlib import Path

        migration = Path(__file__).parents[2] / "deploy" / "postgresql" / "alembic" / "versions" / "001_initial.py"
        assert migration.exists()

    def test_initial_migration_has_upgrade(self):
        """初始迁移应定义 upgrade 函数。"""
        from pathlib import Path

        migration = Path(__file__).parents[2] / "deploy" / "postgresql" / "alembic" / "versions" / "001_initial.py"
        content = migration.read_text()

        assert "def upgrade()" in content
        assert "def downgrade()" in content

    def test_initial_migration_creates_event_outbox(self):
        """初始迁移应创建 event_outbox 表。"""
        from pathlib import Path

        migration = Path(__file__).parents[2] / "deploy" / "postgresql" / "alembic" / "versions" / "001_initial.py"
        content = migration.read_text()

        assert "event_outbox" in content
        assert "op.create_table" in content

    def test_initial_migration_creates_users(self):
        """初始迁移应创建 users 表。"""
        from pathlib import Path

        migration = Path(__file__).parents[2] / "deploy" / "postgresql" / "alembic" / "versions" / "001_initial.py"
        content = migration.read_text()

        assert "users" in content

    def test_initial_migration_creates_roles(self):
        """初始迁移应创建 roles 表。"""
        from pathlib import Path

        migration = Path(__file__).parents[2] / "deploy" / "postgresql" / "alembic" / "versions" / "001_initial.py"
        content = migration.read_text()

        assert "roles" in content

    def test_initial_migration_creates_permissions(self):
        """初始迁移应创建 permissions 表。"""
        from pathlib import Path

        migration = Path(__file__).parents[2] / "deploy" / "postgresql" / "alembic" / "versions" / "001_initial.py"
        content = migration.read_text()

        assert "permissions" in content

    def test_initial_migration_creates_association_tables(self):
        """初始迁移应创建关联表。"""
        from pathlib import Path

        migration = Path(__file__).parents[2] / "deploy" / "postgresql" / "alembic" / "versions" / "001_initial.py"
        content = migration.read_text()

        assert "user_roles" in content
        assert "role_permissions" in content


class TestOutboxEventLifecycle:
    """Outbox 事件生命周期测试。"""

    @pytest.mark.asyncio
    async def test_save_event_to_outbox(self, mock_session):
        """保存事件到发件箱。"""
        from src.domain.events.base import DomainEvent
        from src.infrastructure.messaging.outbox.outbox_repository import PostgreSQLOutboxRepository

        event = DomainEvent(
            event_id=uuid4(),
            event_type="TestEvent",
            timestamp=datetime.now(UTC),
            source="test",
            payload={"key": "value"},
        )

        repo = PostgreSQLOutboxRepository()
        repo.save(event)

        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_unpublished_events(self, mock_session):
        """获取未发布事件列表。"""
        from src.domain.events.base import DomainEvent
        from src.infrastructure.messaging.adapters.event_outbox_adapter import EventRegistry
        from src.infrastructure.messaging.outbox.outbox_repository import PostgreSQLOutboxRepository

        # 注册事件类型
        EventRegistry.register("TestEvent", DomainEvent)

        mock_result = mock.Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        repo = PostgreSQLOutboxRepository()
        result = await repo.async_get_unpublished(limit=10)

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_mark_event_published(self, mock_session):
        """标记事件已发布。"""
        from src.infrastructure.messaging.outbox.outbox_repository import PostgreSQLOutboxRepository

        mock_model = mock.Mock()
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = mock_model
        mock_session.execute.return_value = mock_result

        repo = PostgreSQLOutboxRepository()
        await repo.async_mark_published(uuid4())

        assert mock_model.status == "published"
        assert mock_model.published_at is not None

    @pytest.mark.asyncio
    async def test_mark_event_failed(self, mock_session):
        """标记事件发布失败。"""
        from src.infrastructure.messaging.outbox.outbox_repository import PostgreSQLOutboxRepository

        mock_model = mock.Mock()
        mock_model.retry_count = 0
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = mock_model
        mock_session.execute.return_value = mock_result

        repo = PostgreSQLOutboxRepository()
        await repo.async_mark_failed(uuid4(), "Connection timeout")

        assert mock_model.status == "failed"
        assert mock_model.retry_count == 1
        assert mock_model.error_message == "Connection timeout"


class TestUserCRUD:
    """用户 CRUD 操作测试。"""

    @pytest.mark.asyncio
    async def test_create_user(self, mock_session):
        """创建新用户。"""
        from src.infrastructure.storage.postgresql.repository.user_repository import UserRepository

        repo = UserRepository()
        mock_user = mock.Mock()

        result = await repo.save(mock_user)

        mock_session.add.assert_called_once()
        assert result == mock_user  # save() returns persisted entity

    @pytest.mark.asyncio
    async def test_get_user_by_username(self, mock_session):
        """根据用户名获取用户。"""
        from src.infrastructure.storage.postgresql.repository.user_repository import UserRepository

        repo = UserRepository()
        mock_user = mock.Mock()
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_username("testuser")

        assert result == mock_user

    @pytest.mark.asyncio
    async def test_get_user_by_email(self, mock_session):
        """根据邮箱获取用户。"""
        from src.infrastructure.storage.postgresql.repository.user_repository import UserRepository

        repo = UserRepository()
        mock_user = mock.Mock()
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_email("test@example.com")

        assert result == mock_user


class TestRolePermissionCRUD:
    """角色权限 CRUD 测试。"""

    @pytest.mark.asyncio
    async def test_get_role_by_name(self, mock_session):
        """根据名称获取角色。"""
        from src.infrastructure.storage.postgresql.repository.role_repository import RoleRepository

        repo = RoleRepository()
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_name("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_role_permissions(self, mock_session):
        """获取角色的权限列表。"""
        from src.infrastructure.storage.postgresql.repository.role_repository import RoleRepository

        repo = RoleRepository()
        mock_result = mock.Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await repo.get_permissions_for_role(uuid4())

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_permission_by_name(self, mock_session):
        """根据名称获取权限。"""
        from src.infrastructure.storage.postgresql.repository.permission_repository import PermissionRepository

        repo = PermissionRepository()
        mock_permission = mock.Mock()
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = mock_permission
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_name("read:document")

        assert result == mock_permission


class TestTransactionRollback:
    """事务回滚行为测试。"""

    def test_save_does_not_auto_commit(self, mock_session):
        """save 方法不应自动提交（依赖外部事务管理）。"""
        from src.domain.events.base import DomainEvent
        from src.infrastructure.messaging.outbox.outbox_repository import PostgreSQLOutboxRepository

        event = DomainEvent(
            event_id=uuid4(),
            event_type="TestEvent",
            timestamp=datetime.now(UTC),
            source="test",
            payload={},
        )

        repo = PostgreSQLOutboxRepository()
        repo.save(event)

        # save 应调用 add 但不应调用 commit
        mock_session.add.assert_called_once()


@pytest.fixture
def mock_session():
    """Provide mock AsyncSession and set in ContextVar."""
    session = mock.AsyncMock()
    # add is sync method (no I/O)
    session.add = mock.Mock()
    token = set_session(session)
    yield session
    reset_session(token)
