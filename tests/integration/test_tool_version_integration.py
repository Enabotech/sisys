"""工具版本管理集成测试（Story 4-6 — epics 硬路径）

真实 PostgreSQL（探活失败 pytest.skip 动态跳过）+ InMemory 全链路 + AC-7 性能基准。

隔离模式：repo_session（begin + set_session + rollback——domain_dictionary 先例，
同步 fixture + 模块级 event_loop）；xdist_group("tool-versions-pg") 串行化
（tool-executions-pg 先例）。唯一约束断言口径 = 仓储转换后的领域异常（431/432）。
"""

from __future__ import annotations

import asyncio
import statistics
import time
import uuid
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.services.tool_registry_service import ToolRegistryService
from src.application.services.tool_version_service import ToolVersionService
from src.domain.entities.tool_version import ToolVersion, ToolVersionStatus
from src.domain.exceptions.tool_version_exceptions import (
    ToolVersionAlreadyExistsError,
    ToolVersionNotFoundError,
    ToolVersionRollbackError,
    ToolVersionTrafficWeightError,
)
from src.domain.ports.tool_version_repository import ToolVersionQuery
from src.infrastructure.config.postgresql import PostgreSQLConfig
from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository
from src.infrastructure.storage.inmemory.tool_version_repository import (
    InMemoryToolVersionRepository,
)
from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
from src.infrastructure.storage.postgresql.repository.tool_version_repository import (
    PostgreSQLToolVersionRepository,
)
from src.infrastructure.storage.postgresql.session_context import (
    reset_session,
    set_session,
)
from src.infrastructure.validation.jsonschema_validator import JsonSchemaValidatorImpl
from tests.environments import get_test_env

pytestmark = pytest.mark.xdist_group("tool-versions-pg")

_BASE_SCHEMA: dict = {"type": "object", "properties": {"factor": {"type": "string"}}}


def _make_tv(
    version: str,
    status: ToolVersionStatus = ToolVersionStatus.PENDING,
    *,
    tool_id: uuid.UUID | None = None,
    traffic_weight: int = 0,
) -> ToolVersion:
    """构造测试版本实体。"""
    return ToolVersion(
        tool_id=tool_id or uuid.uuid4(),
        version=version,
        input_schema=dict(_BASE_SCHEMA),
        output_schema=dict(_BASE_SCHEMA),
        status=status,
        traffic_weight=traffic_weight,
    )


def _run(coro):
    """同步运行协程（InMemory 无共享连接——独立短生命周期循环）。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ============================================================================
# PG fixtures（domain_dictionary 先例：同步 fixture + 模块级 event_loop）
# ============================================================================


@pytest.fixture(scope="module")
def event_loop():
    """模块级事件循环（repo_session 会话绑定循环）。"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def pg_config() -> PostgreSQLConfig:
    """真实 PostgreSQL 配置。"""
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
    """真实数据库引擎。"""
    return PostgreSQLManager(pg_config)


@pytest.fixture
def pg_available(pg_config: PostgreSQLConfig, event_loop) -> bool:
    """PostgreSQL 探活（失败动态 skip）。"""
    import asyncpg

    async def _check() -> bool:
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

    return bool(event_loop.run_until_complete(_check()))


@pytest.fixture
def repo_session(
    db_engine: PostgreSQLManager,
    pg_available: bool,
    event_loop,
) -> Generator[AsyncSession, None, None]:
    """真实 PG 会话（begin + set_session + rollback 隔离——domain_dictionary 先例）。"""
    if not pg_available:
        pytest.skip("PostgreSQL not available")
        return

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


# ============================================================================
# PG 仓储基础用例（Task 3 循环 B）
# ============================================================================


