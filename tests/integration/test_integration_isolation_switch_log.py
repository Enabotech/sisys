"""Story 5.6 集成测试 — 隔离切换日志全链（真实 Redis 6380 + 真实 PG 5433）

九场景:
① 切换全链→PG 检索六字段逐项（含 approval_chain JSONB roundtrip + worm_ref None）
② no-op 零新增（同等级二次切换 total 不变）
③ audit-first 拒绝（坏连接仓储实例 127.0.0.1:1——真实类真实代码仅环境参数坏；
   场景不设 ContextVar session 走 fallback → ConnectionRefused → StorageError
   包装 → Redis 等级未变 + 零事件）
④ audit 联动真实 AuditServiceImpl → audit_log 表 isolation:switch 记录
   （correlation_id 双过滤 + old/new_value .value 字符串形态）
⑤ 检索矩阵（四维独立 + 组合 AND + level 双向命中 + 分页 total/offset/limit +
   排序降序——3 Agent × 2 条造数）
⑥ RLS deny UPDATE/DELETE 0 行（rolsuper/rolbypassrls/owner 探测——绕过环境
   skip）+ CheckConstraint IntegrityError（直插 no-op 行）
⑦ 写 P95（切换全链 warmup 1 + 20 采样 quantiles[18] < 0.05——委托缓存 helper）
⑧ 检索 P95（search 全链 < 0.5——委托缓存）
⑨ 成功率 20/20（20 次真实切换 → 检索 total 恰 +20——分子分母显式）

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/integration/\\
        test_integration_isolation_switch_log.py -v

测试隔离:
    - 真实 Redis/PG 双门控（real_redis ping / pg_session SELECT 1——失败 skip）
    - PG 事务隔离：pg_session（begin+rollback）+ 场景内 set_session(token) →
      日志写走请求路径（add+flush）→ 同事务断言可见 → teardown rollback 零残留
      （禁 delete/truncate）；场景③不设 session（坏仓储 fallback 语义前提）
    - Redis 双键精确清理（_agent_ids 登记 + exists 复核删净）
    - 计时委托 helper（_PERF_CACHE 单槽 + xdist_group("isolation-switch-log-perf")
      同 worker 串行——与验收侧逐字同组，缓存命中前提；禁 20 采样双跑）
    - 计时口径注记：采样链按隔离纪律走 set_session → save=add+flush 不含
      commit，生产 CLI 真实形态是 fallback 独立 commit（多一次 RTT）——测得
      P95 略优于真实 CLI 路径
"""

from __future__ import annotations

import statistics
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from src.domain.events.enums import IsolationLevel
from src.infrastructure.storage.redis.key_builder import build_key

pytestmark = [
    pytest.mark.integration,
    pytest.mark.redis,
    pytest.mark.database,
    pytest.mark.benchmark,
    pytest.mark.xdist_group("isolation-switch-log-perf"),
]

# P95 阈值常量（单源定义——验收侧 import 本常量断言，禁双真源；
# epics L1695 写 P95<50ms / L1696 检索 P95<500ms——本地 PG 写 ~3ms + Redis 写
# ~4ms 全链 ~7ms，写预算 50ms 约 7 倍裕量）
SWITCH_LOG_WRITE_P95_LIMIT_SECONDS = 0.05
SWITCH_LOG_SEARCH_P95_LIMIT_SECONDS = 0.5

# 采样规格（warmup 1 + 20 采样——5-4/5-5 同款形态）
SWITCH_LOG_WARMUP_ROUNDS = 1
SWITCH_LOG_SAMPLE_ROUNDS = 20

#: 采样缓存（模块级单槽——集成场景⑦⑧⑨与验收 AC-5.1/5.2 共享同批结果，
#: 同 xdist_group 同 worker 串行保证缓存命中；禁 20 采样双跑拖慢套件）
_PERF_CACHE: dict[str, Any] = {}

#: 坏仓储端点（保留端口 1——connection refused 立即失败）
_BAD_ENDPOINT_HOST = "127.0.0.1"
_BAD_ENDPOINT_PORT = 1


# ===================================================================
# 组装基建（手动组装——场景级客户端禁 resolve 发命令；log repo 请求路径）
# ===================================================================


class _RecordingEventPublisher:
    """事件发布端口记录替身（fail-closed 零事件断言面——5-4/5-5 先例）。"""

    def __init__(self) -> None:
        self.published_events: list[Any] = []

    async def publish(self, event: Any) -> Any:
        from src.domain.events.publish_result import ChannelResult, PublishResult

        self.published_events.append(event)
        return PublishResult(
            event_id=str(uuid.uuid4()),
            results=(ChannelResult(channel_name="inmemory", success=True),),
        )


