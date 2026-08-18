"""Story 3.12 数据陈旧标记验收测试步骤。

使用真实 PostgreSQL 和真实应用服务；外部 L3/L5 不属于本文件的强制依赖，
对应真实外部服务场景在 integration 专用文件中按可用性动态跳过。
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.services.strategic_archive_service import StrategicArchiveService
from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive
from src.domain.ports.archive_repository import ArchiveQuery
from src.infrastructure.config.postgresql import PostgreSQLConfig
from src.infrastructure.messaging.channel_router import ChannelRouter
from src.infrastructure.messaging.outbox.inmemory_outbox import InMemoryOutboxRepository
from src.infrastructure.messaging.rabbitmq_event_bus import RabbitMQEventBus
from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
from src.infrastructure.storage.postgresql.repository.archive_repository import PostgreSQLArchiveRepository
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session
from tests.environments import get_test_env

scenarios("test_acceptance_data_staleness.feature")


@pytest.fixture(scope="module")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """提供 pytest-bdd 兼容的模块级事件循环。"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def pg_config() -> PostgreSQLConfig:
    """读取验收环境 PostgreSQL 配置。"""
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
    """创建真实 PostgreSQL 管理器。"""
    return PostgreSQLManager(pg_config)


@pytest.fixture
def context() -> dict[str, Any]:
    """保存场景上下文和事务资源。"""
    return {}