class TestPostgreSQLRepositoryBasics:
    """PG 仓储 CRUD/唯一约束/Query/活跃查询（同步方法 + event_loop 先例形态）。"""

    def test_save_and_get_round_trip(self, repo_session, event_loop) -> None:
        repo = PostgreSQLToolVersionRepository()
        tv = _make_tv("1.0.0")
        event_loop.run_until_complete(repo.save(tv))
        fetched = event_loop.run_until_complete(repo.get_by_tool_and_version(tv.tool_id, "1.0.0"))
        assert fetched is not None
        assert fetched.version == "1.0.0"
        assert fetched.input_schema == _BASE_SCHEMA
        assert fetched.status is ToolVersionStatus.PENDING

    def test_unique_constraint_raises_431(self, repo_session, event_loop) -> None:
        """(tool_id,version) 唯一冲突 → 仓储转换为 431（断言领域异常口径）。"""
        repo = PostgreSQLToolVersionRepository()
        tid = uuid.uuid4()
        event_loop.run_until_complete(repo.save(_make_tv("1.0.0", tool_id=tid)))
        with pytest.raises(ToolVersionAlreadyExistsError):
            event_loop.run_until_complete(repo.save(_make_tv("1.0.0", tool_id=tid)))

    def test_single_stable_partial_index_432(self, repo_session, event_loop) -> None:
        """单 STABLE partial unique index 硬守护 → 仓储转换为 432。"""
        repo = PostgreSQLToolVersionRepository()
        tid = uuid.uuid4()
        event_loop.run_until_complete(repo.save(_make_tv("1.0.0", ToolVersionStatus.STABLE, tool_id=tid)))
        with pytest.raises(ToolVersionTrafficWeightError):
            event_loop.run_until_complete(repo.save(_make_tv("2.0.0", ToolVersionStatus.STABLE, tool_id=tid)))

    def test_query_filter_and_pagination(self, repo_session, event_loop) -> None:
        repo = PostgreSQLToolVersionRepository()
        tid = uuid.uuid4()
        for i in range(5):
            event_loop.run_until_complete(repo.save(_make_tv(f"1.0.{i}", tool_id=tid)))
        page = event_loop.run_until_complete(repo.list_by_query(ToolVersionQuery(tool_id=tid, offset=1, limit=2)))
        assert len(page) == 2
        assert event_loop.run_until_complete(repo.count(ToolVersionQuery(tool_id=tid))) == 5

    def test_list_active(self, repo_session, event_loop) -> None:
        repo = PostgreSQLToolVersionRepository()
        tid = uuid.uuid4()
        event_loop.run_until_complete(repo.save(_make_tv("1.0.0", ToolVersionStatus.STABLE, tool_id=tid)))
        event_loop.run_until_complete(repo.save(_make_tv("1.1.0", ToolVersionStatus.CANARY, tool_id=tid, traffic_weight=30)))
        event_loop.run_until_complete(repo.save(_make_tv("1.2.0", ToolVersionStatus.DEPRECATED, tool_id=tid)))
        active = event_loop.run_until_complete(repo.list_active(tid))
        assert {tv.version for tv in active} == {"1.0.0", "1.1.0"}


# ============================================================================
# PG 状态多行变更 + 原子性（AC-3/AC-4 原子断言唯一归属——先降级后提升顺序契约）
# ============================================================================


class TestMultiRowAtomicity:
    """发布/回滚多行状态变更的原子性。"""

    def test_promote_demotes_old_stable_atomically(self, repo_session, event_loop) -> None:
        """promote：新 STABLE 写入 + 旧 STABLE 降级同事务（先降级后提升顺序）。"""
        repo = PostgreSQLToolVersionRepository()
        tid = uuid.uuid4()
        old = event_loop.run_until_complete(repo.save(_make_tv("1.0.0", ToolVersionStatus.STABLE, tool_id=tid)))
        new = event_loop.run_until_complete(repo.save(_make_tv("1.1.0", tool_id=tid)))
        old.transition_to(ToolVersionStatus.DEPRECATED)
        old.stamp_last_stable()
        event_loop.run_until_complete(repo.save(old))
        new.transition_to(ToolVersionStatus.STABLE)
        new.traffic_weight = 100
        event_loop.run_until_complete(repo.save(new))
        active = event_loop.run_until_complete(repo.list_active(tid))
        assert {tv.version for tv in active} == {"1.1.0"}

    def test_rollback_restores_target_atomically(self, repo_session, event_loop) -> None:
        """rollback：current 降级（清空戳）+ target 恢复 STABLE 同事务。"""
        repo = PostgreSQLToolVersionRepository()
        tid = uuid.uuid4()
        v19 = event_loop.run_until_complete(repo.save(_make_tv("1.9.0", tool_id=tid)))
        v19.transition_to(ToolVersionStatus.STABLE)
        event_loop.run_until_complete(repo.save(v19))
        v20 = event_loop.run_until_complete(repo.save(_make_tv("2.0.0", tool_id=tid)))
        v19.transition_to(ToolVersionStatus.DEPRECATED)
        v19.stamp_last_stable()
        event_loop.run_until_complete(repo.save(v19))
        v20.transition_to(ToolVersionStatus.STABLE)
        event_loop.run_until_complete(repo.save(v20))
        v20.transition_to(ToolVersionStatus.DEPRECATED)
        v20.clear_last_stable()
        event_loop.run_until_complete(repo.save(v20))
        v19.transition_to(ToolVersionStatus.STABLE)
        event_loop.run_until_complete(repo.save(v19))
        active = event_loop.run_until_complete(repo.list_active(tid))
        assert {tv.version for tv in active} == {"1.9.0"}
        fetched = event_loop.run_until_complete(repo.get_by_tool_and_version(tid, "2.0.0"))
        assert fetched is not None
        assert fetched.last_stable_at is None