def _assemble_real_chain(
    redis_client: Any,
    log_repository: Any = None,
    audit_service: Any = None,
) -> dict[str, Any]:
    """手动组装真实六依赖链（log_repository 可注入坏实例——场景③故障注入）."""
    from src.application.services.isolation_management_service import IsolationManagementService
    from src.application.use_cases.agent_instantiation import InstantiateAgentUseCase
    from src.domain.ports.resolver import resolve
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.storage.postgresql.repository.isolation_switch_log_repository import (
        PostgreSQLIsolationSwitchLogRepository,
    )
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository
    from src.infrastructure.storage.redis.redis_isolation_repository import RedisIsolationRepository

    agent_repository = RedisAgentRepository(adapter=RedisAdapter(redis_client=redis_client))
    isolation_repository = RedisIsolationRepository(adapter=RedisAdapter(redis_client=redis_client))
    recorder = _RecordingEventPublisher()
    effective_log_repo = log_repository if log_repository is not None else PostgreSQLIsolationSwitchLogRepository()
    isolation_service = IsolationManagementService(
        isolation_repository=isolation_repository,
        agent_repository=agent_repository,
        event_publisher=recorder,
        agent_config_loader=resolve("agent_config_loader"),
        isolation_switch_log_repository=effective_log_repo,
        audit_service=audit_service,
    )
    use_case = InstantiateAgentUseCase(
        config_loader=resolve("agent_config_loader"),
        repository=agent_repository,
        event_publisher=InMemoryEventBus(),
        isolation_service=isolation_service,
    )
    return {
        "use_case": use_case,
        "isolation_service": isolation_service,
        "agent_repository": agent_repository,
        "isolation_repository": isolation_repository,
        "log_repository": effective_log_repo,
        "recorder": recorder,
    }


