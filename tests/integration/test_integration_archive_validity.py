"""档案有效期管理集成测试

验证有效期管理核心链路（有效期设置 + 时间轴查询 + 陈旧标记）在真实 PostgreSQL 上的行为。
遵循项目测试隔离约束：
- 真实服务优先（PostgreSQLArchiveRepository + StrategicArchiveService 真实实例）
- 真实 EventPublisher（RabbitMQEventBus + InMemoryOutboxRepository，"纯基础设施，无安全清理"）
- 真实服务 Schema 隔离（独立 PG schema + savepoint rollback）
- 禁止手动 delete/truncate
- 外部 L3/L4/L5 存储层使用 Mock 工厂模式（有效期方法不涉及这些层）
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.services.strategic_archive_service import StrategicArchiveService
from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive
from src.domain.exceptions.archive_exceptions import ValidityPeriodConflictError
from src.domain.ports.archive_repository import ArchiveQuery, ValidityStatus
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.l3_vector import L3VectorPort
from src.domain.ports.l4_object import L4ObjectPort
from src.domain.ports.l5_graph import L5GraphPort
from src.infrastructure.config.postgresql import PostgreSQLConfig
from src.infrastructure.messaging.channel_router import ChannelRouter
from src.infrastructure.messaging.outbox.inmemory_outbox import InMemoryOutboxRepository
from src.infrastructure.messaging.rabbitmq_event_bus import RabbitMQEventBus
from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
from src.infrastructure.storage.postgresql.repository.archive_repository import (
    PostgreSQLArchiveRepository,
)
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


def _make_archive(overrides: dict | None = None) -> StrategicArchive:
    """创建测试用档案实体"""
    archive_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    archive = StrategicArchive(
        archive_id=archive_id,
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
    if overrides:
        for key, value in overrides.items():
            setattr(archive, key, value)
    return archive


def _make_event_publisher() -> RabbitMQEventBus:
    """创建真实 EventPublisher（RabbitMQEventBus + InMemoryOutboxRepository）

    RELIABLE 模式事件通过 Outbox 持久化（RabbitMQ 可靠通道）。
    InMemoryOutboxRepository 提供 get_unpublished() 供测试直接验证事件持久化。
    """
    router = ChannelRouter()
    outbox = InMemoryOutboxRepository()
    return RabbitMQEventBus(outbox_repository=outbox, router=router)


def _make_service(event_publisher: EventPublisher | None = None) -> StrategicArchiveService:
    """创建真实仓储 + 真实 EventPublisher + Mock 外部存储层的服务"""
    return StrategicArchiveService(
        archive_repo=PostgreSQLArchiveRepository(),
        embedding_service=None,
        vector_storage=AsyncMock(spec=L3VectorPort),
        object_storage=AsyncMock(spec=L4ObjectPort),
        graph_storage=AsyncMock(spec=L5GraphPort),
        event_publisher=event_publisher or _make_event_publisher(),
    )


class TestValidityPeriodPersistence:
    """有效期字段持久化集成测试（真实 PG）"""

    def test_save_and_fetch_validity_period(self, repo_session, event_loop) -> None:
        """保存并获取含有效期字段的档案"""
        repo = PostgreSQLArchiveRepository()
        vf = datetime(2026, 1, 1, tzinfo=UTC)
        vu = datetime(2027, 12, 31, tzinfo=UTC)
        archive = _make_archive({"valid_from": vf, "valid_until": vu})
        saved = event_loop.run_until_complete(repo.save(archive))
        assert saved.valid_from == vf
        assert saved.valid_until == vu

        fetched = event_loop.run_until_complete(repo.get_by_id(archive.archive_id))
        assert fetched is not None
        assert fetched.valid_from == vf
        assert fetched.valid_until == vu

    def test_save_missing_validity_period(self, repo_session, event_loop) -> None:
        """有效期字段为 None 时保存与获取"""
        repo = PostgreSQLArchiveRepository()
        archive = _make_archive({"valid_from": None, "valid_until": None})
        saved = event_loop.run_until_complete(repo.save(archive))
        assert saved.valid_from is None
        assert saved.valid_until is None

        fetched = event_loop.run_until_complete(repo.get_by_id(archive.archive_id))
        assert fetched is not None
        assert fetched.valid_from is None
        assert fetched.valid_until is None


class TestValidityQuery:
    """有效期查询集成测试（真实 PG）"""

    def test_query_by_valid_from_range(self, repo_session, event_loop) -> None:
        """按 valid_from 范围过滤查询"""
        repo = PostgreSQLArchiveRepository()
        plan_id = uuid.uuid4()
        target = _make_archive(
            {
                "plan_id": plan_id,
                "valid_from": datetime(2026, 1, 1, tzinfo=UTC),
                "valid_until": datetime(2026, 12, 31, tzinfo=UTC),
            }
        )
        other1 = _make_archive(
            {
                "plan_id": plan_id,
                "valid_from": datetime(2025, 1, 1, tzinfo=UTC),
                "valid_until": datetime(2025, 6, 30, tzinfo=UTC),
            }
        )
        other2 = _make_archive(
            {
                "plan_id": plan_id,
                "valid_from": datetime(2027, 1, 1, tzinfo=UTC),
                "valid_until": datetime(2027, 6, 30, tzinfo=UTC),
            }
        )
        for a in (target, other1, other2):
            event_loop.run_until_complete(repo.save(a))

        query = ArchiveQuery(
            plan_id=plan_id,
            valid_from=datetime(2026, 6, 1, tzinfo=UTC),
        )
        results = event_loop.run_until_complete(repo.find(query))
        # valid_from >= 2026-06-01 时，只有 other2（2027-01-01 起）符合
        # target（2026-01-01）和 other1（2025-01-01）不满足条件
        assert any(a.archive_id == other2.archive_id for a in results)
        assert not any(a.archive_id == target.archive_id for a in results)
        assert not any(a.archive_id == other1.archive_id for a in results)

    def test_query_by_valid_until_range(self, repo_session, event_loop) -> None:
        """按 valid_until 范围过滤查询"""
        repo = PostgreSQLArchiveRepository()
        plan_id = uuid.uuid4()
        target = _make_archive(
            {
                "plan_id": plan_id,
                "valid_from": datetime(2026, 1, 1, tzinfo=UTC),
                "valid_until": datetime(2026, 12, 31, tzinfo=UTC),
            }
        )
        event_loop.run_until_complete(repo.save(target))

        query = ArchiveQuery(
            plan_id=plan_id,
            valid_until=datetime(2027, 6, 1, tzinfo=UTC),
        )
        results = event_loop.run_until_complete(repo.find(query))
        assert any(a.archive_id == target.archive_id for a in results)

    def test_query_by_validity_status_valid(self, repo_session, event_loop) -> None:
        """按有效性状态过滤（valid）"""
        repo = PostgreSQLArchiveRepository()
        plan_id = uuid.uuid4()
        # 有效档案：当前时间在有效期内
        valid = _make_archive(
            {
                "plan_id": plan_id,
                "valid_from": datetime(2020, 1, 1, tzinfo=UTC),
                "valid_until": datetime(2099, 12, 31, tzinfo=UTC),
            }
        )
        # 过期档案
        expired = _make_archive(
            {
                "plan_id": plan_id,
                "valid_from": datetime(2020, 1, 1, tzinfo=UTC),
                "valid_until": datetime(2021, 1, 1, tzinfo=UTC),
            }
        )
        # 永久有效（两者均为 None）
        permanent = _make_archive(
            {
                "plan_id": plan_id,
                "valid_from": None,
                "valid_until": None,
            }
        )
        for a in (valid, expired, permanent):
            event_loop.run_until_complete(repo.save(a))

        query = ArchiveQuery(
            plan_id=plan_id,
            validity_status=ValidityStatus.VALID,
        )
        results = event_loop.run_until_complete(repo.find(query))
        assert any(a.archive_id == valid.archive_id for a in results)
        assert any(a.archive_id == permanent.archive_id for a in results)
        assert not any(a.archive_id == expired.archive_id for a in results)

    def test_query_by_validity_status_expired(self, repo_session, event_loop) -> None:
        """按有效性状态过滤（expired）"""
        repo = PostgreSQLArchiveRepository()
        plan_id = uuid.uuid4()
        expired = _make_archive(
            {
                "plan_id": plan_id,
                "valid_from": datetime(2020, 1, 1, tzinfo=UTC),
                "valid_until": datetime(2021, 1, 1, tzinfo=UTC),
            }
        )
        valid = _make_archive(
            {
                "plan_id": plan_id,
                "valid_from": datetime(2020, 1, 1, tzinfo=UTC),
                "valid_until": datetime(2099, 12, 31, tzinfo=UTC),
            }
        )
        for a in (expired, valid):
            event_loop.run_until_complete(repo.save(a))

        query = ArchiveQuery(
            plan_id=plan_id,
            validity_status=ValidityStatus.EXPIRED,
        )
        results = event_loop.run_until_complete(repo.find(query))
        assert any(a.archive_id == expired.archive_id for a in results)
        assert not any(a.archive_id == valid.archive_id for a in results)

    def test_query_validity_params_compatible_with_existing(self, repo_session, event_loop) -> None:
        """有效期过滤与现有 plan_id/archive_type 组合兼容"""
        repo = PostgreSQLArchiveRepository()
        plan_id = uuid.uuid4()
        target = _make_archive(
            {
                "plan_id": plan_id,
                "archive_type": ArchiveType.DECISION,
                "valid_from": datetime(2026, 1, 1, tzinfo=UTC),
                "valid_until": datetime(2026, 12, 31, tzinfo=UTC),
            }
        )
        other_type = _make_archive(
            {
                "plan_id": plan_id,
                "archive_type": ArchiveType.ASSUMPTION,
                "valid_from": datetime(2026, 1, 1, tzinfo=UTC),
                "valid_until": datetime(2026, 12, 31, tzinfo=UTC),
            }
        )
        for a in (target, other_type):
            event_loop.run_until_complete(repo.save(a))

        query = ArchiveQuery(
            plan_id=plan_id,
            archive_type=ArchiveType.DECISION,
            valid_from=datetime(2025, 1, 1, tzinfo=UTC),
            valid_until=datetime(2029, 12, 31, tzinfo=UTC),
        )
        results = event_loop.run_until_complete(repo.find(query))
        assert any(a.archive_id == target.archive_id for a in results)
        assert not any(a.archive_id == other_type.archive_id for a in results)


class TestSetValidityPeriodIntegration:
    """set_validity_period 集成测试（真实 PG + 真实 EventPublisher）"""

    def test_set_validity_period_roundtrip(self, repo_session, event_loop) -> None:
        """设置有效期并持久化到真实 PG，事件写入 Outbox"""
        service = _make_service()
        archive = _make_archive()
        event_loop.run_until_complete(service._archive_repo.save(archive))

        vf = datetime(2026, 1, 1, tzinfo=UTC)
        vu = datetime(2027, 12, 31, tzinfo=UTC)
        updated = event_loop.run_until_complete(service.set_validity_period(archive.archive_id, vf, vu))
        assert updated.valid_from == vf
        assert updated.valid_until == vu

        # 验证持久化
        fetched = event_loop.run_until_complete(service._archive_repo.get_by_id(archive.archive_id))
        assert fetched is not None
        assert fetched.valid_from == vf
        assert fetched.valid_until == vu

        # 验证事件已写入 Outbox（真实 EventPublisher 路径）
        event_publisher = service._event_publisher
        assert isinstance(event_publisher, RabbitMQEventBus)
        outbox = event_publisher._outbox_repo
        assert isinstance(outbox, InMemoryOutboxRepository)
        unpublished = event_loop.run_until_complete(outbox.get_unpublished(100))
        assert any(e.event_type == "ValidityPeriodSet" for e in unpublished)
        stale_events = [e for e in unpublished if e.event_type == "ValidityPeriodSet"]
        assert len(stale_events) == 1
        assert stale_events[0].archive_id == str(archive.archive_id)

    def test_set_validity_period_overwrite(self, repo_session, event_loop) -> None:
        """有效期可被覆盖更新"""
        service = _make_service()
        archive = _make_archive(
            {
                "valid_from": datetime(2026, 1, 1, tzinfo=UTC),
                "valid_until": datetime(2026, 12, 31, tzinfo=UTC),
            }
        )
        event_loop.run_until_complete(service._archive_repo.save(archive))

        new_vf = datetime(2027, 1, 1, tzinfo=UTC)
        new_vu = datetime(2028, 12, 31, tzinfo=UTC)
        updated = event_loop.run_until_complete(service.set_validity_period(archive.archive_id, new_vf, new_vu))
        assert updated.valid_from == new_vf
        assert updated.valid_until == new_vu


class TestValidityConflictIntegration:
    """有效期冲突检测集成测试（真实 PG）"""

    def test_conflict_detected_same_plan_type(self, repo_session, event_loop) -> None:
        """同一 plan_id + archive_type 下有效期重叠抛出冲突"""
        service = _make_service()
        plan_id = uuid.uuid4()
        # 既有档案：有效期为 2026-01-01 到 2026-12-31
        existing = _make_archive(
            {
                "plan_id": plan_id,
                "valid_from": datetime(2026, 1, 1, tzinfo=UTC),
                "valid_until": datetime(2026, 12, 31, tzinfo=UTC),
            }
        )
        event_loop.run_until_complete(service._archive_repo.save(existing))

        # 新区间与既有区间重叠：2026-06-01 到 2027-06-01
        conflicting = _make_archive({"plan_id": plan_id})
        event_loop.run_until_complete(service._archive_repo.save(conflicting))

        with pytest.raises(ValidityPeriodConflictError):
            event_loop.run_until_complete(
                service.set_validity_period(
                    conflicting.archive_id,
                    datetime(2026, 6, 1, tzinfo=UTC),
                    datetime(2027, 6, 1, tzinfo=UTC),
                )
            )

    def test_adjacent_periods_no_conflict(self, repo_session, event_loop) -> None:
        """端点相接（半开区间）不视为冲突"""
        service = _make_service()
        plan_id = uuid.uuid4()
        # 既有档案：valid_until = 2026-01-01
        existing = _make_archive(
            {
                "plan_id": plan_id,
                "valid_from": datetime(2025, 1, 1, tzinfo=UTC),
                "valid_until": datetime(2026, 1, 1, tzinfo=UTC),
            }
        )
        event_loop.run_until_complete(service._archive_repo.save(existing))

        # 新区间：valid_from = 2026-01-01（恰好相接，不重叠）
        adjacent = _make_archive({"plan_id": plan_id})
        event_loop.run_until_complete(service._archive_repo.save(adjacent))

        updated = event_loop.run_until_complete(
            service.set_validity_period(
                adjacent.archive_id,
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2027, 6, 1, tzinfo=UTC),
            )
        )
        assert updated.valid_from == datetime(2026, 1, 1, tzinfo=UTC)

    def test_no_conflict_with_self(self, repo_session, event_loop) -> None:
        """不与自身冲突"""
        service = _make_service()
        archive = _make_archive({"valid_from": None, "valid_until": None})
        event_loop.run_until_complete(service._archive_repo.save(archive))

        updated = event_loop.run_until_complete(
            service.set_validity_period(
                archive.archive_id,
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2027, 12, 31, tzinfo=UTC),
            )
        )
        assert updated.valid_from == datetime(2026, 1, 1, tzinfo=UTC)


class TestMarkStaleIntegration:
    """陈旧标记集成测试（真实 PG + 真实 EventPublisher）"""

    def test_mark_expired_archive(self, repo_session, event_loop) -> None:
        """标记过期档案为陈旧，事件写入 Outbox"""
        service = _make_service()

        expired = _make_archive({"valid_until": datetime(2021, 1, 1, tzinfo=UTC)})
        valid = _make_archive({"valid_until": datetime(2099, 12, 31, tzinfo=UTC)})
        for a in (expired, valid):
            event_loop.run_until_complete(service._archive_repo.save(a))

        marked = event_loop.run_until_complete(service.mark_stale_archives())
        # 仅过期档案被标记
        assert any(a.archive_id == expired.archive_id for a in marked)
        assert not any(a.archive_id == valid.archive_id for a in marked)

        # 验证持久化的 metadata 标记
        fetched = event_loop.run_until_complete(service._archive_repo.get_by_id(expired.archive_id))
        assert fetched is not None
        assert fetched.metadata.get("staleness") == "stale"
        assert "stale_since" in fetched.metadata

        # 验证事件已写入 Outbox（真实 EventPublisher 路径）
        event_publisher = service._event_publisher
        assert isinstance(event_publisher, RabbitMQEventBus)
        outbox = event_publisher._outbox_repo
        assert isinstance(outbox, InMemoryOutboxRepository)
        unpublished = event_loop.run_until_complete(outbox.get_unpublished(100))
        fact_events = [e for e in unpublished if e.event_type == "FactBecameStale"]
        assert any(e.stale_reason == "expired" for e in fact_events)

    def test_mark_archived_too_long(self, repo_session, event_loop) -> None:
        """标记归档超 12 个月且未设置有效期的档案为陈旧"""
        service = _make_service()

        old = _make_archive(
            {
                "valid_until": None,
                "archived_at": datetime.now(UTC) - timedelta(days=400),
            }
        )
        recent = _make_archive(
            {
                "valid_until": None,
                "archived_at": datetime.now(UTC) - timedelta(days=30),
            }
        )
        for a in (old, recent):
            event_loop.run_until_complete(service._archive_repo.save(a))

        marked = event_loop.run_until_complete(service.mark_stale_archives())
        assert any(a.archive_id == old.archive_id for a in marked)
        assert not any(a.archive_id == recent.archive_id for a in marked)

        # 验证事件已写入 Outbox
        event_publisher = service._event_publisher
        assert isinstance(event_publisher, RabbitMQEventBus)
        outbox = event_publisher._outbox_repo
        assert isinstance(outbox, InMemoryOutboxRepository)
        unpublished = event_loop.run_until_complete(outbox.get_unpublished(100))
        fact_events = [e for e in unpublished if e.event_type == "FactBecameStale"]
        assert any(e.stale_reason == "archived_too_long" for e in fact_events)

    def test_mark_stale_idempotent(self, repo_session, event_loop) -> None:
        """陈旧标记幂等：重复执行不重复标记"""
        service = _make_service()

        expired = _make_archive({"valid_until": datetime(2021, 1, 1, tzinfo=UTC)})
        event_loop.run_until_complete(service._archive_repo.save(expired))

        marked1 = event_loop.run_until_complete(service.mark_stale_archives())
        assert len(marked1) == 1

        # 第二次执行：已标记档案被跳过，不产生新事件
        event_publisher = service._event_publisher
        assert isinstance(event_publisher, RabbitMQEventBus)
        outbox = event_publisher._outbox_repo
        assert isinstance(outbox, InMemoryOutboxRepository)
        unpublished_before = event_loop.run_until_complete(outbox.get_unpublished(100))
        stale_count_before = len([e for e in unpublished_before if e.event_type == "FactBecameStale"])

        marked2 = event_loop.run_until_complete(service.mark_stale_archives())
        assert len(marked2) == 0

        # 验证未产生新事件
        unpublished_after = event_loop.run_until_complete(outbox.get_unpublished(100))
        stale_count_after = len([e for e in unpublished_after if e.event_type == "FactBecameStale"])
        assert stale_count_after == stale_count_before

    def test_is_stale_method(self, repo_session, event_loop) -> None:
        """is_stale 服务方法委托实体判断"""
        service = _make_service()
        expired = _make_archive({"valid_until": datetime(2021, 1, 1, tzinfo=UTC)})
        valid = _make_archive({"valid_until": datetime(2099, 12, 31, tzinfo=UTC)})
        for a in (expired, valid):
            event_loop.run_until_complete(service._archive_repo.save(a))

        assert event_loop.run_until_complete(service.is_stale(expired.archive_id)) is True
        assert event_loop.run_until_complete(service.is_stale(valid.archive_id)) is False