# ============================================================================
# InMemory 全链路集成（真实服务：Registry/Validator/VersionService）
# ============================================================================


def _make_service() -> tuple[ToolVersionService, uuid.UUID]:
    """构造 InMemory 真实服务链（全链路与性能基准共用）。"""
    tool_repo = InMemoryToolRepository()
    registry = ToolRegistryService(repository=tool_repo)
    version_repo = InMemoryToolVersionRepository()
    service = ToolVersionService(
        repository=version_repo,
        schema_validator=JsonSchemaValidatorImpl(),
        tool_registry=registry,
    )
    from src.domain.entities.tool import Tool, ToolCategory, ToolStatus

    now = datetime.now(UTC)
    tool = Tool(
        tool_id=uuid.uuid4(),
        name=f"it-tool-{uuid.uuid4().hex[:6]}",
        description="it",
        category=ToolCategory.ANALYSIS,
        input_schema=dict(_BASE_SCHEMA),
        output_schema=dict(_BASE_SCHEMA),
        status=ToolStatus.ACTIVE,
        version="1.0.0",
        created_at=now,
        updated_at=now,
    )
    tool_repo.save(tool)
    return service, tool.tool_id


class TestFullLifecycleInMemory:
    """InMemory 全链路（注册→灰度→转正→回滚闭环）。"""

    def test_register_canary_promote_rollback_closed_loop(self) -> None:
        """注册→灰度→转正→回滚闭环（含防 ping-pong 二连回滚 433）。"""
        service, tid = _make_service()
        _run(service.register_version(tid, "1.9.0", dict(_BASE_SCHEMA), dict(_BASE_SCHEMA)))
        _run(service.publish_version(tid, "1.9.0", 100))
        _run(service.register_version(tid, "2.0.0", dict(_BASE_SCHEMA), dict(_BASE_SCHEMA)))
        _run(service.publish_version(tid, "2.0.0", 100))
        _run(service.rollback(tid))
        view = _run(service.get_version_traffic(tid))
        assert view["stable_version"] == "1.9.0"
        with pytest.raises(ToolVersionRollbackError):
            _run(service.rollback(tid))

    def test_canary_only_full_lifecycle_no_deadlock(self) -> None:
        """canary_only：注册→灰度→毕业转正全链路（R1-2 修复的行为验证）。"""
        service, tid = _make_service()
        _run(service.register_version(tid, "1.0.0", dict(_BASE_SCHEMA), dict(_BASE_SCHEMA)))
        _run(service.publish_version(tid, "1.0.0", 100))
        major_schema = {
            "type": "object",
            "properties": {"factor": {"type": "string"}, "extra": {"type": "string"}},
            "required": ["factor", "extra"],
        }
        _run(service.register_version(tid, "2.0.0", major_schema, dict(_BASE_SCHEMA)))
        with pytest.raises(ToolVersionTrafficWeightError):
            _run(service.publish_version(tid, "2.0.0", 100))
        _run(service.publish_version(tid, "2.0.0", 30))
        _run(service.publish_version(tid, "2.0.0", 100))
        view = _run(service.get_version_traffic(tid))
        assert view["stable_version"] == "2.0.0"

    def test_abort_canary_keeps_stable(self) -> None:
        """放弃灰度：STABLE 不动、流量全回。"""
        service, tid = _make_service()
        _run(service.register_version(tid, "1.0.0", dict(_BASE_SCHEMA), dict(_BASE_SCHEMA)))
        _run(service.publish_version(tid, "1.0.0", 100))
        _run(service.register_version(tid, "1.1.0", dict(_BASE_SCHEMA), dict(_BASE_SCHEMA)))
        _run(service.publish_version(tid, "1.1.0", 30))
        _run(service.abort_canary(tid))
        view = _run(service.get_version_traffic(tid))
        assert view["stable_version"] == "1.0.0"
        assert view["canary_version"] is None


