"""Story 3.12 数据陈旧标记集成测试。

本文件新增于 Story 3.12，不修改 Story 3.11 的有效期集成测试。
使用真实 PostgreSQL；Qdrant/Neo4j/Rabbit 真实链路在外部服务专用测试中按可用性分层。
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.services.staleness_weight_service import StalenessWeightService
from src.application.services.strategic_archive_service import StrategicArchiveService
from src.application.services.summary_generation_service import SummaryGenerationService
from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive
from src.domain.ports.archive_repository import ArchiveQuery
from src.domain.ports.l3_vector import L3VectorPort, SearchResult
from src.domain.ports.llm_client import LLMClientPort
from src.infrastructure.config.postgresql import PostgreSQLConfig
from src.infrastructure.messaging.channel_router import ChannelRouter
from src.infrastructure.messaging.outbox.inmemory_outbox import InMemoryOutboxRepository
from src.infrastructure.messaging.rabbitmq_event_bus import RabbitMQEventBus
from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
from src.infrastructure.storage.postgresql.repository.archive_repository import PostgreSQLArchiveRepository
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session
from tests.environments import get_test_env


@pytest.fixture(scope="module")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """提供同步 BDD/集成风格兼容的事件循环。"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def pg_config() -> PostgreSQLConfig:
    """读取测试 PostgreSQL 配置。"""
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
    """创建真实数据库管理器。"""
    return PostgreSQLManager(pg_config)


@pytest.fixture
def pg_session(db_engine: PostgreSQLManager, event_loop: asyncio.AbstractEventLoop) -> Generator[AsyncSession, None, None]:
    """创建事务会话，测试结束 rollback。"""
    import asyncpg

    env = get_test_env()

    async def check() -> bool:
        try:
            connection = await asyncpg.connect(
                host=env.postgres.host,
                port=env.postgres.port,
                user=env.postgres.username,
                password=env.postgres.password,
                database=env.postgres.database,
            )
            await connection.close()
            return True
        except Exception:
            return False

    if not event_loop.run_until_complete(check()):
        pytest.skip(f"PostgreSQL unavailable at {env.postgres.host}:{env.postgres.port}")
    try:
        from src.infrastructure.storage.postgresql.models import Base

        Base.metadata.create_all(db_engine.get_sync_engine())
    except Exception as exc:
        pytest.skip(f"PostgreSQL schema unavailable: {exc}")
    session = AsyncSession(db_engine.get_async_engine())
    event_loop.run_until_complete(session.begin())
    token = set_session(session)
    yield session
    reset_session(token)
    event_loop.run_until_complete(session.rollback())
    event_loop.run_until_complete(session.close())


def _archive(**overrides: object) -> StrategicArchive:
    """创建唯一的集成测试档案。"""
    now = datetime.now(UTC)
    values: dict[str, Any] = {
        "archive_id": uuid4(),
        "plan_id": uuid4(),
        "plan_type": "SP",
        "archive_type": ArchiveType.ASSUMPTION,
        "metadata_ref": f"story-3-12-integration:{uuid4()}",
        "created_at": now,
        "archived_at": now,
    }
    values.update(overrides)
    return StrategicArchive(**values)


def _service() -> tuple[StrategicArchiveService, PostgreSQLArchiveRepository, InMemoryOutboxRepository]:
    """构建真实 L2 服务与可观测 Outbox。"""
    repo = PostgreSQLArchiveRepository()
    outbox = InMemoryOutboxRepository()
    publisher = RabbitMQEventBus(outbox_repository=outbox, router=ChannelRouter())
    return StrategicArchiveService(archive_repo=repo, event_publisher=publisher), repo, outbox


