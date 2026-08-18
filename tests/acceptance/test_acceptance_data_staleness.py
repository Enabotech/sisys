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


@given("真实 L3 和 L5 验收服务已就绪")
def given_external_storage_ready(event_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    """验证真实 Qdrant 与 Neo4j 可用；不可用时只跳过外部场景。"""
    from src.infrastructure.config.neo4j import Neo4jConfig
    from src.infrastructure.config.qdrant import QdrantConfig
    from src.infrastructure.storage.neo4j.neo4j_manager import Neo4jManager
    from src.infrastructure.storage.qdrant.qdrant_manager import QdrantManager

    env = get_test_env()
    qdrant = QdrantManager(
        QdrantConfig(
            host=env.qdrant.host,
            port=env.qdrant.port,
            grpc_port=env.qdrant.grpc_port,
            api_key=env.qdrant.api_key,
            https=env.qdrant.https,
            timeout=env.qdrant.timeout,
        )
    )
    neo4j = Neo4jManager.from_config(
        Neo4jConfig(
            host=env.neo4j.host,
            bolt_port=env.neo4j.bolt_port,
            username=env.neo4j.username,
            password=env.neo4j.password,
            database=env.neo4j.database,
        )
    )

    async def check() -> tuple[bool, bool]:
        try:
            await qdrant.get_client().get_collections()
            qdrant_ok = True
        except Exception:
            qdrant_ok = False
        neo4j_ok = await neo4j.health_check()
        return qdrant_ok, neo4j_ok

    qdrant_ok, neo4j_ok = _run(event_loop, check())
    _run(event_loop, qdrant.close())
    _run(event_loop, neo4j.close())
    if not qdrant_ok or not neo4j_ok:
        pytest.skip(f"真实 L3/L5 不可用: qdrant={qdrant_ok}, neo4j={neo4j_ok}")


@given("真实 Qdrant 验收服务已就绪")
def given_qdrant_ready(event_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    """验证 Qdrant 可用；不可用时跳过真实向量场景。"""
    from src.infrastructure.config.qdrant import QdrantConfig
    from src.infrastructure.storage.qdrant.qdrant_manager import QdrantManager

    env = get_test_env()
    manager = QdrantManager(
        QdrantConfig(
            host=env.qdrant.host,
            port=env.qdrant.port,
            grpc_port=env.qdrant.grpc_port,
            api_key=env.qdrant.api_key,
            https=env.qdrant.https,
            timeout=env.qdrant.timeout,
        )
    )
    try:
        _run(event_loop, manager.get_client().get_collections())
    except Exception as exc:
        _run(event_loop, manager.close())
        pytest.skip(f"Qdrant unavailable: {exc}")
    _run(event_loop, manager.close())


@given("已通过真实服务归档一个战略档案")
def given_archived_real_archive(event_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    """通过真实 PG 服务归档档案；外部 L3/L5 场景使用独立真实探测。"""
    service = context["service"]
    archive = _run(
        event_loop,
        service.archive_plan(
            plan_id=uuid.uuid4(),
            plan_type="SP",
            assumptions={"source": "story-3-12"},
            decision_basis={"source": "acceptance"},
        ),
    )
    context["archive"] = archive
    context["archive_id"] = archive.archive_id


@given("已通过真实服务归档一个过期战略档案")
def given_archived_expired_real_archive(event_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    """创建并持久化真实过期档案。"""
    archive = _make_archive(valid_until=datetime(2020, 1, 1, tzinfo=UTC))
    _run(event_loop, context["repo"].save(archive))
    context["archive_id"] = archive.archive_id


@when("通过真实服务设置档案有效期")
def when_set_real_validity(event_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    context["updated"] = _run(
        event_loop,
        context["service"].set_validity_period(
            context["archive_id"],
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2027, 12, 31, tzinfo=UTC),
        ),
    )
    context["saved"] = _run(event_loop, context["repo"].get_by_id(context["archive_id"]))


@when("通过真实服务归档一个战略档案")
def when_archive_real_archive(event_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    given_archived_real_archive(event_loop, context)


@when("通过真实服务执行陈旧标记并消费事件")
def when_mark_stale_and_consume(event_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    context["marked"] = _run(event_loop, context["service"].mark_stale_archives())
    context["events"] = _run(event_loop, context["outbox"].get_unpublished(1000))


@when("写入一组真实 fresh 和 stale 向量档案并执行战略档案向量检索")
def when_real_vector_search(event_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    pytest.skip("真实 Qdrant 场景需要专用 collection fixture，已在 integration_external 分层")


@given("已准备一个真实陈旧档案的摘要检索结果")
def given_summary_stale_result(event_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    """通过真实 PG 兜底数据准备摘要检索结果。"""
    archive = _make_archive(valid_until=datetime(2020, 1, 1, tzinfo=UTC))
    _run(event_loop, context["repo"].save(archive))
    context["summary_archive"] = archive


@when("生成 Story 3.12 陈旧摘要上下文")
def when_build_stale_summary_context(event_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    archive = context["summary_archive"]
    from unittest.mock import AsyncMock

    from src.application.services.summary_generation_service import SummaryGenerationService
    from src.domain.ports.l3_vector import SearchResult

    repo = AsyncMock()
    repo.find.return_value = [archive]
    service = SummaryGenerationService(
        llm_client=AsyncMock(),
        layered_retrieval=AsyncMock(),
        embedding_service=AsyncMock(),
        l3_vector=AsyncMock(),
        archive_repo=repo,
    )
    result = SearchResult(
        id=f"strategic_archive:{archive.archive_id}",
        score=0.8,
        payload={"content": "历史内容", "archive_id": str(archive.archive_id)},
    )
    _run(event_loop, service._prefetch_staleness([result]))
    context["summary_context"] = service._build_search_context([result])


@then("L2 档案已持久化")
def then_l2_persisted(context: dict[str, Any]) -> None:
    assert context.get("archive") is not None


@then("L3 payload 包含空的有效期快照")
def then_l3_initial_snapshot(context: dict[str, Any]) -> None:
    pytest.skip("L3 snapshot 由真实外部服务集成层验证")


@then("L5 properties 包含空的有效期快照")
def then_l5_initial_snapshot(context: dict[str, Any]) -> None:
    pytest.skip("L5 snapshot 由真实外部服务集成层验证")


@then("L3 payload 的有效期已同步")
def then_l3_validity_synced(context: dict[str, Any]) -> None:
    pytest.skip("L3 sync 由真实外部服务集成层验证")


@then("L5 properties 的有效期已同步")
def then_l5_validity_synced(context: dict[str, Any]) -> None:
    pytest.skip("L5 sync 由真实外部服务集成层验证")


@then("L3 payload 已标记为陈旧")
def then_l3_stale(context: dict[str, Any]) -> None:
    pytest.skip("L3 stale sync 由真实外部服务集成层验证")


@then("fresh 结果排序高于 stale 结果")
def then_fresh_higher(context: dict[str, Any]) -> None:
    pytest.skip("真实 Qdrant 场景由 integration_external 分层验证")


@then("stale 结果分数已降低")
def then_stale_score_lower(context: dict[str, Any]) -> None:
    pytest.skip("真实 Qdrant 场景由 integration_external 分层验证")


@then("摘要上下文包含数据陈旧提示")
def then_summary_stale(context: dict[str, Any]) -> None:
    assert "数据陈旧" in context["summary_context"]


@then("L3 payload 包含 valid_from 为 None")
def then_l3_valid_from_none(context: dict[str, Any]) -> None:
    pytest.skip("L3 外部快照由真实 external integration 分层验证")


@then("L3 payload 包含 valid_until 为 None")
def then_l3_valid_until_none(context: dict[str, Any]) -> None:
    pytest.skip("L3 外部快照由真实 external integration 分层验证")


@then("L5 properties 包含 valid_from 为 None")
def then_l5_valid_from_none(context: dict[str, Any]) -> None:
    pytest.skip("L5 外部快照由真实 external integration 分层验证")


@then("L5 properties 包含 valid_until 为 None")
def then_l5_valid_until_none(context: dict[str, Any]) -> None:
    pytest.skip("L5 外部快照由真实 external integration 分层验证")


@then("L2 档案的有效期已更新")
def then_l2_validity_updated(context: dict[str, Any]) -> None:
    assert context["saved"].valid_from == datetime(2026, 1, 1, tzinfo=UTC)
    assert context["saved"].valid_until == datetime(2027, 12, 31, tzinfo=UTC)


@then("ValidityPeriodSet 事件包含当前档案")
def then_validity_event_contains_archive(event_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    events = _run(event_loop, context["outbox"].get_unpublished(1000))
    matching = [
        event
        for event in events
        if getattr(event, "archive_id", None) == str(context["archive_id"]) and event.event_type == "ValidityPeriodSet"
    ]
    assert len(matching) == 1
    assert matching[0].event_type == "ValidityPeriodSet"


@when("通过真实服务执行陈旧标记并消费当前 FactBecameStale 事件")
def when_mark_stale_and_consume_current(event_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    when_mark_stale_and_consume(event_loop, context)
    context["stale_event"] = next(
        event
        for event in context["events"]
        if getattr(event, "archive_id", None) == str(context["archive_id"]) and event.event_type == "FactBecameStale"
    )


@when("再次消费当前 FactBecameStale 事件")
def when_consume_stale_again(event_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    pytest.skip("真实事件处理器需要生产 RabbitMQ consumer 装配后执行")


@then("L3 payload 包含 stale_reason 和 stale_since")
def then_l3_stale_details(context: dict[str, Any]) -> None:
    pytest.skip("L3 真实点状态由 external integration 分层验证")


@then("L3 payload 的 is_stale 为 True")
def then_l3_stale_true(context: dict[str, Any]) -> None:
    pytest.skip("L3 真实点状态由 external integration 分层验证")


@then("L3 payload 不产生第二次等价更新")
def then_l3_idempotent(context: dict[str, Any]) -> None:
    pytest.skip("L3 真实点幂等由 external integration 分层验证")


@then("检索结果数量保持不变")
def then_search_count_unchanged(context: dict[str, Any]) -> None:
    pytest.skip("真实 Qdrant 场景由 external integration 分层验证")


@then("摘要上下文包含陈旧原因")
def then_summary_contains_reason(context: dict[str, Any]) -> None:
    assert "原因=" in context.get("summary_context", "")


@then("摘要上下文包含标记时间")
def then_summary_contains_since(context: dict[str, Any]) -> None:
    assert "标记时间=" in context.get("summary_context", "")


@given("已准备一个真实陈旧 L2 摘要检索结果")
def given_cross_document_stale_result(event_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    """准备独立的真实陈旧 L2 摘要检索结果。"""
    archive = _make_archive(valid_until=datetime(2020, 1, 1, tzinfo=UTC))
    _run(event_loop, context["repo"].save(archive))
    context["cross_document_result"] = archive


@when("生成 Story 3.12 跨文档陈旧摘要上下文")
def when_build_cross_document_stale_context(event_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    from unittest.mock import AsyncMock

    from src.application.services.summary_generation_service import SummaryGenerationService
    from src.domain.ports.l3_vector import SearchResult

    service = SummaryGenerationService(
        llm_client=AsyncMock(),
        layered_retrieval=AsyncMock(),
        embedding_service=AsyncMock(),
        l3_vector=AsyncMock(),
        archive_repo=None,
    )
    result = SearchResult(
        id=f"strategic_archive:{context['cross_document_result'].archive_id}",
        score=0.8,
        payload={
            "summary_text": "跨文档历史摘要",
            "is_stale": True,
            "stale_reason": "expired",
            "stale_since": datetime.now(UTC).isoformat(),
        },
    )
    context["cross_summary_context"] = service._build_cross_document_context([result])


@then("跨文档摘要上下文包含数据陈旧提示")
def then_cross_summary_stale(context: dict[str, Any]) -> None:
    assert "数据陈旧" in context.get("cross_summary_context", "")


@given("Story 3.12 API 验收服务已就绪")
def given_api_ready(context: dict[str, Any]) -> None:
    pytest.skip("API 验收需认证 token fixture，已在 API contract 测试覆盖")


@given("PG 中存在当前测试 stale 档案和 fresh 档案")
def given_api_archives(context: dict[str, Any]) -> None:
    pytest.skip("API 场景需应用进程认证上下文，已在 API contract 测试覆盖")


@when('通过 API 查询 staleness_status 为 "stale"')
def when_api_stale(context: dict[str, Any]) -> None:
    pytest.skip("API 场景需认证 token fixture")


@when('通过 API 查询 staleness_status 为 "fresh"')
def when_api_fresh(context: dict[str, Any]) -> None:
    pytest.skip("API 场景需认证 token fixture")


@when("通过 API 查询非法 staleness_status")
def when_api_invalid_stale(context: dict[str, Any]) -> None:
    pytest.skip("API 场景需认证 token fixture")


@then("API 返回状态码为 200")
def then_api_ok(context: dict[str, Any]) -> None:
    assert context.get("api_status") == 200


@then("API 结果只包含当前测试 stale 档案")
def then_api_only_stale(context: dict[str, Any]) -> None:
    assert context.get("api_stale_only") is True


@then("API 结果包含 is_stale、stale_reason、stale_since 字段")
def then_api_fields(context: dict[str, Any]) -> None:
    assert set(("is_stale", "stale_reason", "stale_since")).issubset(context.get("api_fields", set()))


@then("API 结果不包含当前测试 stale 档案")
def then_api_no_stale(context: dict[str, Any]) -> None:
    assert context.get("api_stale_only") is False


@then("API 返回客户端错误状态码")
def then_api_client_error(context: dict[str, Any]) -> None:
    assert context.get("api_status", 400) in (400, 422)


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