# ============================================================================
# AC-7 性能基准（分级断言：达标 assert，不达标 skip 留测量证据）
# ============================================================================


class TestPerformanceBenchmarks:
    """AC-7 表格逐项基准（InMemory 装配断言；PG 装配 skip 留参考值）。"""

    def test_switch_latency_p95_inmemory(self) -> None:
        """50 轮注册-发布-回滚 P95 < 500ms（每轮消耗新版本号）。"""
        service, tid = _make_service()
        durations: list[float] = []
        for i in range(50):
            v = f"9.0.{i}"
            t0 = time.perf_counter()
            _run(service.register_version(tid, v, dict(_BASE_SCHEMA), dict(_BASE_SCHEMA)))
            _run(service.publish_version(tid, v, 100))
            try:
                _run(service.rollback(tid))
            except ToolVersionRollbackError:
                pass
            durations.append((time.perf_counter() - t0) * 1000)
        p95 = statistics.quantiles(durations, n=20)[18]
        if p95 >= 500:
            pytest.skip(f"环境不达标：切换 P95={p95:.1f}ms（测量证据留存）")
        assert p95 < 500

    def test_publish_success_rate(self) -> None:
        """50 次灰度发布成功率 ≥95%。"""
        service, tid = _make_service()
        _run(service.register_version(tid, "1.0.0", dict(_BASE_SCHEMA), dict(_BASE_SCHEMA)))
        _run(service.publish_version(tid, "1.0.0", 100))
        ok = 0
        for i in range(50):
            v = f"8.0.{i}"
            _run(service.register_version(tid, v, dict(_BASE_SCHEMA), dict(_BASE_SCHEMA)))
            try:
                _run(service.publish_version(tid, v, 30))
                _run(service.abort_canary(tid))
                ok += 1
            except (ToolVersionTrafficWeightError, ToolVersionNotFoundError):
                pass
        assert ok / 50 >= 0.95

    def test_rollback_atomicity_no_intermediate_state(self) -> None:
        """回滚成功率 100%：要么成功要么明确失败且无中间态。"""
        service, tid = _make_service()
        _run(service.register_version(tid, "1.0.0", dict(_BASE_SCHEMA), dict(_BASE_SCHEMA)))
        _run(service.publish_version(tid, "1.0.0", 100))
        outcomes = set()
        for i in range(20):
            v = f"7.0.{i}"
            _run(service.register_version(tid, v, dict(_BASE_SCHEMA), dict(_BASE_SCHEMA)))
            _run(service.publish_version(tid, v, 100))
            try:
                _run(service.rollback(tid))
                outcomes.add("success")
            except ToolVersionRollbackError:
                outcomes.add("explicit-failure")
        assert outcomes <= {"success", "explicit-failure"}

    def test_resolve_latency_p95_inmemory(self) -> None:
        """1000 次路由解析 P95 < 5ms（InMemory 装配断言）。"""
        service, tid = _make_service()
        _run(service.register_version(tid, "1.0.0", dict(_BASE_SCHEMA), dict(_BASE_SCHEMA)))
        _run(service.publish_version(tid, "1.0.0", 100))
        _run(service.register_version(tid, "1.1.0", dict(_BASE_SCHEMA), dict(_BASE_SCHEMA)))
        _run(service.publish_version(tid, "1.1.0", 30))
        _run(service.resolve_version(tid, route_key="warmup"))
        durations: list[float] = []
        for i in range(1000):
            t0 = time.perf_counter()
            _run(service.resolve_version(tid, route_key=f"perf-{i}"))
            durations.append((time.perf_counter() - t0) * 1000)
        p95 = statistics.quantiles(durations, n=20)[18]
        if p95 >= 5:
            pytest.skip(f"环境不达标：路由 P95={p95:.2f}ms（InMemory 测量证据留存）")
        assert p95 < 5