class TestDataStalenessPostgreSQL:
    """Story 3.12 L2、事件和降权兜底集成验证。"""

    def test_expired_reason_event_and_idempotency(
        self,
        pg_session: AsyncSession,
        event_loop: asyncio.AbstractEventLoop,
    ) -> None:
        """过期原因、事件和重复扫描幂等性。"""
        service, repo, outbox = _service()
        archive = _archive(valid_until=datetime(2020, 1, 1, tzinfo=UTC))
        event_loop.run_until_complete(repo.save(archive))

        marked = event_loop.run_until_complete(service.mark_stale_archives())
        assert [item.archive_id for item in marked] == [archive.archive_id]
        saved = event_loop.run_until_complete(repo.get_by_id(archive.archive_id))
        assert saved is not None
        assert saved.metadata["staleness"] == "stale"
        assert saved.metadata["stale_reason"] == "expired"
        assert saved.metadata["stale_since"]
        events = event_loop.run_until_complete(outbox.get_unpublished(1000))
        matching = [event for event in events if getattr(event, "archive_id", None) == str(archive.archive_id)]
        assert len(matching) == 1
        assert matching[0].event_type == "FactBecameStale"

        repeated = event_loop.run_until_complete(service.mark_stale_archives())
        assert not any(item.archive_id == archive.archive_id for item in repeated)

    def test_archived_too_long_reason(self, pg_session: AsyncSession, event_loop: asyncio.AbstractEventLoop) -> None:
        """没有有效期且归档超过 12 个月时使用 archived_too_long。"""
        service, repo, _ = _service()
        archive = _archive(valid_until=None, archived_at=datetime.now(UTC) - timedelta(days=400))
        event_loop.run_until_complete(repo.save(archive))
        event_loop.run_until_complete(service.mark_stale_archives())
        saved = event_loop.run_until_complete(repo.get_by_id(archive.archive_id))
        assert saved is not None
        assert saved.metadata["stale_reason"] == "archived_too_long"

    def test_staleness_status_filter_null_semantics(
        self,
        pg_session: AsyncSession,
        event_loop: asyncio.AbstractEventLoop,
    ) -> None:
        """fresh 过滤包含 metadata 缺失档案，stale 过滤只包含权威标记档案。"""
        repo = PostgreSQLArchiveRepository()
        fresh = _archive(metadata={})
        stale = _archive(metadata={"staleness": "stale", "stale_reason": "expired"})
        event_loop.run_until_complete(repo.save(fresh))
        event_loop.run_until_complete(repo.save(stale))

        stale_results = event_loop.run_until_complete(repo.find(ArchiveQuery(staleness_status="stale")))
        fresh_results = event_loop.run_until_complete(repo.find(ArchiveQuery(staleness_status="fresh")))
        assert stale.archive_id in {item.archive_id for item in stale_results}
        assert fresh.archive_id not in {item.archive_id for item in stale_results}
        assert stale.archive_id not in {item.archive_id for item in fresh_results}
        assert fresh.archive_id in {item.archive_id for item in fresh_results}

    def test_staleness_weight_service_uses_l2_fallback(
        self,
        pg_session: AsyncSession,
        event_loop: asyncio.AbstractEventLoop,
    ) -> None:
        """L3 缺少标记时通过真实 PG archive_repo 兜底降权。"""
        repo = PostgreSQLArchiveRepository()
        stale = _archive(valid_until=datetime(2020, 1, 1, tzinfo=UTC))
        event_loop.run_until_complete(repo.save(stale))
        service = StalenessWeightService(archive_repo=repo)
        result = SearchResult(
            id=f"strategic_archive:{stale.archive_id}",
            score=0.8,
            payload={"archive_id": str(stale.archive_id)},
        )
        weighted = event_loop.run_until_complete(service.apply_staleness_weight([result]))
        assert weighted[0]["score"] == pytest.approx(0.4)


class TestDataStalenessApplicationPorts:
    """无需外部基础设施的应用端口集成验证。"""

    @pytest.mark.usefixtures("pg_session")
    def test_summary_fallback_prompt_contains_staleness(
        self,
        pg_session: AsyncSession,
    ) -> None:
        """摘要服务在 L3 缺少标记时可以使用 archive_repo 兜底。"""
        repo = AsyncMock()
        archive_id = uuid4()
        archive = _archive(archive_id=archive_id, valid_until=datetime(2020, 1, 1, tzinfo=UTC))
        repo.find.return_value = [archive]
        llm = AsyncMock(spec=LLMClientPort)
        retrieval = AsyncMock()
        embedding = AsyncMock()
        vector = AsyncMock(spec=L3VectorPort)
        service = SummaryGenerationService(
            llm_client=llm,
            layered_retrieval=retrieval,
            embedding_service=embedding,
            l3_vector=vector,
            archive_repo=repo,
        )
        result = SearchResult(
            id=f"strategic_archive:{archive_id}",
            score=0.8,
            payload={"content": "历史内容", "archive_id": str(archive_id)},
        )
        # 该测试验证真实 SummaryGenerationService + 真实 StrategicArchive 实体判断；
        # LLM port 是外部边界，仅用于捕获 prompt，不替代被测服务。
        event_loop = asyncio.new_event_loop()
        try:
            event_loop.run_until_complete(service._prefetch_staleness([result]))
        finally:
            event_loop.close()
        context = service._build_search_context([result])
        assert "数据陈旧" in context
        assert "历史内容" in context
