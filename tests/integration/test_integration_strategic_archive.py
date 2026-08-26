"""战略档案集成测试

验证真实 PG 仓储 CRUD + StrategicArchiveService 多存储层协同。
使用真实 PostgreSQL（测试 schema 隔离 + savepoint rollback）。
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.config.postgresql import PostgreSQLConfig
from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session
from tests.environments import get_test_env

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def event_loop():
    """模块级事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def pg_config() -> PostgreSQLConfig:
    """真实 PostgreSQL 配置"""
    env = get_test_env()
    return PostgreSQLConfig(
        host=env.postgres.host,
        port=env.postgres.port,
        database=env.postgres.database,
        username=env.postgres.username,
        password=env.postgres.password,
        pool_size=5,
        max_overflow=10,
    )


@pytest.fixture
def db_engine(pg_config: PostgreSQLConfig) -> PostgreSQLManager:
    """真实数据库引擎"""
    return PostgreSQLManager(pg_config)


@pytest.fixture
def pg_available(pg_config: PostgreSQLConfig, event_loop) -> bool:
    """检查 PostgreSQL 是否可用"""
    import asyncpg

    async def _check():
        try:
            conn = await asyncpg.connect(
                host=pg_config.host,
                port=pg_config.port,
                user=pg_config.username,
                password=pg_config.password,
                database=pg_config.database,
            )
            await conn.close()
            return True
        except Exception:
            return False

    result: bool = event_loop.run_until_complete(_check())
    return result


@pytest.fixture
def repo_session(
    db_engine: PostgreSQLManager,
    pg_available: bool,
    event_loop,
) -> Generator[AsyncSession, None, None]:
    """真实 PG 会话（savepoint rollback 隔离）"""
    if not pg_available:
        pytest.skip("PostgreSQL not available")
        return

    # 确保表结构存在
    try:
        from src.infrastructure.storage.postgresql.models import Base

        Base.metadata.create_all(db_engine.get_sync_engine())
    except Exception:
        pass

    async_engine = db_engine.get_async_engine()
    session = AsyncSession(async_engine)
    event_loop.run_until_complete(session.begin())
    token = set_session(session)
    yield session
    reset_session(token)
    event_loop.run_until_complete(session.rollback())
    event_loop.run_until_complete(session.close())


def _run(coro):
    """同步运行 async 协程"""
    return asyncio.run(coro)


class TestArchivePersistence:
    """档案存储集成测试（真实 PG）"""

    def test_crud_roundtrip(self, repo_session, event_loop):
        """档案 CRUD 端到端"""
        from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive
        from src.infrastructure.storage.postgresql.repository.archive_repository import (
            PostgreSQLArchiveRepository,
        )

        repo = PostgreSQLArchiveRepository()
        plan_id = uuid.uuid4()

        # Create
        archive = StrategicArchive(
            archive_id=uuid.uuid4(),
            plan_id=plan_id,
            plan_type="SP",
            archive_type=ArchiveType.ASSUMPTION,
            assumptions={"market": "grow"},
            decision_basis={"method": "A"},
            execution_deviation={},
            metadata_ref=f"strategic_archives:{plan_id}",
            created_at=datetime.now(UTC),
            archived_at=datetime.now(UTC),
        )
        saved = event_loop.run_until_complete(repo.save(archive))
        assert saved.archive_id == archive.archive_id

        # Get by ID
        fetched = event_loop.run_until_complete(repo.get_by_id(archive.archive_id))
        assert fetched is not None
        assert fetched.plan_id == plan_id
        assert fetched.assumptions == {"market": "grow"}
        assert fetched.archive_type == ArchiveType.ASSUMPTION

        # Find by query
        from src.domain.ports.archive_repository import ArchiveQuery

        query = ArchiveQuery(plan_id=plan_id)
        results = event_loop.run_until_complete(repo.find(query))
        assert len(results) >= 1
        assert any(a.archive_id == archive.archive_id for a in results)

        # Count
        count = event_loop.run_until_complete(repo.count(query))
        assert count >= 1

        # List by plan
        by_plan = event_loop.run_until_complete(repo.list_by_plan(plan_id))
        assert len(by_plan) >= 1

        # Soft delete
        event_loop.run_until_complete(repo.delete(archive.archive_id))
        fetched = event_loop.run_until_complete(repo.get_by_id(archive.archive_id))
        assert fetched is None

    def test_list_by_archive_type(self, repo_session, event_loop):
        """按类型查询"""
        from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive
        from src.infrastructure.storage.postgresql.repository.archive_repository import (
            PostgreSQLArchiveRepository,
        )

        repo = PostgreSQLArchiveRepository()
        plan_id = uuid.uuid4()
        archive = StrategicArchive(
            archive_id=uuid.uuid4(),
            plan_id=plan_id,
            plan_type="SP",
            archive_type=ArchiveType.DECISION,
            assumptions={},
            decision_basis={"scenario": "A"},
            execution_deviation={},
            metadata_ref=f"strategic_archives:{plan_id}",
            created_at=datetime.now(UTC),
            archived_at=datetime.now(UTC),
        )
        event_loop.run_until_complete(repo.save(archive))

        results = event_loop.run_until_complete(repo.list_by_archive_type(ArchiveType.DECISION))
        assert len(results) >= 1
        assert any(a.archive_id == archive.archive_id for a in results)


class TestArchiveServiceIntegration:
    """StrategicArchiveService 集成测试（真实 PG + Mock 存储层）"""

    def test_archive_plan_with_mock_storage(self, repo_session, event_loop):
        """归档流程多存储层协同（Mock L3/L4/L5）"""
        from unittest.mock import AsyncMock

        from src.application.services.strategic_archive_service import StrategicArchiveService
        from src.domain.entities.strategic_archive import ArchiveType
        from src.domain.ports.event_publisher import EventPublisher
        from src.domain.ports.l3_vector import L3VectorPort
        from src.domain.ports.l4_object import L4ObjectPort
        from src.domain.ports.l5_graph import L5GraphPort
        from src.infrastructure.storage.postgresql.repository.archive_repository import (
            PostgreSQLArchiveRepository,
        )

        service = StrategicArchiveService(
            archive_repo=PostgreSQLArchiveRepository(),
            embedding_service=None,
            vector_storage=AsyncMock(spec=L3VectorPort),
            object_storage=AsyncMock(spec=L4ObjectPort),
            graph_storage=AsyncMock(spec=L5GraphPort),
            event_publisher=AsyncMock(spec=EventPublisher),
        )

        plan_id = uuid.uuid4()
        saved = event_loop.run_until_complete(
            service.archive_plan(
                plan_id=plan_id,
                plan_type="SP",
                assumptions={"market": "growing"},
                decision_basis={"method": "scenario"},
                execution_deviation={"revenue": -0.05},
                evidence_blob=b"evidence package content",
            )
        )
        assert saved is not None
        assert saved.plan_id == plan_id
        assert saved.archive_type == ArchiveType.ASSUMPTION
        assert saved.metadata_ref != ""
        assert saved.embedding_ref is not None
        assert saved.blob_ref is not None
        assert saved.graph_ref is not None

        # 验证已持久化
        from src.infrastructure.storage.postgresql.repository.archive_repository import (
            PostgreSQLArchiveRepository,
        )

        repo = PostgreSQLArchiveRepository()
        fetched = event_loop.run_until_complete(repo.get_by_id(saved.archive_id))
        assert fetched is not None
        assert fetched.assumptions == {"market": "growing"}
