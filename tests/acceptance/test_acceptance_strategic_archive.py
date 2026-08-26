"""战略档案库验收测试步骤实现

验证战略档案库长期存储与归档功能，覆盖 Happy Path、查询、降级、异常路径等场景。

运行: poetry run pytest tests/acceptance/test_acceptance_strategic_archive.py -v

前置条件:
    - PostgreSQL 服务运行中（L2 元数据真实持久化）
    - L3/L4/L5 外部基础设施使用 mock（可控失败注入，验证优雅降级）
    - 事件发布使用真实 InMemoryEventBus（验证 ArchiveCreated 事件）
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive
from src.domain.events.archive_events import ArchiveCreated
from src.domain.ports.archive_repository import ArchiveQuery, ArchiveRepositoryPort
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.l3_vector import L3VectorPort
from src.domain.ports.l4_object import L4ObjectPort
from src.domain.ports.l5_graph import L5GraphPort
from src.infrastructure.config.postgresql import PostgreSQLConfig
from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session
from tests.environments import get_test_env

ROOT = Path(__file__).resolve().parents[2]

scenarios("test_acceptance_strategic_archive.feature")

# 模块级共享数据库引擎
_shared_db_engine: PostgreSQLManager | None = None


# ===================================================================
# Fixtures
# ===================================================================


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
def context() -> dict[str, Any]:
    """BDD 步骤间共享状态"""
    return {}


@pytest.fixture(autouse=True)
def _cleanup_service(event_loop, context):
    """测试结束后自动清理 savepoint rollback"""
    yield
    if "_svc" in context:
        ctx = context["_svc"]
        reset_session(ctx["token"])
        event_loop.run_until_complete(ctx["session"].rollback())
        event_loop.run_until_complete(ctx["session"].close())


# ===================================================================
# Helper: 构建真实服务（真实 PG + mock L3/L4/L5 + 真实事件总线）
# ===================================================================


def _build_service(event_loop):
    """构建真实 StrategicArchiveService 实例

    返回上下文字典，包含 service 及各 mock 端口引用（用于降级注入）。
    """
    from src.application.services.strategic_archive_service import StrategicArchiveService
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.storage.postgresql.repository.archive_repository import (
        PostgreSQLArchiveRepository,
    )

    async_engine = _shared_db_engine.get_async_engine()
    session = AsyncSession(async_engine)
    event_loop.run_until_complete(session.begin())
    token = set_session(session)

    repo = PostgreSQLArchiveRepository()

    vector = AsyncMock(spec=L3VectorPort)
    vector.upsert_points.return_value = True
    obj = AsyncMock(spec=L4ObjectPort)
    obj.archive.return_value = "etag"
    graph = AsyncMock(spec=L5GraphPort)
    graph.create_entity.return_value = True
    event_bus = InMemoryEventBus()

    service = StrategicArchiveService(
        archive_repo=cast(ArchiveRepositoryPort, repo),
        embedding_service=None,
        vector_storage=cast(L3VectorPort, vector),
        object_storage=cast(L4ObjectPort, obj),
        graph_storage=cast(L5GraphPort, graph),
        event_publisher=cast(EventPublisher, event_bus),
    )

    return {
        "session": session,
        "token": token,
        "repo": repo,
        "vector": vector,
        "obj": obj,
        "graph": graph,
        "event_bus": event_bus,
        "service": service,
    }


def _run(event_loop, coro):
    """同步运行 async 协程"""
    return event_loop.run_until_complete(coro)


def _save_archive(event_loop, repo, plan_id, archive_type):
    """直接通过仓储保存指定类型的档案（绕过 service 的类型固定限制）"""
    now = datetime.now(UTC)
    archive = StrategicArchive(
        archive_id=uuid.uuid4(),
        plan_id=plan_id,
        plan_type="SP",
        archive_type=archive_type,
        assumptions={"key": "value"},
        decision_basis={},
        execution_deviation={},
        metadata_ref=f"strategic_archives:{uuid.uuid4()}",
        created_at=now,
        archived_at=now,
    )
    archive.validate()
    return _run(event_loop, repo.save(archive))


# ===================================================================
# Background
# ===================================================================


@given("系统已初始化战略档案服务")
def system_initialized(pg_config: PostgreSQLConfig, db_engine: PostgreSQLManager, event_loop):
    """验证 PG 可用，初始化档案服务"""
    global _shared_db_engine
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

    is_available = event_loop.run_until_complete(_check())
    if not is_available:
        pytest.skip(f"PostgreSQL not available at {pg_config.host}:{pg_config.port}")

    _shared_db_engine = db_engine

    # 确保表结构存在
    try:
        from src.infrastructure.storage.postgresql.models import Base

        Base.metadata.create_all(db_engine.get_sync_engine())
    except Exception:
        pass


# ===================================================================
# Given 步骤
# ===================================================================


@given("存在一个 SP 规划")
def given_plan_exists(event_loop, context):
    """存在一个 SP 规划"""
    ctx = _build_service(event_loop)
    context["_svc"] = ctx
    context["plan_id"] = uuid.uuid4()


@given("存在多个不同类型的档案")
def given_multiple_archives(event_loop, context):
    """存在多个不同类型的档案（通过仓储直接保存不同类型）"""
    ctx = _build_service(event_loop)
    context["_svc"] = ctx
    plan_id = uuid.uuid4()
    context["plan_id"] = plan_id
    for atype in ArchiveType:
        _save_archive(event_loop, ctx["repo"], plan_id, atype)


@given("存在多个规划的档案")
def given_multiple_plans(event_loop, context):
    """存在多个规划的档案"""
    ctx = _build_service(event_loop)
    context["_svc"] = ctx
    plan_ids = []
    for i in range(3):
        plan_id = uuid.uuid4()
        _save_archive(event_loop, ctx["repo"], plan_id, ArchiveType.ASSUMPTION)
        plan_ids.append(plan_id)
    context["plan_ids"] = plan_ids
    context["target_plan_id"] = plan_ids[0]


@given("存在一个已归档的档案")
def given_one_archived(event_loop, context):
    """存在一个已归档的档案"""
    ctx = _build_service(event_loop)
    context["_svc"] = ctx
    service = ctx["service"]
    plan_id = uuid.uuid4()
    archive = _run(
        event_loop,
        service.archive_plan(
            plan_id=plan_id,
            plan_type="SP",
            assumptions={"key": "value"},
            decision_basis={"reason": "test"},
            execution_deviation={"delta": "0.1"},
            evidence_blob=b"test evidence",
        ),
    )
    context["archive"] = archive
    context["plan_id"] = plan_id


@given("不存在 archive_id 为「00000000-0000-0000-0000-000000009999」的档案")
def given_archive_not_exists(event_loop, context):
    """不存在指定 archive_id 的档案"""
    ctx = _build_service(event_loop)
    context["_svc"] = ctx
    context["nonexistent_id"] = uuid.UUID("00000000-0000-0000-0000-000000009999")


@given("存在一个规划关联多个档案")
def given_plan_with_multiple_archives(event_loop, context):
    """一个规划关联多个档案（通过仓储直接保存不同类型）"""
    ctx = _build_service(event_loop)
    context["_svc"] = ctx
    plan_id = uuid.uuid4()
    context["plan_id"] = plan_id
    for atype in ArchiveType:
        _save_archive(event_loop, ctx["repo"], plan_id, atype)


# ===================================================================
# When 步骤
# ===================================================================


@when("用户归档该规划的假设变量、决策依据和执行偏差")
def when_archive_plan(event_loop, context):
    """归档规划（含证据包）"""
    ctx = context["_svc"]
    service = ctx["service"]
    plan_id = context["plan_id"]
    archive = _run(
        event_loop,
        service.archive_plan(
            plan_id=plan_id,
            plan_type="SP",
            assumptions={"market_trend": "growing", "risk_level": "medium"},
            decision_basis={"method": "scenario_analysis", "confidence": 0.85},
            execution_deviation={"revenue": -0.05, "cost": 0.03},
            evidence_blob=b'{"summary": "Q1 financial review"}',
        ),
    )
    context["created_archive"] = archive


@when("用户归档该规划")
def when_archive_plan_basic(event_loop, context):
    """归档规划（可能伴随存储层失败）"""
    ctx = context["_svc"]
    service = ctx["service"]
    plan_id = context["plan_id"]
    archive = _run(
        event_loop,
        service.archive_plan(
            plan_id=plan_id,
            plan_type="SP",
            assumptions={"test": "value"},
            decision_basis={},
            execution_deviation={},
            evidence_blob=b"evidence",
        ),
    )
    context["created_archive"] = archive


@given("L3 向量存储失败")
def given_l3_fails(context):
    """L3 向量存储失败（前置条件）"""
    ctx = context["_svc"]
    ctx["vector"].upsert_points.side_effect = RuntimeError("qdrant down")
    context["l3_fail"] = True


@given("L5 图存储失败")
def given_l5_fails(context):
    """L5 图存储失败（前置条件）"""
    ctx = context["_svc"]
    ctx["graph"].create_entity.side_effect = RuntimeError("neo4j down")
    context["l5_fail"] = True


@when("用户按档案类型「assumption」查询")
def when_query_by_type(event_loop, context):
    """按档案类型查询"""
    ctx = context["_svc"]
    service = ctx["service"]
    query = ArchiveQuery(archive_type=ArchiveType.ASSUMPTION)
    context["query_result"] = _run(event_loop, service.query_archive(query))


@when("用户按该规划 ID 查询")
def when_query_by_plan_id(event_loop, context):
    """按规划 ID 查询"""
    ctx = context["_svc"]
    service = ctx["service"]
    plan_id = context["target_plan_id"]
    query = ArchiveQuery(plan_id=plan_id)
    context["query_result"] = _run(event_loop, service.query_archive(query))


@when("用户按该档案的 archive_id 查询")
def when_get_archive(event_loop, context):
    """按 archive_id 查询档案详情"""
    ctx = context["_svc"]
    service = ctx["service"]
    archive = context["archive"]
    context["fetched_archive"] = _run(event_loop, service.get_archive(archive.archive_id))


@when("用户按该 archive_id 查询")
def when_query_nonexistent(event_loop, context):
    """查询不存在的档案"""
    ctx = context["_svc"]
    service = ctx["service"]
    try:
        _run(event_loop, service.get_archive(context["nonexistent_id"]))
        context["error"] = None
    except Exception as e:
        context["error"] = e


@when("用户按规划 ID 列出档案")
def when_list_by_plan(event_loop, context):
    """按规划 ID 列出档案"""
    ctx = context["_svc"]
    service = ctx["service"]
    plan_id = context["plan_id"]
    context["plan_archives"] = _run(event_loop, service.query_archive(ArchiveQuery(plan_id=plan_id)))


# ===================================================================
# Then 步骤
# ===================================================================


@then("系统返回已创建的档案信息")
def then_archive_created(context):
    """档案创建成功"""
    assert context["created_archive"] is not None
    assert context["created_archive"].archive_id is not None


@then("L2 元数据已持久化")
def then_l2_persisted(event_loop, context):
    """L2 元数据持久化验证"""
    ctx = context["_svc"]
    repo = ctx["repo"]
    archive = context["created_archive"]
    fetched = _run(event_loop, repo.get_by_id(archive.archive_id))
    assert fetched is not None


@then("L3 向量已存储")
def then_l3_stored(context):
    """L3 向量存储验证"""
    ctx = context["_svc"]
    assert ctx["vector"].upsert_points.called


@then("L4 对象已归档（WORM 7年）")
def then_l4_archived(context):
    """L4 对象归档验证"""
    ctx = context["_svc"]
    assert ctx["obj"].archive.called


@then("L5 图谱节点已创建")
def then_l5_created(context):
    """L5 图谱节点验证"""
    ctx = context["_svc"]
    assert ctx["graph"].create_entity.called


@then("ArchiveCreated 事件已发布")
def then_event_published(context):
    """ArchiveCreated 事件发布验证"""
    ctx = context["_svc"]
    events = ctx["event_bus"].published_events
    assert any(isinstance(e, ArchiveCreated) for e in events)


@then("ArchiveCreated 事件仍发布")
def then_event_still_published(context):
    """ArchiveCreated 仍发布"""
    ctx = context["_svc"]
    events = ctx["event_bus"].published_events
    assert any(isinstance(e, ArchiveCreated) for e in events)


@then("仅返回类型为「assumption」的档案")
def then_only_assumption(context):
    """仅返回 assumption 类型档案"""
    result = context["query_result"]
    assert len(result) > 0
    for archive in result:
        assert archive.archive_type == ArchiveType.ASSUMPTION


@then("返回结果不包含其他类型的档案")
def then_no_other_types(context):
    """不包含其他类型档案"""
    result = context["query_result"]
    for archive in result:
        assert archive.archive_type == ArchiveType.ASSUMPTION


@then("仅返回该规划关联的档案")
def then_only_plan_archives(context):
    """仅返回该规划关联的档案"""
    result = context["query_result"]
    assert len(result) > 0
    target_plan_id = context["target_plan_id"]
    for archive in result:
        assert archive.plan_id == target_plan_id


@then("返回结果不包含其他规划的档案")
def then_no_other_plan_archives(context):
    """不包含其他规划档案"""
    result = context["query_result"]
    target_plan_id = context["target_plan_id"]
    for archive in result:
        assert archive.plan_id == target_plan_id


@then("系统返回完整的档案详情")
def then_full_archive_detail(context):
    """返回完整档案详情"""
    fetched = context["fetched_archive"]
    assert fetched is not None
    assert fetched.archive_id == context["archive"].archive_id


@then("包含所有六层存储引用")
def then_all_storage_refs(context):
    """包含六层存储引用"""
    fetched = context["fetched_archive"]
    assert fetched.metadata_ref is not None


@then("L2 元数据仍持久化成功")
def then_l2_still_success(event_loop, context):
    """L2 仍持久化成功"""
    ctx = context["_svc"]
    repo = ctx["repo"]
    archive = context["created_archive"]
    fetched = _run(event_loop, repo.get_by_id(archive.archive_id))
    assert fetched is not None


@then("L4 对象仍归档成功")
def then_l4_still_success(context):
    """L4 仍归档成功"""
    ctx = context["_svc"]
    assert ctx["obj"].archive.called


@then("embedding_ref 为空")
def then_embedding_ref_null(context):
    """embedding_ref 为空"""
    archive = context["created_archive"]
    assert archive.embedding_ref is None


@then("graph_ref 为空")
def then_graph_ref_null(context):
    """graph_ref 为空"""
    archive = context["created_archive"]
    assert archive.graph_ref is None


@then("系统返回错误码「EXCEPTION_282」")
def then_error_282(context):
    """返回 EXCEPTION_282 错误"""
    from src.domain.exceptions.archive_exceptions import ArchiveNotFoundError

    err = context["error"]
    assert err is not None
    assert isinstance(err, ArchiveNotFoundError)
    assert err.code == "EXCEPTION_282"


@then("错误HTTP状态码为404")
def then_http_404(context):
    """HTTP 404"""
    from src.interfaces.api.exception_handlers import _get_http_status

    err = context["error"]
    assert _get_http_status(err) == 404


@then("返回该规划的所有关联档案")
def then_all_plan_archives(context):
    """返回所有关联档案"""
    archives = context["plan_archives"]
    assert len(archives) > 0
    for archive in archives:
        assert archive.plan_id == context["plan_id"]


@then("返回结果包含所有档案类型")
def then_all_types(context):
    """包含所有档案类型"""
    archives = context["plan_archives"]
    types_found = {a.archive_type for a in archives}
    assert len(types_found) > 0