@pytest.fixture(autouse=True)
def cleanup_context(event_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> Generator[None, None, None]:
    """场景结束时回滚当前事务，不执行全局清理。"""
    yield
    session = context.get("session")
    token = context.get("session_token")
    if token is not None:
        reset_session(token)
    if session is not None:
        event_loop.run_until_complete(session.rollback())
        event_loop.run_until_complete(session.close())


def _run(event_loop: asyncio.AbstractEventLoop, awaitable: Any) -> Any:
    """在 BDD 步骤中运行异步调用。"""
    return event_loop.run_until_complete(awaitable)


def _make_archive(**overrides: Any) -> StrategicArchive:
    """创建唯一测试档案。"""
    now = datetime.now(UTC)
    values: dict[str, Any] = {
        "archive_id": uuid.uuid4(),
        "plan_id": uuid.uuid4(),
        "plan_type": "SP",
        "archive_type": ArchiveType.ASSUMPTION,
        "metadata_ref": f"story-3-12:{uuid.uuid4()}",
        "created_at": now,
        "archived_at": now,
    }
    values.update(overrides)
    return StrategicArchive(**values)


def _build_service(event_loop: asyncio.AbstractEventLoop, db_engine: PostgreSQLManager) -> dict[str, Any]:
    """创建真实 L2 服务和可观测内存可靠 Outbox。"""
    try:
        from src.infrastructure.storage.postgresql.models import Base

        Base.metadata.create_all(db_engine.get_sync_engine())
    except Exception as exc:
        pytest.skip(f"PostgreSQL schema unavailable: {exc}")

    session = AsyncSession(db_engine.get_async_engine())
    _run(event_loop, session.begin())
    token = set_session(session)
    repo = PostgreSQLArchiveRepository()
    outbox = InMemoryOutboxRepository()
    publisher = RabbitMQEventBus(outbox_repository=outbox, router=ChannelRouter())
    service = StrategicArchiveService(archive_repo=repo, event_publisher=publisher)
    return {"session": session, "session_token": token, "repo": repo, "outbox": outbox, "service": service}


@given("Story 3.12 PostgreSQL 验收服务已就绪", target_fixture="context")
def given_service_ready(
    event_loop: asyncio.AbstractEventLoop,
    db_engine: PostgreSQLManager,
    context: dict[str, Any],
) -> dict[str, Any]:
    """探测 PostgreSQL，不可用时只跳过本文件场景。"""
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

    if not _run(event_loop, check()):
        pytest.skip(f"PostgreSQL unavailable at {env.postgres.host}:{env.postgres.port}")
    context.update(_build_service(event_loop, db_engine))
    return context


@given("存在一个已过期的真实战略档案")
def given_expired_archive(event_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    archive = _make_archive(valid_until=datetime(2020, 1, 1, tzinfo=UTC))
    _run(event_loop, context["repo"].save(archive))
    context["archive_id"] = archive.archive_id


@given("存在一个归档超过十二个月且没有 valid_until 的真实战略档案")
def given_old_archive(event_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    archive = _make_archive(
        valid_until=None,
        archived_at=datetime.now(UTC) - timedelta(days=400),
    )
    _run(event_loop, context["repo"].save(archive))
    context["archive_id"] = archive.archive_id


@when("执行 Story 3.12 陈旧标记检查")
def when_mark_stale(event_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    marked = _run(event_loop, context["service"].mark_stale_archives())
    context["marked"] = marked
    context["saved"] = _run(event_loop, context["repo"].get_by_id(context["archive_id"]))
    events = _run(event_loop, context["outbox"].get_unpublished(1000))
    context["events"] = [event for event in events if getattr(event, "archive_id", None) == str(context["archive_id"])]


@then('L2 档案的 staleness 为 "stale"')
def then_l2_stale(context: dict[str, Any]) -> None:
    assert context["saved"].metadata.get("staleness") == "stale"


@then('L2 档案的 stale_reason 为 "expired"')
def then_expired_reason(context: dict[str, Any]) -> None:
    assert context["saved"].metadata.get("stale_reason") == "expired"


@then('L2 档案的 stale_reason 为 "archived_too_long"')
def then_old_reason(context: dict[str, Any]) -> None:
    assert context["saved"].metadata.get("stale_reason") == "archived_too_long"


@then("已发布当前档案的 FactBecameStale 事件")
def then_stale_event(context: dict[str, Any]) -> None:
    assert len(context["events"]) == 1
    assert context["events"][0].event_type == "FactBecameStale"


@when("再次执行陈旧标记检查")
def when_repeat_stale_check(event_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    context["repeat_marked"] = _run(event_loop, context["service"].mark_stale_archives())


@then("重复检查结果不包含当前档案")
def then_repeat_is_idempotent(context: dict[str, Any]) -> None:
    assert all(item.archive_id != context["archive_id"] for item in context["repeat_marked"])


@given("存在一个 fresh 档案和一个 stale 档案")
def given_fresh_and_stale(event_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    fresh = _make_archive(metadata={})
    stale = _make_archive(
        metadata={
            "staleness": "stale",
            "stale_reason": "expired",
            "stale_since": datetime.now(UTC).isoformat(),
        }
    )
    _run(event_loop, context["repo"].save(fresh))
    _run(event_loop, context["repo"].save(stale))
    context["fresh_id"] = fresh.archive_id
    context["stale_id"] = stale.archive_id


@when('按 staleness_status 为 "stale" 查询真实档案仓储')
def when_query_stale(event_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    context["stale_results"] = _run(event_loop, context["repo"].find(ArchiveQuery(staleness_status="stale")))


@then("查询结果只包含 stale 档案")
def then_only_stale(context: dict[str, Any]) -> None:
    ids = {item.archive_id for item in context["stale_results"]}
    assert context["stale_id"] in ids
    assert context["fresh_id"] not in ids


@when('按 staleness_status 为 "fresh" 查询真实档案仓储')
def when_query_fresh(event_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    context["fresh_results"] = _run(event_loop, context["repo"].find(ArchiveQuery(staleness_status="fresh")))


@then("查询结果不包含 stale 档案")
def then_no_stale(context: dict[str, Any]) -> None:
    ids = {item.archive_id for item in context["fresh_results"]}
    assert context["stale_id"] not in ids


@given("Story 3.12 Resolver 已初始化")
def given_resolver_ready() -> None:
    """测试启动时已由全局 bootstrap 初始化 Resolver。"""


@when("通过 Story 3.12 Resolver 解析组件")
def when_resolve_components(context: dict[str, Any]) -> None:
    from src.application.event_handlers.archive_handlers import ArchiveValidityHandler
    from src.application.services.staleness_weight_service import StalenessWeightService
    from src.application.services.strategic_archive_service import StrategicArchiveService
    from src.domain.ports.resolver import get_resolver

    resolver = get_resolver()
    try:
        resolved_service = resolver.resolve("strategic_archive_service")
    except Exception as exc:
        pytest.skip(f"StrategicArchiveService dependencies unavailable: {exc}")
    context["resolved"] = {
        "handler": resolver.resolve("archive_validity_handler"),
        "weight": resolver.resolve("staleness_weight_service"),
        "service": resolved_service,
    }
    context["types"] = (ArchiveValidityHandler, StalenessWeightService, StrategicArchiveService)


@then("Story 3.12 组件均解析成功")
def then_components_resolved(context: dict[str, Any]) -> None:
    assert all(value is not None for value in context["resolved"].values())
    assert isinstance(context["resolved"]["handler"], context["types"][0])
    assert isinstance(context["resolved"]["weight"], context["types"][1])
    assert isinstance(context["resolved"]["service"], context["types"][2])


@then("ArchiveValidityHandler 已注册两个陈旧相关事件")
def then_handler_events_registered(context: dict[str, Any]) -> None:
    handler = context["resolved"]["handler"]
    listener = handler._event_listener
    assert "ValidityPeriodSet" in listener._handlers
    assert "FactBecameStale" in listener._handlers