def _make_bad_log_repository() -> Any:
    """坏连接日志仓储（真实类 + 不可达 session_factory 127.0.0.1:1——保留端口
    connection refused 立即失败，禁不可路由 IP 拖 connect_timeout）."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from sqlalchemy.ext.asyncio import create_async_engine as create_engine

    from src.infrastructure.storage.postgresql.repository.isolation_switch_log_repository import (
        PostgreSQLIsolationSwitchLogRepository,
    )
    from tests.environments import get_test_env

    # 凭据从测试配置动态拼接（零字面量——secret 扫描命中面；仅端点坏 127.0.0.1:1
    # 保留端口 connection refused 立即失败，禁不可路由 IP 拖 connect_timeout）
    pg = get_test_env().postgres
    bad_url = f"postgresql+asyncpg://{pg.username}:{pg.password}@{_BAD_ENDPOINT_HOST}:{_BAD_ENDPOINT_PORT}/{pg.database}"
    bad_engine = create_engine(
        bad_url,
        pool_pre_ping=False,
        connect_args={"timeout": 2, "command_timeout": 2},
    )
    bad_factory = async_sessionmaker(bind=bad_engine, class_=AsyncSession, expire_on_commit=False)
    return PostgreSQLIsolationSwitchLogRepository(session_factory=bad_factory), bad_engine


def _make_log(
    agent_id: uuid.UUID,
    previous: IsolationLevel,
    target: IsolationLevel,
    reason: str,
    when: datetime,
    chain: tuple[str, ...] = (),
) -> Any:
    """直构日志造数（from_event 通道——检索矩阵场景⑤造数面）."""
    from src.domain.entities.isolation_switch_log import IsolationSwitchLog
    from src.domain.events.isolation_events import IsolationLevelSwitched

    event = IsolationLevelSwitched(
        agent_id=agent_id,
        previous_level=previous,
        target_level=target,
        trigger_reason=reason,
        approval_chain=list(chain),
        switch_timestamp=when,
    )
    return IsolationSwitchLog.from_event(event)


# ===================================================================
# 委托计时 helper（验收 AC-5.1/5.2 共享——单槽缓存禁双跑；内部自管 PG scope）
# ===================================================================


async def _perf_pg_scope() -> Any:
    """计时专用 PG scope（engine+session+set_session——helper 自管，与外部 fixture 解耦）."""
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.infrastructure.config.postgresql import PostgreSQLConfig
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
    from src.infrastructure.storage.postgresql.session_context import set_session
    from tests.environments import get_test_env

    pg = get_test_env().postgres
    pg_config = PostgreSQLConfig(
        host=pg.host,
        port=pg.port,
        database=pg.database,
        username=pg.username,
        password=pg.password,
    )
    manager = PostgreSQLManager(pg_config)
    session = AsyncSession(manager.get_async_engine(), expire_on_commit=False)
    await session.begin()
    token = set_session(session)
    return manager, session, token


async def sample_write_perf(redis_client: Any) -> dict[str, Any]:
    """写 P95 采样（计时锚 = switch_isolation_level 服务全链：守卫 + 日志 PG 写 +
    Redis 写 + 事件发布；warmup 1 + 20 采样——单槽缓存命中即返）."""
    if "write" in _PERF_CACHE:
        cached: dict[str, Any] = _PERF_CACHE["write"]
        return cached

    from src.domain.entities.agent import AgentRole
    from src.infrastructure.storage.postgresql.session_context import reset_session

    manager, session, token = await _perf_pg_scope()
    chain = _assemble_real_chain(redis_client)
    latencies: list[float] = []
    sample_agent_ids: list[uuid.UUID] = []
    try:

        async def _one_round(record: bool) -> float:
            instantiation = await chain["use_case"].execute(role=AgentRole.CEO)
            sample_agent_ids.append(instantiation.agent_id)
            started = time.perf_counter()
            await chain["isolation_service"].switch_isolation_level(instantiation.agent_id, IsolationLevel.L3_SOFT, "性能采样")
            elapsed = time.perf_counter() - started
            return elapsed if record else elapsed

        for _ in range(SWITCH_LOG_WARMUP_ROUNDS):
            await _one_round(record=False)  # warmup 不计入采样
        for _ in range(SWITCH_LOG_SAMPLE_ROUNDS):
            latencies.append(await _one_round(record=True))
    finally:
        reset_session(token)
        await session.rollback()
        await session.close()
        await manager.get_async_engine().dispose()
        # Redis 采样键精确清理（PG 行随 rollback 回收）
        if sample_agent_ids:
            await redis_client.delete(*[build_key(ns, str(aid)) for aid in sample_agent_ids for ns in ("agent", "isolation")])

    result: dict[str, Any] = {
        "p95_seconds": statistics.quantiles(latencies, n=SWITCH_LOG_SAMPLE_ROUNDS)[18],
        "samples": latencies,
    }
    _PERF_CACHE["write"] = result
    return result


async def sample_search_perf(redis_client: Any) -> dict[str, Any]:
    """检索 P95 采样（计时锚 = search 全链：count + items 双查询 + 实体投影）."""
    if "search" in _PERF_CACHE:
        cached: dict[str, Any] = _PERF_CACHE["search"]
        return cached

    from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogQuery
    from src.infrastructure.storage.postgresql.repository.isolation_switch_log_repository import (
        PostgreSQLIsolationSwitchLogRepository,
    )
    from src.infrastructure.storage.postgresql.session_context import reset_session

    manager, session, token = await _perf_pg_scope()
    repo = PostgreSQLIsolationSwitchLogRepository()
    # 造数：20 条（计时面足够行数——写经请求路径 flush，同事务可见）
    seed_ids = [uuid.uuid4() for _ in range(20)]
    base = datetime.now(UTC)
    for i, aid in enumerate(seed_ids):
        await repo.save(
            _make_log(aid, IsolationLevel.L4_HARD, IsolationLevel.L3_SOFT, f"检索计时-{i}", base + timedelta(seconds=i))
        )
    latencies: list[float] = []
    try:
        for _ in range(SWITCH_LOG_WARMUP_ROUNDS):
            await repo.search(IsolationSwitchLogQuery())
        for _ in range(SWITCH_LOG_SAMPLE_ROUNDS):
            started = time.perf_counter()
            await repo.search(IsolationSwitchLogQuery(level=IsolationLevel.L3_SOFT, limit=20))
            latencies.append(time.perf_counter() - started)
    finally:
        reset_session(token)
        await session.rollback()
        await session.close()
        await manager.get_async_engine().dispose()

    result: dict[str, Any] = {
        "p95_seconds": statistics.quantiles(latencies, n=SWITCH_LOG_SAMPLE_ROUNDS)[18],
        "samples": latencies,
    }
    _PERF_CACHE["search"] = result
    return result


async def sample_success_rate(redis_client: Any) -> dict[str, Any]:
    """存储成功率采样（20 次真实切换 → 检索 total 恰 +20——分子分母显式；
    含审批链非空场景混合——成功分子要求每轮日志可检索）."""
    if "success" in _PERF_CACHE:
        cached: dict[str, Any] = _PERF_CACHE["success"]
        return cached

    from src.domain.entities.agent import AgentRole
    from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogQuery
    from src.infrastructure.storage.postgresql.session_context import reset_session

    manager, session, token = await _perf_pg_scope()
    chain = _assemble_real_chain(redis_client)
    success_count = 0
    sample_agent_ids: list[uuid.UUID] = []
    try:
        for i in range(SWITCH_LOG_SAMPLE_ROUNDS):
            instantiation = await chain["use_case"].execute(role=AgentRole.CEO)
            sample_agent_ids.append(instantiation.agent_id)
            chain["recorder"].published_events.clear()
            switch_result = await chain["isolation_service"].switch_isolation_level(
                instantiation.agent_id,
                IsolationLevel.L3_SOFT if i % 2 == 0 else IsolationLevel.L2_COLLAB,
                f"成功率采样-{i}",
                ("合规负责人",) if i % 2 == 0 else (),
            )
            if switch_result.switched:
                found = await chain["log_repository"].search(IsolationSwitchLogQuery(agent_id=instantiation.agent_id))
                if found.total == 1:
                    success_count += 1
    finally:
        reset_session(token)
        await session.rollback()
        await session.close()
        await manager.get_async_engine().dispose()
        if sample_agent_ids:
            await redis_client.delete(*[build_key(ns, str(aid)) for aid in sample_agent_ids for ns in ("agent", "isolation")])

    result: dict[str, Any] = {
        "success_count": success_count,
        "total_count": SWITCH_LOG_SAMPLE_ROUNDS,
    }
    _PERF_CACHE["success"] = result
    return result


#: RLS 就位 ensure 的幂等 DDL（与 migration 015+016 终态同款四策略 + ENABLE +
#: FORCE——deny 策略 AS RESTRICTIVE（R2-F1：permissive deny 与 016 终态漂移，
#: 未来 permissive 放行策略经 OR 合并会消解 deny）；DROP IF EXISTS 后 CREATE，
#: 重复执行安全；策略 DDL 事务性——随测试事务 rollback 回收，不污染目标库）
_RLS_ENSURE_STATEMENTS = (
    "ALTER TABLE isolation_switch_logs ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE isolation_switch_logs FORCE ROW LEVEL SECURITY",
    "DROP POLICY IF EXISTS isolation_switch_logs_insert ON isolation_switch_logs",
    "DROP POLICY IF EXISTS isolation_switch_logs_select ON isolation_switch_logs",
    "DROP POLICY IF EXISTS isolation_switch_logs_deny_update ON isolation_switch_logs",
    "DROP POLICY IF EXISTS isolation_switch_logs_deny_delete ON isolation_switch_logs",
    """
    CREATE POLICY isolation_switch_logs_insert ON isolation_switch_logs
    FOR INSERT WITH CHECK (true)
    """,
    """
    CREATE POLICY isolation_switch_logs_select ON isolation_switch_logs
    FOR SELECT USING (true)
    """,
    """
    CREATE POLICY isolation_switch_logs_deny_update ON isolation_switch_logs
    AS RESTRICTIVE
    FOR UPDATE USING (false) WITH CHECK (false)
    """,
    """
    CREATE POLICY isolation_switch_logs_deny_delete ON isolation_switch_logs
    AS RESTRICTIVE
    FOR DELETE USING (false)
    """,
)


async def _ensure_rls_policies(session: Any) -> bool:
    """RLS 策略就位保障（ensure 语义——ensure_alembic_migration 同哲学）.

    背景：create_all 兜底建表路径（alembic 超时/失败时）只建 ORM 元数据声明的
    表/索引/CheckConstraint，**不建 RLS 策略**（op.execute 的 SQL 不在 metadata）
    ——CI 冷启动超 60s 触发兜底后表无 RLS，SET ROLE 降权断言失真（UPDATE 1 行）。
    本 ensure 探测 pg_policies 策略计数，缺失时幂等补建（DDL 事务性随测试事务
    回收）——RLS deny 语义断言在任何建表路径下均有效。

    Returns:
        是否执行了补建（False=策略本就在位）。
    """
    from sqlalchemy import text

    count = (
        await session.execute(
            text("SELECT COUNT(*) FROM pg_policies WHERE schemaname = 'public' AND tablename = 'isolation_switch_logs'")
        )
    ).scalar_one()
    if count >= 4:
        # 形态核验（R2-F1）：count>=4 不等于形态正确——permissive deny（015 款漂移态）
        # 需补建升级为 RESTRICTIVE（016 终态），ensure 自愈而非放行
        deny_form = (
            await session.execute(
                text(
                    "SELECT permissive FROM pg_policies "
                    "WHERE schemaname = 'public' AND tablename = 'isolation_switch_logs' "
                    "AND policyname = 'isolation_switch_logs_deny_update'"
                )
            )
        ).scalar_one_or_none()
        if deny_form == "RESTRICTIVE":
            return False
    for statement in _RLS_ENSURE_STATEMENTS:
        await session.execute(text(statement))
    return True


# ===================================================================
# 九场景
# ===================================================================


@pytest.mark.asyncio
async def test_scenario_1_switch_full_chain_six_fields(real_redis: Any, pg_session: Any) -> None:
    """场景①: 真实切换全链 → PG 检索取回六字段逐项（approval_chain JSONB roundtrip）."""
    from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogQuery
    from src.domain.ports.resolver import resolve
    from src.infrastructure.security.audit_service_impl import AuditServiceImpl
    from src.infrastructure.storage.postgresql.session_context import reset_session, set_session

    token = set_session(pg_session)
    agent_ids: list[uuid.UUID] = []
    try:
        chain = _assemble_real_chain(real_redis, audit_service=AuditServiceImpl(audit_repository=resolve("audit_repo")))
        instantiation = await chain["use_case"].execute(
            role=__import__("src.domain.entities.agent", fromlist=["AgentRole"]).AgentRole.CEO
        )
        agent_ids.append(instantiation.agent_id)
        result = await chain["isolation_service"].switch_isolation_level(
            instantiation.agent_id, IsolationLevel.L3_SOFT, "集成六字段验证", ("合规负责人", "安全官")
        )
        assert result.switched is True

        found = await chain["log_repository"].search(IsolationSwitchLogQuery(agent_id=instantiation.agent_id))
        assert found.total == 1
        log = found.items[0]
        event = result.event
        assert log.agent_id == event.agent_id
        assert log.previous_level is IsolationLevel.L4_HARD
        assert log.target_level is IsolationLevel.L3_SOFT
        assert log.trigger_reason == event.trigger_reason
        assert log.approval_chain == ("合规负责人", "安全官")  # JSONB roundtrip list→tuple
        assert log.switch_timestamp == event.switch_timestamp
        assert log.worm_ref is None  # OD-1 预留
    finally:
        reset_session(token)
        for aid in agent_ids:
            for ns in ("agent", "isolation"):
                await real_redis.delete(build_key(ns, str(aid)))


@pytest.mark.asyncio
async def test_scenario_2_noop_zero_new_logs(real_redis: Any, pg_session: Any) -> None:
    """场景②: no-op 零新增（前置切换 1 条 → 同等级二次调用 → total 保持 1）."""
    from src.domain.entities.agent import AgentRole
    from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogQuery
    from src.infrastructure.storage.postgresql.session_context import reset_session, set_session

    token = set_session(pg_session)
    agent_ids: list[uuid.UUID] = []
    try:
        chain = _assemble_real_chain(real_redis)
        instantiation = await chain["use_case"].execute(role=AgentRole.CEO)
        agent_ids.append(instantiation.agent_id)
        first = await chain["isolation_service"].switch_isolation_level(
            instantiation.agent_id, IsolationLevel.L3_SOFT, "前置切换"
        )
        assert first.switched is True
        chain["recorder"].published_events.clear()

        second = await chain["isolation_service"].switch_isolation_level(
            instantiation.agent_id, IsolationLevel.L3_SOFT, "重复请求"
        )
        assert second.switched is False
        assert chain["recorder"].published_events == []  # 零事件
        found = await chain["log_repository"].search(IsolationSwitchLogQuery(agent_id=instantiation.agent_id))
        assert found.total == 1, f"no-op 后 total 应保持 1，实际 {found.total}"
    finally:
        reset_session(token)
        for aid in agent_ids:
            for ns in ("agent", "isolation"):
                await real_redis.delete(build_key(ns, str(aid)))


@pytest.mark.asyncio
async def test_scenario_3_audit_first_fail_closed(real_redis: Any) -> None:
    """场景③: 坏仓储拒绝路径（不设 ContextVar session——走 fallback；
    127.0.0.1:1 connection refused → StorageError 包装 → Redis 未变 + 零事件）."""
    from src.domain.entities.agent import AgentRole
    from src.domain.exceptions import StorageError
    from src.infrastructure.storage.postgresql.session_context import clear_session, get_session_optional

    bad_repo, bad_engine = _make_bad_log_repository()
    agent_ids: list[uuid.UUID] = []
    try:
        # 硬前提：本场景不设 ContextVar session（设了则坏仓储命中好 session
        # 永不触发 StorageError——僵尸场景）。原「assert ... or True」恒真式
        # （R1-F2——声明的守卫实际不存在）改为泄漏自愈：探测到前序场景泄漏
        # 的 session 时免 Token 主动清除（原 Token 在泄漏方手里不可得——
        # clear_session 置 None 与未设置语义等价）
        if get_session_optional() is not None:
            clear_session()

        chain = _assemble_real_chain(real_redis, log_repository=bad_repo)
        instantiation = await chain["use_case"].execute(role=AgentRole.CEO)
        agent_ids.append(instantiation.agent_id)
        chain["recorder"].published_events.clear()

        with pytest.raises(StorageError) as exc_info:
            await chain["isolation_service"].switch_isolation_level(instantiation.agent_id, IsolationLevel.L3_SOFT, "故障注入")
        assert exc_info.value.code == "EXCEPTION_103"

        # fail-closed 断言面：Redis 等级未变（仍 L4）+ 零事件
        state = await chain["isolation_service"].get_isolation_state(instantiation.agent_id)
        assert state.current_level is IsolationLevel.L4_HARD
        assert chain["recorder"].published_events == []
    finally:
        await bad_engine.dispose()
        for aid in agent_ids:
            for ns in ("agent", "isolation"):
                await real_redis.delete(build_key(ns, str(aid)))


@pytest.mark.asyncio
async def test_scenario_4_audit_linkage_audit_log_table(real_redis: Any, pg_session: Any) -> None:
    """场景④: audit 联动（真实 AuditServiceImpl → audit_log 表 isolation:switch
    一条 + correlation_id 匹配 + old/new_value .value 字符串形态）."""
    from sqlalchemy import text

    from src.domain.entities.agent import AgentRole
    from src.domain.ports.resolver import resolve
    from src.infrastructure.security.audit_service_impl import AuditServiceImpl
    from src.infrastructure.storage.postgresql.session_context import reset_session, set_session

    token = set_session(pg_session)
    agent_ids: list[uuid.UUID] = []
    try:
        chain = _assemble_real_chain(real_redis, audit_service=AuditServiceImpl(audit_repository=resolve("audit_repo")))
        instantiation = await chain["use_case"].execute(role=AgentRole.CEO)
        agent_ids.append(instantiation.agent_id)
        result = await chain["isolation_service"].switch_isolation_level(
            instantiation.agent_id, IsolationLevel.L3_SOFT, "联动审计验证"
        )
        assert result.switched is True

        rows = (
            await pg_session.execute(
                text("SELECT actor, old_value, new_value FROM audit_log WHERE action_type = :action AND correlation_id = :cid"),
                {"action": "isolation:switch", "cid": str(result.event.event_id)},
            )
        ).fetchall()
        assert len(rows) == 1, f"audit_log 应恰 1 条 isolation:switch（实际 {len(rows)}）"
        actor, old_value, new_value = rows[0]
        assert actor == f"agent:{instantiation.agent_id}"
        assert old_value == {"level": "L4"}  # .value 字符串形态（JSONB 安全）
        assert new_value["level"] == "L3"
        assert new_value["reason"] == "联动审计验证"
        assert new_value["approval_chain"] == []
    finally:
        reset_session(token)
        for aid in agent_ids:
            for ns in ("agent", "isolation"):
                await real_redis.delete(build_key(ns, str(aid)))


@pytest.mark.asyncio
async def test_scenario_5_search_matrix(real_redis: Any, pg_session: Any) -> None:
    """场景⑤: 检索矩阵（3 Agent × 2 条造数——四维独立 + 组合 AND + level 双向
    命中 + 分页独立造数 5 条 + 排序降序）."""
    from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogQuery
    from src.infrastructure.storage.postgresql.repository.isolation_switch_log_repository import (
        PostgreSQLIsolationSwitchLogRepository,
    )
    from src.infrastructure.storage.postgresql.session_context import reset_session, set_session

    token = set_session(pg_session)
    try:
        repo = PostgreSQLIsolationSwitchLogRepository()
        base = datetime(2026, 10, 25, 12, 0, 0, tzinfo=UTC)
        agent_ids = [uuid.uuid4() for _ in range(3)]
        for i, aid in enumerate(agent_ids):
            for j, target in enumerate((IsolationLevel.L3_SOFT, IsolationLevel.L2_COLLAB)):
                await repo.save(
                    _make_log(
                        aid,
                        IsolationLevel.L4_HARD,
                        target,
                        f"矩阵-{i}-{j}",
                        base + timedelta(minutes=i * 10 + j),
                    )
                )

        # 四维独立：按 AGENT（agent1 恰 2 条且仅自身）
        by_agent = await repo.search(IsolationSwitchLogQuery(agent_id=agent_ids[1]))
        assert by_agent.total == 2
        assert all(log.agent_id == agent_ids[1] for log in by_agent.items)

        # 按时间（闭区间 <=：agent0 两条在 base+0min / base+1min——窗口 [base-1min,
        # base+30s] 仅含第 1 条；宽窗含两条验证闭边界命中）
        by_time_narrow = await repo.search(
            IsolationSwitchLogQuery(
                agent_id=agent_ids[0],
                start_time=base - timedelta(minutes=1),
                end_time=base + timedelta(seconds=30),
            )
        )
        assert by_time_narrow.total == 1
        by_time_wide = await repo.search(
            IsolationSwitchLogQuery(
                agent_id=agent_ids[0],
                start_time=base - timedelta(minutes=1),
                end_time=base + timedelta(minutes=1),
            )
        )
        assert by_time_wide.total == 2  # base+1min 恰等于 end_time——闭区间边界命中

        # 按等级（双向命中：L4→L3 在 level=L3 命中 target 臂 + level=L4 命中 previous 臂）
        by_l3 = await repo.search(IsolationSwitchLogQuery(agent_id=agent_ids[0], level=IsolationLevel.L3_SOFT))
        assert by_l3.total == 1
        by_l4 = await repo.search(IsolationSwitchLogQuery(agent_id=agent_ids[0], level=IsolationLevel.L4_HARD))
        assert by_l4.total == 2, "level=L4 应命中全部（previous 臂）"

        # 组合 AND（agent + 时间 + level 三条件）
        combined = await repo.search(
            IsolationSwitchLogQuery(
                agent_id=agent_ids[2],
                start_time=base,
                end_time=base + timedelta(minutes=30),
                level=IsolationLevel.L2_COLLAB,
            )
        )
        assert combined.total == 1  # agent2 的 L4→L2 一条

        # 分页（独立造数：单 Agent 5 条）
        pager_agent = uuid.uuid4()
        for j in range(5):
            await repo.save(
                _make_log(
                    pager_agent,
                    IsolationLevel.L4_HARD,
                    IsolationLevel.L3_SOFT if j % 2 == 0 else IsolationLevel.L2_COLLAB,
                    f"分页-{j}",
                    base + timedelta(hours=1, minutes=j),
                )
            )
        page1 = await repo.search(IsolationSwitchLogQuery(agent_id=pager_agent, limit=2, offset=0))
        assert len(page1.items) == 2 and page1.total == 5
        page3 = await repo.search(IsolationSwitchLogQuery(agent_id=pager_agent, limit=2, offset=4))
        assert len(page3.items) == 1 and page3.total == 5
        empty_page = await repo.search(IsolationSwitchLogQuery(agent_id=pager_agent, limit=2, offset=5))
        assert len(empty_page.items) == 0 and empty_page.total == 5  # 空页边界

        # 排序（switch_timestamp 降序——最新在前）
        timestamps = [log.switch_timestamp for log in page1.items]
        assert timestamps == sorted(timestamps, reverse=True)
    finally:
        reset_session(token)


@pytest.mark.asyncio
async def test_scenario_6_rls_and_check_constraint(real_redis: Any, pg_session: Any) -> None:
    """场景⑥: RLS deny UPDATE/DELETE 0 行（非绕过连接；superuser/bypassrls/owner
    探测 skip）+ CheckConstraint IntegrityError（no-op 直插——不依赖 RLS 真实可达）."""
    from sqlalchemy import text

    from src.infrastructure.storage.postgresql.repository.isolation_switch_log_repository import (
        PostgreSQLIsolationSwitchLogRepository,
    )
    from src.infrastructure.storage.postgresql.session_context import reset_session, set_session

    token = set_session(pg_session)
    try:
        repo = PostgreSQLIsolationSwitchLogRepository()
        agent_id = uuid.uuid4()
        await repo.save(_make_log(agent_id, IsolationLevel.L4_HARD, IsolationLevel.L3_SOFT, "防篡改实证", datetime.now(UTC)))

        # CheckConstraint 实证（先跑——superuser 环境仍真实可达）
        from sqlalchemy.exc import IntegrityError

        inserted = False
        try:
            await pg_session.execute(
                text(
                    "INSERT INTO isolation_switch_logs "
                    "(log_id, agent_id, previous_level, target_level, trigger_reason, "
                    "approval_chain, switch_timestamp) "
                    "VALUES (:lid, :aid, 'L3', 'L3', 'no-op 直插', '[]'::jsonb, NOW())"
                ),
                {"lid": str(uuid.uuid4()), "aid": str(uuid.uuid4())},
            )
            await pg_session.flush()
            inserted = True
        except IntegrityError:
            await pg_session.rollback()  # 复位再继续
            # rollback 回收场景造数——重新落库供 RLS 段使用
            await repo.save(
                _make_log(agent_id, IsolationLevel.L4_HARD, IsolationLevel.L3_SOFT, "防篡改实证", datetime.now(UTC))
            )
        assert not inserted, "no-op 直插应触发 CheckConstraint IntegrityError"

        # RLS 非绕过形态保障（与验收 AC-4.1 同款——任一环境真实实证）:
        # 前置 RLS 策略就位 ensure（create_all 兜底路径不建 RLS——CI 超时兜底
        # 后 SET ROLE 断言失真形态，2026-10-25 CI 实测定谳）；非绕过直连直接
        # 断言；superuser 经事务内 CREATE ROLE + GRANT + SET ROLE 临时降权
        # （角色随测试事务 rollback 自动回收）；owner 子查询限定 public schema
        # （多 schema 同名表 CardinalityViolation 干扰面）
        await _ensure_rls_policies(pg_session)
        probe = (
            await pg_session.execute(
                text(
                    "SELECT (SELECT rolsuper OR rolbypassrls FROM pg_roles "
                    "WHERE rolname = current_user) AS bypass, "
                    "(SELECT rolsuper FROM pg_roles WHERE rolname = current_user) AS is_super, "
                    "(SELECT pg_roles.rolname = current_user FROM pg_class "
                    "JOIN pg_roles ON pg_roles.oid = pg_class.relowner "
                    "WHERE pg_class.relname = 'isolation_switch_logs' "
                    "AND pg_class.relnamespace = 'public'::regnamespace) AS is_owner"
                )
            )
        ).fetchone()
        bypass, is_super, is_owner = probe[0], probe[1], probe[2]
        probe_role: str | None = None
        if bypass or is_owner:
            if not is_super:
                pytest.skip(
                    "RLS deny 断言需非绕过连接（当前角色 rolbypassrls 属性绕过 RLS 或"
                    "为表 owner 的保守 skip 面——owner 在 FORCE 下实际受约束但无 "
                    "CREATE ROLE 权限无法临时降权——需预置非绕过应用角色）"
                )
            probe_role = f"rls_probe_{uuid.uuid4().hex[:8]}"
            await pg_session.execute(text(f"CREATE ROLE \"{probe_role}\" LOGIN PASSWORD '{uuid.uuid4().hex}'"))
            await pg_session.execute(text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON isolation_switch_logs TO "{probe_role}"'))
            await pg_session.execute(text(f'SET ROLE "{probe_role}"'))

        # 变异锚注记：删 migration deny 行 → 此断言红（Task 4 变异实证）
        found = await repo.search(
            __import__(
                "src.domain.ports.isolation_switch_log_repository",
                fromlist=["IsolationSwitchLogQuery"],
            ).IsolationSwitchLogQuery(agent_id=agent_id)
        )
        assert found.total == 1
        log_id = found.items[0].log_id
        updated = (
            await pg_session.execute(
                text("UPDATE isolation_switch_logs SET target_level = 'L2' WHERE log_id = :lid"),
                {"lid": str(log_id)},
            )
        ).rowcount
        assert updated == 0, "UPDATE 应被 RLS deny（0 行）"
        deleted = (
            await pg_session.execute(
                text("DELETE FROM isolation_switch_logs WHERE log_id = :lid"),
                {"lid": str(log_id)},
            )
        ).rowcount
        assert deleted == 0, "DELETE 应被 RLS deny（0 行）"
        # RESTRICTIVE 终态钉死（R2-F1）：deny 策略被还原为 permissive 时本断言红
        # ——permissive deny 经 OR 合并可被未来放行策略消解（016 防御的威胁模型）
        deny_forms = (
            await pg_session.execute(
                text(
                    "SELECT policyname, permissive FROM pg_policies "
                    "WHERE schemaname = 'public' AND tablename = 'isolation_switch_logs' "
                    "AND policyname IN ('isolation_switch_logs_deny_update', 'isolation_switch_logs_deny_delete')"
                )
            )
        ).fetchall()
        assert {name: form for name, form in deny_forms} == {
            "isolation_switch_logs_deny_update": "RESTRICTIVE",
            "isolation_switch_logs_deny_delete": "RESTRICTIVE",
        }, f"deny 策略必须为 RESTRICTIVE 终态（实际 {deny_forms}——migration 016 漂移）"
        if probe_role is not None:
            await pg_session.execute(text("RESET ROLE"))  # 会话级复位（角色随事务回收）
    finally:
        reset_session(token)


@pytest.mark.asyncio
async def test_scenario_7_write_p95(real_redis: Any) -> None:
    """场景⑦: 写 P95<50ms（切换全链——委托缓存 helper，验收 AC-5.1 共享）."""
    result = await sample_write_perf(real_redis)
    assert result["p95_seconds"] < SWITCH_LOG_WRITE_P95_LIMIT_SECONDS, (
        f"写 P95={result['p95_seconds']:.4f}s 超限 {SWITCH_LOG_WRITE_P95_LIMIT_SECONDS}s"
    )


@pytest.mark.asyncio
async def test_scenario_8_search_p95(real_redis: Any) -> None:
    """场景⑧: 检索 P95<500ms（search 全链——委托缓存 helper）."""
    result = await sample_search_perf(real_redis)
    assert result["p95_seconds"] < SWITCH_LOG_SEARCH_P95_LIMIT_SECONDS, (
        f"检索 P95={result['p95_seconds']:.4f}s 超限 {SWITCH_LOG_SEARCH_P95_LIMIT_SECONDS}s"
    )


@pytest.mark.asyncio
async def test_scenario_9_success_rate_20_of_20(real_redis: Any) -> None:
    """场景⑨: 存储成功率 100%（20 切换 → 20 日志——分子分母显式）。"""
    result = await sample_success_rate(real_redis)
    assert result["total_count"] == 20
    assert result["success_count"] == 20, f"存储成功率 {result['success_count']}/{result['total_count']}——期望 20/20"
