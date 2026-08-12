"""Story 3.3 战略领域词典库管理验收测试

使用真实 DomainDictionaryService + 真实 PostgreSQLAdapter 仓储，
通过 savepoint rollback 保证测试自包含。
热更新端到端验证使用真实 RuleBasedExtractor 实例。

运行: poetry run pytest tests/acceptance/test_acceptance_domain_dictionary.py -v

前置条件:
    - PostgreSQL 服务运行中
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import (
    DictionaryEntryConflictError,
    DictionaryNotFoundError,
    DictionaryVersionConflictError,
)
from src.domain.ports.domain_dictionary import (
    DictionaryEntry,
)
from src.infrastructure.config.postgresql import PostgreSQLConfig
from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session
from tests.environments import get_test_env

# ===================================================================
# Paths & Constants
# ===================================================================
ROOT = Path(__file__).resolve().parents[2]

scenarios("test_acceptance_domain_dictionary.feature")

# 模块级共享状态
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
def test_tenant_id() -> str:
    """生成唯一测试租户ID"""
    return f"test_{uuid.uuid4().hex[:8]}"


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
def context() -> dict:
    """BDD 步骤间共享状态"""
    return {}


# ===================================================================
# Helper: 构建真实服务（带 savepoint rollback 隔离）
# ===================================================================


def _build_service(event_loop):
    """构建真实 DomainDictionaryService 实例"""
    global _shared_db_engine
    from src.application.services.domain_dictionary_service import DomainDictionaryService
    from src.infrastructure.external_services.entity_extraction.rule_extractor import (
        RuleBasedExtractor,
    )
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.storage.postgresql.repository.domain_dictionary_repository import (
        PostgreSQLDomainDictionaryRepository,
    )

    async_engine = _shared_db_engine.get_async_engine()
    session = AsyncSession(async_engine)
    event_loop.run_until_complete(session.begin())
    token = set_session(session)

    repo = PostgreSQLDomainDictionaryRepository()
    extractor = RuleBasedExtractor()
    event_bus = InMemoryEventBus()

    service = DomainDictionaryService(
        dictionary_repo=repo,
        dictionary_consumer=extractor,
        event_publisher=event_bus,
    )

    return {
        "session": session,
        "token": token,
        "repo": repo,
        "extractor": extractor,
        "event_bus": event_bus,
        "service": service,
    }


def _teardown_service(ctx, event_loop):
    """清理 savepoint rollback"""
    reset_session(ctx["token"])
    event_loop.run_until_complete(ctx["session"].rollback())
    event_loop.run_until_complete(ctx["session"].close())


# ===================================================================
# Background
# ===================================================================


@given("系统已初始化词典服务")
def system_initialized(pg_config: PostgreSQLConfig, db_engine: PostgreSQLManager, event_loop):
    """验证 PG 可用，初始化词典服务和仓储"""
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
# Scenario 1: 添加词条 -> 热更新 -> 实体抽取识别新词
# ===================================================================


@given("规则基抽取器初始词典不含「元宇宙」")
def initial_dict_without_metaverse(event_loop, context):
    """验证初始词典不含「元宇宙」"""
    ctx = _build_service(event_loop)
    context["_svc"] = ctx
    extractor = ctx["extractor"]

    async def _check():
        result = await extractor.extract_entities("元宇宙技术趋势")
        for entity in result.entities:
            assert entity.name != "元宇宙", "初始词典不应包含「元宇宙」"
        return True

    event_loop.run_until_complete(_check())


@when("用户添加词条「元宇宙」类型为「CONCEPT」")
def add_entry_metaverse(event_loop, context):
    """添加词条「元宇宙」"""
    ctx = context["_svc"]
    service = ctx["service"]
    entry = DictionaryEntry(term="元宇宙", entity_type="CONCEPT", category="tech")
    event_loop.run_until_complete(service.add_entry(entry, trigger="api"))


@when("用户触发热更新")
def trigger_refresh(event_loop, context):
    """触发热更新"""
    ctx = context["_svc"]
    service = ctx["service"]
    event_loop.run_until_complete(service.refresh_dictionary())


@then("规则基抽取器识别「元宇宙技术趋势」中的「元宇宙」实体")
def verify_metaverse_recognized(event_loop, context):
    """验证热更新后识别新词"""
    ctx = context["_svc"]
    extractor = ctx["extractor"]

    async def _check():
        result = await extractor.extract_entities("元宇宙技术趋势")
        assert any(e.name == "元宇宙" for e in result.entities), "热更新后应识别「元宇宙」"
        return True

    event_loop.run_until_complete(_check())


@then("实体类型为「CONCEPT」")
def verify_entity_type_concept(event_loop, context):
    """验证实体类型"""
    ctx = context["_svc"]
    extractor = ctx["extractor"]

    async def _check():
        result = await extractor.extract_entities("元宇宙技术趋势")
        for e in result.entities:
            if e.name == "元宇宙":
                assert e.entity_type == "CONCEPT", f"实体类型应为 CONCEPT，实际为 {e.entity_type}"
        return True

    event_loop.run_until_complete(_check())
    _teardown_service(ctx, event_loop)


# ===================================================================
# Scenario 2: 修改词条 -> 热更新 -> 抽取使用新实体类型
# ===================================================================


@given("词条「BLM」已存在且类型为「CONCEPT」")
def entry_blm_exists_as_concept(event_loop, context):
    """词条BLM已存在"""
    ctx = _build_service(event_loop)
    context["_svc"] = ctx
    service = ctx["service"]
    entry = DictionaryEntry(term="BLM", entity_type="CONCEPT", category="strategy")
    event_loop.run_until_complete(service.add_entry(entry, trigger="api"))


@when("用户修改词条「BLM」类型为「STRATEGY」")
def update_entry_blm_to_strategy(event_loop, context):
    """修改词条类型"""
    ctx = context["_svc"]
    service = ctx["service"]
    updated = DictionaryEntry(term="BLM", entity_type="STRATEGY", category="strategy", version=1)
    event_loop.run_until_complete(service.update_entry("BLM", updated, trigger="api"))


@then("规则基抽取器识别「BLM方法论」中的「BLM」实体")
def verify_blm_recognized(event_loop, context):
    """验证BLM被识别"""
    ctx = context["_svc"]
    extractor = ctx["extractor"]

    async def _check():
        result = await extractor.extract_entities("BLM方法论")
        assert any(e.name == "BLM" for e in result.entities), "热更新后应识别BLM"
        return True

    event_loop.run_until_complete(_check())


@then("实体类型为「STRATEGY」")
def verify_entity_type_strategy(event_loop, context):
    """验证实体类型为STRATEGY"""
    ctx = context["_svc"]
    extractor = ctx["extractor"]

    async def _check():
        result = await extractor.extract_entities("BLM方法论")
        for e in result.entities:
            if e.name == "BLM":
                assert e.entity_type == "STRATEGY", f"实体类型应为 STRATEGY，实际为 {e.entity_type}"
        return True

    event_loop.run_until_complete(_check())
    _teardown_service(ctx, event_loop)


# ===================================================================
# Scenario 3: 创建快照 -> 回滚 -> 词典恢复至目标版本
# ===================================================================


@given("词典包含词条「BLM」类型「CONCEPT」")
def dict_contains_blm_concept(event_loop, context):
    """词典包含词条"""
    ctx = _build_service(event_loop)
    context["_svc"] = ctx
    service = ctx["service"]
    entry = DictionaryEntry(term="BLM", entity_type="CONCEPT", category="strategy")
    event_loop.run_until_complete(service.add_entry(entry, trigger="api"))


@when("用户创建词典快照")
def create_snapshot(event_loop, context):
    """创建快照"""
    ctx = context["_svc"]
    service = ctx["service"]
    snapshot = event_loop.run_until_complete(service.create_snapshot("admin"))
    context["snapshot_version"] = snapshot.version


@when("用户修改词条「BLM」类型为「STRATEGY」")
def update_blm_to_strategy_for_snapshot(event_loop, context):
    """修改词条用于回滚测试"""
    ctx = context["_svc"]
    service = ctx["service"]
    entry = DictionaryEntry(term="BLM", entity_type="STRATEGY", category="strategy", version=1)
    event_loop.run_until_complete(service.update_entry("BLM", entry, trigger="api"))


@when("用户回滚至快照版本")
def rollback_to_snapshot(event_loop, context):
    """回滚至快照"""
    ctx = context["_svc"]
    service = ctx["service"]
    version = context["snapshot_version"]
    event_loop.run_until_complete(service.rollback(version, trigger="api"))


@then("词条「BLM」的类型恢复为「CONCEPT」")
def verify_blm_restored_to_concept(event_loop, context):
    """验证回滚后词条恢复"""
    ctx = context["_svc"]
    service = ctx["service"]
    result = event_loop.run_until_complete(service.get_entry("BLM"))
    assert result is not None, "回滚后BLM应存在"
    assert result.entity_type == "CONCEPT", f"回滚后类型应为 CONCEPT，实际为 {result.entity_type}"
    _teardown_service(ctx, event_loop)


# ===================================================================
# Scenario 4: 删除词条 -> 热更新 -> 抽取不再匹配
# ===================================================================


@given("词条「BLM」已存在")
def entry_blm_exists(event_loop, context):
    """词条BLM已存在"""
    ctx = _build_service(event_loop)
    context["_svc"] = ctx
    service = ctx["service"]
    entry = DictionaryEntry(term="BLM", entity_type="CONCEPT")
    event_loop.run_until_complete(service.add_entry(entry, trigger="api"))
    event_loop.run_until_complete(service.refresh_dictionary())


@when("用户删除词条「BLM」")
def delete_entry_blm(event_loop, context):
    """删除词条"""
    ctx = context["_svc"]
    service = ctx["service"]
    event_loop.run_until_complete(service.delete_entry("BLM", trigger="api"))
    event_loop.run_until_complete(service.refresh_dictionary())


@then("规则基抽取器不识别「BLM方法论」中的「BLM」实体")
def verify_blm_not_recognized(event_loop, context):
    """验证BLM不再被识别"""
    ctx = context["_svc"]
    extractor = ctx["extractor"]

    async def _check():
        result = await extractor.extract_entities("BLM方法论")
        assert all(e.name != "BLM" for e in result.entities), "删除后不应识别BLM"
        return True

    event_loop.run_until_complete(_check())
    _teardown_service(ctx, event_loop)


# ===================================================================
# Scenario 5: 添加已存在词条 -> 409
# ===================================================================


@when("用户尝试添加词条「BLM」类型为「CONCEPT」")
def try_add_duplicate_blm(event_loop, context):
    """尝试添加重复词条"""
    ctx = context["_svc"]
    service = ctx["service"]
    entry = DictionaryEntry(term="BLM", entity_type="CONCEPT")
    try:
        event_loop.run_until_complete(service.add_entry(entry, trigger="api"))
        context["last_error"] = None
    except Exception as e:
        context["last_error"] = e


@then("系统返回错误码「EXCEPTION_271」")
def verify_error_code_271(context):
    """验证错误码"""
    err = context.get("last_error")
    assert err is not None, "应抛出异常"
    assert isinstance(err, DictionaryEntryConflictError), f"应为 DictionaryEntryConflictError，实际为 {type(err).__name__}"
    assert err.code == "EXCEPTION_271"


@then("错误HTTP状态码为409")
def verify_http_409(event_loop, context):
    """验证HTTP状态码 409 并清理"""
    from src.interfaces.api.exception_handlers import _get_http_status

    err = context["last_error"]
    status = _get_http_status(err)
    assert status == 409, f"HTTP 状态码应为 409，实际为 {status}"
    _teardown_service(context["_svc"], event_loop)


# ===================================================================
# Scenario 6: 修改不存在的词条 -> 404
# ===================================================================


@given("词条「不存在的词」不存在")
def entry_not_exist():
    """词条不存在——无需额外操作"""
    pass


@when("用户尝试修改词条「不存在的词」类型为「CONCEPT」")
def try_update_nonexistent(event_loop, context):
    """尝试修改不存在的词条"""
    ctx = _build_service(event_loop)
    context["_svc"] = ctx
    service = ctx["service"]
    entry = DictionaryEntry(term="不存在的词", entity_type="CONCEPT", version=2)

    try:
        event_loop.run_until_complete(service.update_entry("不存在的词", entry, trigger="api"))
        context["last_error"] = None
    except Exception as e:
        context["last_error"] = e


@then("系统返回错误码「EXCEPTION_270」")
def verify_error_code_270(context):
    """验证错误码270"""
    err = context.get("last_error")
    assert err is not None, "应抛出异常"
    assert isinstance(err, DictionaryNotFoundError), f"应为 DictionaryNotFoundError，实际为 {type(err).__name__}"
    assert err.code == "EXCEPTION_270"


@then("错误HTTP状态码为404")
def verify_http_404(event_loop, context):
    """验证HTTP状态码404"""
    from src.interfaces.api.exception_handlers import _get_http_status

    err = context["last_error"]
    status = _get_http_status(err)
    assert status == 404, f"HTTP 状态码应为 404，实际为 {status}"
    _teardown_service(context["_svc"], event_loop)


# ===================================================================
# Scenario 7: 删除不存在的词条 -> 404
# ===================================================================


@when("用户尝试删除词条「不存在的词」")
def try_delete_nonexistent(event_loop, context):
    """尝试删除不存在的词条"""
    ctx = _build_service(event_loop)
    context["_svc"] = ctx
    service = ctx["service"]

    try:
        event_loop.run_until_complete(service.delete_entry("不存在的词", trigger="api"))
        context["last_error"] = None
    except Exception as e:
        context["last_error"] = e


# 复用 then 步骤：EXCEPTION_270 + 404


# ===================================================================
# Scenario 8: 回滚到不存在的版本 -> 404
# ===================================================================


@given("词典版本号为1")
def dict_version_is_1(event_loop, context):
    """词典版本号为1"""
    ctx = _build_service(event_loop)
    context["_svc"] = ctx


@when("用户尝试回滚至版本号99")
def try_rollback_to_version_99(event_loop, context):
    """尝试回滚到不存在的版本"""
    ctx = context["_svc"]
    service = ctx["service"]
    try:
        event_loop.run_until_complete(service.rollback(99, trigger="api"))
        context["last_error"] = None
    except Exception as e:
        context["last_error"] = e


# 复用 then 步骤：EXCEPTION_270 + 404


# ===================================================================
# Scenario 9: 并发修改版本冲突 -> 409
# ===================================================================


@given("词条「BLM」已存在版本号为1")
def entry_blm_version_1(event_loop, context):
    """词条BLM版本号为1"""
    ctx = _build_service(event_loop)
    context["_svc"] = ctx
    service = ctx["service"]
    entry = DictionaryEntry(term="BLM", entity_type="CONCEPT")
    event_loop.run_until_complete(service.add_entry(entry, trigger="api"))


@when("用户尝试以版本号1和版本号1同时修改词条「BLM」")
def try_concurrent_update(event_loop, context):
    """尝试并发修改——第一次修改成功，第二次基于旧版本修改应冲突"""
    ctx = context["_svc"]
    service = ctx["service"]

    # 第一次修改成功（version 1 -> 2）
    entry = DictionaryEntry(term="BLM", entity_type="STRATEGY", version=1)
    event_loop.run_until_complete(service.update_entry("BLM", entry, trigger="api"))

    # 第二次基于旧版本 1 修改 -> 冲突（当前版本已为 2，仍传 version=1 应冲突）
    entry2 = DictionaryEntry(term="BLM", entity_type="TOOL", version=1)
    try:
        event_loop.run_until_complete(service.update_entry("BLM", entry2, trigger="api"))
        context["last_error"] = None
    except Exception as e:
        context["last_error"] = e


@then("后一次修改返回错误码「EXCEPTION_272」")
def verify_error_code_272(context):
    """验证版本冲突错误码"""
    err = context.get("last_error")
    assert err is not None, "应抛出 DictionaryVersionConflictError"
    assert isinstance(err, DictionaryVersionConflictError), f"应为 DictionaryVersionConflictError，实际为 {type(err).__name__}"
    assert err.code == "EXCEPTION_272"


@then("错误HTTP状态码为409")
def verify_http_409_version_conflict(event_loop, context):
    """验证HTTP状态码409"""
    from src.interfaces.api.exception_handlers import _get_http_status

    err = context["last_error"]
    status = _get_http_status(err)
    assert status == 409, f"HTTP 状态码应为 409，实际为 {status}"
    _teardown_service(context["_svc"], event_loop)
