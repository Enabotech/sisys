"""隔离切换日志记录验收测试（Story 5.6 — FR-AC-06 审计留痕面）.

模板基准：tests/acceptance/test_acceptance_postgresql_relational_layer.py（R6 基准）
+ 5-4/5-5 R6 改造形态（@scenario 显式绑定 + context dict fixture + _run_async 同循环
+ 步骤化门控 + 双面清理 + 延迟 import）。禁 then-pass 占位（PG 模板历史缺陷）。

17 场景三属性分档表（层级 / 服务依赖 / 断言面）：

| 场景 | 层级 | 服务依赖 | 断言面 |
|------|------|---------|--------|
| AC-1.1 from_event 六字段映射 | 端口级 | 无 | 字段完整性 |
| AC-1.2 实体不变量与不可变形态 | 端口级 | 无 | 异常契约（242 五场景）|
| AC-2.1 切换成功六字段落库 | 服务级 | Redis+PG | 字段完整性 + audit-first |
| AC-2.2 no-op 零日志新增 | 服务级 | Redis+PG | 顺序与计数 |
| AC-2.3 audit-first 拒绝路径 | 服务级 | Redis（单门控——断言面零好 PG 依赖） | 顺序与计数（fail-closed） |
| AC-2.4 audit 联动记录 | 服务级 | Redis+PG | 字段完整性（audit_log 表） |
| AC-3.1 按 AGENT 检索 | 服务级 | PG | 检索矩阵 |
| AC-3.2 时间+等级组合检索 | 服务级 | PG | 检索矩阵（level 双向命中） |
| AC-3.3 分页与排序 | 服务级 | PG | 检索矩阵（total/offset/limit） |
| AC-4.1 RLS 篡改拒绝 | 服务级 | PG | 防篡改（绕过环境 skip） |
| AC-4.2 worm_ref 预留与表结构 | 服务级 | PG | 防篡改（ORM/表结构） |
| AC-5.1 写 P95<50ms | 服务级 | Redis+PG | 性能（委托集成缓存） |
| AC-5.2 检索 P95<500ms + 成功率 | 服务级 | Redis+PG | 性能（委托 + 20/20） |
| AC-6.1 组合根接线 | 端口级 | 无（resolve 级联惰性） | 接线内省（禁发真实命令） |
| AC-6.2 CLI isolation-logs | 服务级 | PG | CLI fallback 全链（生产真实形态） |
| AC-6.3 架构合规静态扫描 | 端口级 | 无 | 静态扫描（AST） |
| AC-6.4 回归面资产在位 | 端口级 | 无 | 静态（文件存在 + 枚举注册） |

实施注记（AC-6.2 形态定谳——dev 阶段实验裁定）：
    故事钉死的「set_session(test_session) 作用域内 in-process 调 main()」经跨循环实验
    证伪——CLI 内部 asyncio.run 新建事件循环，同一 AsyncSession 绑定创建循环后跨循环
    使用必炸（RuntimeError: attached to a different loop）；fresh session 可在 CLI 循环
    首用但循环关闭后无法 rollback/close（InterfaceError）。裁定采用生产真实形态：造数走
    fallback 独立会话 commit（故事 AC-5 口径注记自认「生产 CLI 真实形态是 fallback 独立
    commit」）+ CLI 全链走 fallback（每个 asyncio.run 自建自用自关，零跨循环）+ superuser
    连接清理造数行（RLS deny DELETE 对 superuser 不设防；非绕过环境本场景动态 skip——
    与 AC-4.1 RLS 探测同款纪律）。

测试隔离条款：
    - Redis：场景级独立客户端 + 双键精确清理（_agent_ids 登记 + exists 复核删净；
      禁 delete_pattern/flush/全库 scan_iter）
    - PG：场景级 session（set_session token）→ 日志写走请求路径（add+flush）→ 同事务
      断言可见 → teardown rollback + close + reset_session(token)（ContextVar 完整复位
      是 AC-2.3「不设 session」前提的硬依赖）→ 零残留零 delete/truncate
    - AC-2.3 坏仓储场景不设 ContextVar session（双模式 get_session 优先——设了测试
      session 则坏仓储命中好 session 永不触发 StorageError；不设则 RuntimeError →
      走坏 factory → 连接失败快速抛出）
    - 计时委托集成模块（_PERF_CACHE 单槽缓存 + xdist_group 同 worker 串行——禁双跑）

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/acceptance/\\
        test_acceptance_isolation_switch_log.py -v
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import uuid
from collections.abc import Coroutine, Generator
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from src.infrastructure.storage.redis.key_builder import build_key

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"

# 文件名不含 redis/postgres 关键词，acceptance conftest 自动 marker 不生效——显式声明
# 双服务 marker；xdist_group("isolation-switch-log-perf") 与集成计时场景逐字同组——
# loadgroup 同 worker 串行是 _PERF_CACHE 委托缓存命中的前提（5-4 委托模式照抄）
pytestmark = [
    pytest.mark.acceptance,
    pytest.mark.redis,
    pytest.mark.database,
    pytest.mark.xdist_group("isolation-switch-log-perf"),
]

#: CLI 造数清理锚（AC-6.2——造数行 log_id 登记于 context，superuser 清理按 id 精确删除）
_BAD_ENDPOINT_FACTORY_HOST = "127.0.0.1"
_BAD_ENDPOINT_FACTORY_PORT = 1


class _RecordingEventPublisher:
    """手写 duck-typing 事件捕获类（直接实现 EventPublisher 端口契约——5-4/5-5 先例）.

    publish 追加事件到 published_events 并返回真实 PublishResult（成功单通道），
    供「恰好一次/零次」计数断言（fail-closed 判别力——比「至少一次」强）。
    """

    def __init__(self) -> None:
        self.published_events: list[Any] = []

    async def publish(self, event: Any) -> Any:
        from src.domain.events.publish_result import ChannelResult, PublishResult

        self.published_events.append(event)
        return PublishResult(
            event_id=str(uuid.uuid4()),
            results=(ChannelResult(channel_name="inmemory", success=True),),
        )


def _run_async(event_loop: asyncio.AbstractEventLoop, coro: Coroutine[Any, Any, Any]) -> Any:
    """同循环调度（BDD 步骤禁 @pytest.mark.asyncio——context 数据丢失）."""
    return event_loop.run_until_complete(coro)


# =============================================================================
# 场景级 context fixture（Redis 独立客户端 + PG 惰性事务隔离 session + 双面清理）
# =============================================================================


@pytest.fixture
def context(
    event_loop: asyncio.AbstractEventLoop,
    acceptance_env_config: Any,
) -> Generator[dict[str, Any], None, None]:
    """场景级独立 Redis 客户端 + PG 惰性 session + 同循环关闭 + 双面精确清理.

    PG session 惰性创建（首个需要 PG 的步骤经 _ensure_pg_session 触发）——
    端口级场景（AC-1/AC-6.1/6.3/6.4）零 PG 连接开销。teardown 顺序：
    reset_session(token)（ContextVar 完整复位——AC-2.3 不设 session 前提的
    硬依赖）→ rollback → close → Redis 双键 delete → exists 复核 → close。
    """
    import redis.asyncio as aioredis

    redis_client = aioredis.Redis(
        host=acceptance_env_config.redis.host,
        port=acceptance_env_config.redis.port,
        password=acceptance_env_config.redis.password,
        decode_responses=True,
    )
    ctx: dict[str, Any] = {
        "_loop": event_loop,
        "_redis_client": redis_client,
        "_agent_ids": [],
        "_pg": None,  # 惰性：{"engine", "session", "token"}
    }
    yield ctx

    # teardown ①：PG session 完整复位（reset → rollback → close → 池 dispose；
    # AC-6.2 CLI 场景无 PG session。dispose 是连接池彻底释放——同 worker 多场景
    # engine 累积会压迫 PG max_connections 产生偶发 dbapi 连接失败）
    pg = ctx.get("_pg")
    if pg is not None:
        from src.infrastructure.storage.postgresql.session_context import reset_session

        reset_session(pg["token"])
        _run_async(event_loop, pg["session"].rollback())
        if "_rls_probe_role" in ctx:
            # RLS 降权探针双保险复位（角色本体已随事务 rollback 回收；RESET ROLE
            # 防连接池归还会话的 SET ROLE 状态残留——engine dispose 已杜绝复用，
            # 此处再显式复位）
            from sqlalchemy import text

            _run_async(event_loop, pg["session"].execute(text("RESET ROLE")))
            ctx.pop("_rls_probe_role")
        _run_async(event_loop, pg["session"].close())
        _run_async(event_loop, pg["engine"].close())
        _run_async(event_loop, pg["engine"].get_async_engine().dispose())
    # teardown ②：Redis 双键精确删除（禁 delete_pattern/flush——多 worker 共享测试实例）
    for agent_id in ctx["_agent_ids"]:
        for namespace in ("agent", "isolation"):
            _run_async(event_loop, redis_client.delete(build_key(namespace, str(agent_id))))
    # exists 复核：自产键删净（唯一例外——443 拒绝路径的预生成 uuid 不登记）
    for agent_id in ctx["_agent_ids"]:
        for namespace in ("agent", "isolation"):
            key = build_key(namespace, str(agent_id))
            assert not _run_async(event_loop, redis_client.exists(key)), f"自产键未清理: {key}"
    _run_async(event_loop, redis_client.close())


def _ensure_pg_session(context: dict[str, Any]) -> dict[str, Any]:
    """惰性创建场景级 PG 事务隔离 session 并 set_session（token 登记 context）.

    Returns:
        {"engine", "session", "token"} 字典（重复调用返回同一实例）
    """
    existing: dict[str, Any] | None = context["_pg"]
    if existing is not None:
        return existing

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
    engine = PostgreSQLManager(pg_config)
    session = AsyncSession(engine.get_async_engine(), expire_on_commit=False)
    token = set_session(session)
    pg_data: dict[str, Any] = {"engine": engine, "session": session, "token": token}
    context["_pg"] = pg_data
    return pg_data


# =============================================================================
# 门控步骤（步骤化门控——禁 Background 背景块）
# =============================================================================

_migration_run = False


def _ensure_alembic_migration(context: dict[str, Any]) -> None:
    """确保 schema 存在（alembic 优先 + create_all 兜底——模块级单次短路）."""
    global _migration_run
    if _migration_run:
        return
    from tests.environments import get_test_env

    pg = get_test_env().postgres
    alembic_ini = REPO_ROOT / "deploy/postgresql/alembic/alembic.ini"
    migration_success = False
    if alembic_ini.exists():
        env = {
            "POSTGRES_HOST": pg.host,
            "POSTGRES_PORT": str(pg.port),
            "POSTGRES_USERNAME": pg.username,
            "POSTGRES_PASSWORD": pg.password,
            "POSTGRES_DATABASE": pg.database,
        }
        try:
            result = subprocess.run(
                ["poetry", "run", "alembic", "-c", str(alembic_ini), "upgrade", "head"],
                cwd=str(REPO_ROOT),
                env={**os.environ, **env},
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0 or "already up to date" in result.stdout:
                migration_success = True
            else:
                print(f"Alembic upgrade warning: {result.stderr}")
        except Exception as e:  # 门控兜底（失败转 create_all，最终 skip）
            print(f"Alembic upgrade failed: {e}")
    if not migration_success:
        try:
            from src.infrastructure.storage.postgresql.models import Base
            from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager

            engine = PostgreSQLManager(
                __import__(
                    "src.infrastructure.config.postgresql",
                    fromlist=["PostgreSQLConfig"],
                ).PostgreSQLConfig(
                    host=pg.host,
                    port=pg.port,
                    database=pg.database,
                    username=pg.username,
                    password=pg.password,
                )
            )
            Base.metadata.create_all(engine.get_sync_engine())
        except Exception as e:  # 兜底失败唯一出口是 skip（门控纪律）
            pytest.skip(f"Failed to create schema: {e}")
    _migration_run = True


@given("Redis 缓存服务可用")
def given_redis_service_available(context: dict[str, Any]) -> None:
    """Redis 门控（ping 失败动态 skip——禁写死 @pytest.mark.skip）."""
    try:
        _run_async(context["_loop"], context["_redis_client"].ping())
    except Exception as exc:
        pytest.skip(f"Redis not available: {exc}")


@given("PostgreSQL 服务可用")
def given_postgresql_service_available(context: dict[str, Any]) -> None:
    """PG 连接门控（asyncpg 真连探测 + alembic 迁移确保表在位——失败动态 skip）."""
    import asyncpg

    from tests.environments import get_test_env

    pg = get_test_env().postgres

    async def _check() -> bool:
        try:
            conn = await asyncpg.connect(
                host=pg.host,
                port=pg.port,
                user=pg.username,
                password=pg.password,
                database=pg.database,
            )
            await conn.close()
            return True
        except Exception:  # 门控探测（任何失败统一转 skip）
            return False

    probe_loop = asyncio.new_event_loop()
    try:
        is_available = probe_loop.run_until_complete(_check())
    finally:
        probe_loop.close()
    if not is_available:
        pytest.skip(f"PostgreSQL not available at {pg.host}:{pg.port}")
    _ensure_alembic_migration(context)


# =============================================================================
# 组装与造数 helper（手动组装纪律——禁 resolve 发真实命令）
# =============================================================================


def _instantiate_agent(context: dict[str, Any]) -> None:
    """真实 Agent 实例化（默认 L4）——真实链手动组装（六依赖服务）.

    组装件：真实 Redis 双仓储 + _RecordingEventPublisher + resolve("agent_config_loader")
    （无状态配置加载器合法）+ 真实 PG 日志仓储（请求路径——set_session 的 test session）
    + 可选真实 audit_service（audit 联动场景）。结果写入 context。
    """
    from src.application.services.isolation_management_service import IsolationManagementService
    from src.application.use_cases.agent_instantiation import InstantiateAgentUseCase
    from src.domain.entities.agent import AgentRole
    from src.domain.ports.resolver import resolve
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.security.audit_service_impl import AuditServiceImpl
    from src.infrastructure.storage.postgresql.repository.isolation_switch_log_repository import (
        PostgreSQLIsolationSwitchLogRepository,
    )
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository
    from src.infrastructure.storage.redis.redis_isolation_repository import RedisIsolationRepository

    loop: asyncio.AbstractEventLoop = context["_loop"]
    redis_client = context["_redis_client"]
    _ensure_pg_session(context)
    agent_repository = RedisAgentRepository(adapter=RedisAdapter(redis_client=redis_client))
    isolation_repository = RedisIsolationRepository(adapter=RedisAdapter(redis_client=redis_client))
    recorder = _RecordingEventPublisher()
    log_repo = PostgreSQLIsolationSwitchLogRepository()
    audit_service = AuditServiceImpl(
        audit_repository=resolve("audit_repo"),
    )
    isolation_service = IsolationManagementService(
        isolation_repository=isolation_repository,
        agent_repository=agent_repository,
        event_publisher=recorder,
        agent_config_loader=resolve("agent_config_loader"),
        isolation_switch_log_repository=log_repo,
        audit_service=audit_service,
    )
    use_case = InstantiateAgentUseCase(
        config_loader=resolve("agent_config_loader"),
        repository=agent_repository,
        event_publisher=InMemoryEventBus(),
        isolation_service=isolation_service,
    )
    result = _run_async(loop, use_case.execute(role=AgentRole.CEO))
    context["_agent_ids"].append(result.agent_id)
    context["agent_id"] = result.agent_id
    context["isolation_service"] = isolation_service
    context["event_recorder"] = recorder
    context["log_repository"] = log_repo


def _make_log_from_levels(
    agent_id: uuid.UUID,
    previous: Any,
    target: Any,
    reason: str,
    when: Any,
    chain: tuple[str, ...] = (),
) -> Any:
    """直构 IsolationSwitchLog 造数（检索场景——不经切换链，纯 PG 面造数）."""
    from datetime import UTC, datetime

    from src.domain.events.isolation_events import IsolationLevelSwitched

    event = IsolationLevelSwitched(
        agent_id=agent_id,
        previous_level=previous,
        target_level=target,
        trigger_reason=reason,
        approval_chain=list(chain),
        switch_timestamp=when if when is not None else datetime.now(UTC),
    )
    from src.domain.entities.isolation_switch_log import IsolationSwitchLog

    return IsolationSwitchLog.from_event(event)


# =============================================================================
# AC-1: IsolationSwitchLog 领域实体与事件映射（端口级——无服务依赖）
# =============================================================================


@scenario(
    "test_acceptance_isolation_switch_log.feature",
    "AC-1.1 - from_event 六字段映射与审计字段完整",
)
def test_ac_1_1_from_event_six_field_mapping(context: dict[str, Any]) -> None:
    """AC-1.1: 事件六字段零加工映射 + log_id 自铸 + worm_ref 预留."""


@scenario(
    "test_acceptance_isolation_switch_log.feature",
    "AC-1.2 - 实体不变量与不可变形态",
)
def test_ac_1_2_entity_invariants(context: dict[str, Any]) -> None:
    """AC-1.2: 242 五场景 + to_dict 序列化 + frozen 不可变."""


@given("已构造真实切换事件 IsolationLevelSwitched（六字段 payload）")
def given_real_switch_event(context: dict[str, Any]) -> None:
    """构造真实六字段事件（5-4 交付的 IsolationLevelSwitched——本 Story 数据源契约）."""
    from datetime import UTC, datetime

    from src.domain.events.isolation_events import IsolationLevelSwitched

    switch_ts = datetime(2026, 10, 25, 10, 0, 0, tzinfo=UTC)
    event = IsolationLevelSwitched(
        agent_id=uuid.UUID("0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"),
        previous_level=__import__("src.domain.events.enums", fromlist=["IsolationLevel"]).IsolationLevel.L4_HARD,
        target_level=__import__("src.domain.events.enums", fromlist=["IsolationLevel"]).IsolationLevel.L3_SOFT,
        trigger_reason="验收事件构造",
        approval_chain=["合规负责人", "安全官"],
        switch_timestamp=switch_ts,
    )
    context["event"] = event


@when("调用 IsolationSwitchLog.from_event 映射日志实体")
def when_from_event_mapping(context: dict[str, Any]) -> None:
    """from_event 工厂映射（事件 payload 单一真源——DC-1）."""
    from src.domain.entities.isolation_switch_log import IsolationSwitchLog

    context["log"] = IsolationSwitchLog.from_event(context["event"])


@then("六字段逐项映射完整（agent_id/switch_timestamp/previous_level/target_level/trigger_reason/approval_chain）")
def then_six_fields_mapped(context: dict[str, Any]) -> None:
    """六字段逐项相等断言（FR-AC-06 六要素）."""
    log = context["log"]
    event = context["event"]
    assert log.agent_id == event.agent_id
    assert log.previous_level == event.previous_level
    assert log.target_level == event.target_level
    assert log.trigger_reason == event.trigger_reason
    assert list(log.approval_chain) == list(event.approval_chain)


@then("switch_timestamp 取事件 switch_timestamp（单钟纪律）")
def then_switch_timestamp_single_clock(context: dict[str, Any]) -> None:
    """时间戳取事件 switch_timestamp 而非 event.timestamp（事件时刻=状态变更时刻）."""
    log = context["log"]
    event = context["event"]
    assert log.switch_timestamp == event.switch_timestamp
    assert log.switch_timestamp != event.timestamp or event.switch_timestamp == event.timestamp


@then("approval_chain 为不可变 tuple 形态（list 冻结拷贝）")
def then_approval_chain_tuple(context: dict[str, Any]) -> None:
    """list→tuple 冻结（不可变审计事实）."""
    log = context["log"]
    assert isinstance(log.approval_chain, tuple)
    assert not isinstance(log.approval_chain, list)


@then("log_id 为自铸 UUID4")
def then_log_id_uuid4(context: dict[str, Any]) -> None:
    """log_id 随机自铸 UUID4（from_event 不收外部 log_id）."""
    log = context["log"]
    assert isinstance(log.log_id, uuid.UUID)
    assert log.log_id.version == 4


@then("worm_ref 默认 None（OD-1 预留）")
def then_worm_ref_none(context: dict[str, Any]) -> None:
    """worm_ref nullable 预留（OD-1——WORM 归档归 V1 Story 13-4）."""
    assert context["log"].worm_ref is None


@given("实体构造通道已就绪")
def given_entity_channel_ready(context: dict[str, Any]) -> None:
    """AC-1.2 前置（dataclass 直构造注入非法值——from_event 自铸合法值无法产出非法输入）."""
    context["invalid_inputs"] = True


@when("分别注入五类非法输入构造日志实体")
def when_five_invalid_inputs(context: dict[str, Any]) -> None:
    """五场景：agent_id 非 UUID / 枚举非实例 / previous==target / reason 空白 / chain 非 tuple·元素非 str."""
    from datetime import UTC, datetime

    from src.domain.entities.isolation_switch_log import IsolationSwitchLog
    from src.domain.events.enums import IsolationLevel

    agent_id = uuid.uuid4()
    switch_ts = datetime.now(UTC)
    valid: dict[str, Any] = {
        "log_id": uuid.uuid4(),
        "agent_id": agent_id,
        "previous_level": IsolationLevel.L4_HARD,
        "target_level": IsolationLevel.L3_SOFT,
        "trigger_reason": "合法输入",
        "approval_chain": ("审批人",),
        "switch_timestamp": switch_ts,
    }

    def _make(**overrides: Any) -> Any:
        return IsolationSwitchLog(**{**valid, **overrides})

    cases: dict[str, Any] = {
        "agent_id_non_uuid": lambda: _make(agent_id="not-a-uuid"),
        "log_id_non_uuid": lambda: _make(log_id="not-a-uuid"),
        "previous_non_enum": lambda: _make(previous_level="L4"),  # str,Enum 混入语义——isinstance 先行
        "target_non_enum": lambda: _make(target_level="L3"),
        "levels_equal": lambda: _make(target_level=IsolationLevel.L4_HARD),
        "reason_blank": lambda: _make(trigger_reason="   "),
        "chain_non_tuple": lambda: _make(approval_chain=["审批人"]),
        "chain_element_blank": lambda: _make(approval_chain=("  ",)),
    }
    context["invalid_cases"] = cases
    # 合法基线（to_dict/frozen 断言用）
    context["log"] = IsolationSwitchLog(**valid)


@then("每类输入抛 EntityValidationError 242 且 context 携带字段名")
def then_entity_validation_error_242(context: dict[str, Any]) -> None:
    """242 三段式断言（isinstance → code → context 字段名稳定可断言）."""
    from src.domain.exceptions import EntityValidationError

    for name, case in context["invalid_cases"].items():
        try:
            case()
        except EntityValidationError as exc:
            assert exc.code == "EXCEPTION_242", f"{name}: code={exc.code}"
            assert exc.context, f"{name}: context 为空"
        except Exception as exc:  # 非 242 异常即断言失败
            pytest.fail(f"{name}: 抛出非 242 异常 {type(exc).__name__}")
        else:
            pytest.fail(f"{name}: 非法输入未抛 EntityValidationError")


@then("to_dict 全字段可序列化（UUID→str/Enum→value/datetime→ISO 8601/tuple→list）")
def then_to_dict_serializable(context: dict[str, Any]) -> None:
    """序列化惯例对齐 audit_log.to_dict."""
    from src.domain.events.enums import IsolationLevel

    log = context["log"]
    d = log.to_dict()
    assert isinstance(d["log_id"], str) and isinstance(d["agent_id"], str)
    assert d["previous_level"] == IsolationLevel.L4_HARD.value
    assert d["target_level"] == IsolationLevel.L3_SOFT.value
    assert "T" in d["switch_timestamp"]  # ISO 8601 形态
    assert isinstance(d["approval_chain"], list)
    assert d["worm_ref"] is None
    assert set(d) == {
        "log_id",
        "agent_id",
        "previous_level",
        "target_level",
        "trigger_reason",
        "approval_chain",
        "switch_timestamp",
        "worm_ref",
    }


@then("frozen 赋值被拒绝（日志不可变性）")
def then_frozen_rejected(context: dict[str, Any]) -> None:
    """frozen 断言（dataclasses.FrozenInstanceError——追加型日志事实不可变）."""
    import dataclasses

    log = context["log"]
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(log, "trigger_reason", "篡改尝试")


# =============================================================================
# AC-2: 切换链 audit-first 日志写入（服务级）
# =============================================================================


@scenario(
    "test_acceptance_isolation_switch_log.feature",
    "AC-2.1 - 切换成功六字段落库",
)
def test_ac_2_1_switch_success_persisted(context: dict[str, Any]) -> None:
    """AC-2.1: 真实切换 → PG 检索取回 → 六字段逐项一致."""


@scenario(
    "test_acceptance_isolation_switch_log.feature",
    "AC-2.2 - no-op 零日志新增",
)
def test_ac_2_2_noop_zero_logs(context: dict[str, Any]) -> None:
    """AC-2.2: 同等级二次调用 → 零日志（save 零调用语义）."""


@scenario(
    "test_acceptance_isolation_switch_log.feature",
    "AC-2.3 - audit-first 拒绝路径（日志写失败切换被拒）",
)
def test_ac_2_3_audit_first_fail_closed(context: dict[str, Any]) -> None:
    """AC-2.3: 坏仓储 → StorageError 上抛 → 切换被拒（Redis 未变 + 零事件）."""


@scenario(
    "test_acceptance_isolation_switch_log.feature",
    "AC-2.4 - audit 联动记录",
)
def test_ac_2_4_audit_linkage_record(context: dict[str, Any]) -> None:
    """AC-2.4: audit_log 表 isolation:switch 记录 + correlation_id 匹配."""


@given("真实 Agent 已实例化（默认 L4）")
def given_real_agent_instantiated(context: dict[str, Any]) -> None:
    """真实链实例化（Redis 真实写 + 默认 L4 硬隔离）."""
    _instantiate_agent(context)


@given("真实切换链已手动组装（含 PG 日志仓储）")
def given_real_chain_with_log_repo(context: dict[str, Any]) -> None:
    """链已在 _instantiate_agent 内组装（六依赖注入确认——audit_service 默认真实）."""
    assert context.get("log_repository") is not None
    assert context.get("isolation_service") is not None


@given(parsers.parse('真实 Agent 已实例化并已切换到 "{level}"'))
def given_agent_switched_to(context: dict[str, Any], level: str) -> None:
    """实例化 + 先行切换（造 no-op 前置态）."""
    from src.domain.events.enums import IsolationLevel

    _instantiate_agent(context)
    result = _run_async(
        context["_loop"],
        context["isolation_service"].switch_isolation_level(context["agent_id"], IsolationLevel(level), "前置切换", ()),
    )
    assert result.switched is True
    context["event_recorder"].published_events.clear()


@given("切换链已注入坏连接日志仓储（不可达端点 127.0.0.1:1，不设请求 session）")
def given_bad_log_repository(context: dict[str, Any]) -> None:
    """坏仓储组装（真实类 + 不可达 session_factory——仅环境参数坏，非 mock）.

    构造前提：本场景不设 ContextVar session（禁 set_session）——双模式 get_session
    优先，若设了测试 session 会命中好 session 永不触发 StorageError（僵尸场景）。
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from sqlalchemy.ext.asyncio import create_async_engine as _create_engine

    from src.application.services.isolation_management_service import IsolationManagementService
    from src.application.use_cases.agent_instantiation import InstantiateAgentUseCase
    from src.domain.entities.agent import AgentRole
    from src.domain.ports.resolver import resolve
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.storage.postgresql.repository.isolation_switch_log_repository import (
        PostgreSQLIsolationSwitchLogRepository,
    )
    from src.infrastructure.storage.postgresql.session_context import reset_session
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository
    from src.infrastructure.storage.redis.redis_isolation_repository import RedisIsolationRepository

    loop: asyncio.AbstractEventLoop = context["_loop"]
    redis_client = context["_redis_client"]
    # 硬前提复核：本场景不得存在 ContextVar session（前序场景泄漏则走僵尸 session 路径）
    pg = context.get("_pg")
    if pg is not None:
        reset_session(pg["token"])
        context["_pg"] = None  # 标记：本场景不走请求路径清理（session 已复位）

    # 凭据从测试配置动态拼接（零字面量——secret 扫描命中面；仅端点坏 127.0.0.1:1）
    from tests.environments import get_test_env

    env_pg = get_test_env().postgres
    bad_url = (
        f"postgresql+asyncpg://{env_pg.username}:{env_pg.password}"
        f"@{_BAD_ENDPOINT_FACTORY_HOST}:{_BAD_ENDPOINT_FACTORY_PORT}/{env_pg.database}"
    )
    bad_engine = _create_engine(
        bad_url,
        pool_pre_ping=False,
        connect_args={"timeout": 2, "command_timeout": 2},
    )
    bad_factory = async_sessionmaker(bind=bad_engine, class_=AsyncSession, expire_on_commit=False)
    bad_log_repo = PostgreSQLIsolationSwitchLogRepository(session_factory=bad_factory)
    context["_bad_engine"] = bad_engine

    agent_repository = RedisAgentRepository(adapter=RedisAdapter(redis_client=redis_client))
    isolation_repository = RedisIsolationRepository(adapter=RedisAdapter(redis_client=redis_client))
    recorder = _RecordingEventPublisher()
    isolation_service = IsolationManagementService(
        isolation_repository=isolation_repository,
        agent_repository=agent_repository,
        event_publisher=recorder,
        agent_config_loader=resolve("agent_config_loader"),
        isolation_switch_log_repository=bad_log_repo,
        audit_service=None,  # 坏仓储场景不涉 audit 联动（save 先失败）
    )
    use_case = InstantiateAgentUseCase(
        config_loader=resolve("agent_config_loader"),
        repository=agent_repository,
        event_publisher=InMemoryEventBus(),
        isolation_service=isolation_service,
    )
    result = _run_async(loop, use_case.execute(role=AgentRole.CEO))
    context["_agent_ids"].append(result.agent_id)
    context["agent_id"] = result.agent_id
    context["isolation_service"] = isolation_service
    context["event_recorder"] = recorder
    context["log_repository"] = bad_log_repo


@when(parsers.parse('请求切换隔离等级到 "{level}" 原因 "{reason}" 审批链 "{chain}"'))
def when_switch_with_chain(context: dict[str, Any], level: str, reason: str, chain: str) -> None:
    """真实切换（审批链非空——完整六字段记录面）."""
    from src.domain.events.enums import IsolationLevel

    result = _run_async(
        context["_loop"],
        context["isolation_service"].switch_isolation_level(context["agent_id"], IsolationLevel(level), reason, (chain,)),
    )
    context["switch_result"] = result


@when(parsers.parse('请求切换隔离等级到 "{level}" 原因 "{reason}"'))
@when(parsers.parse('再次请求切换隔离等级到 "{level}" 原因 "{reason}"'))
def when_switch_no_chain(context: dict[str, Any], level: str, reason: str) -> None:
    """真实切换（空审批链——MVP 用户请求通道的真实事实记录）."""
    from src.domain.events.enums import IsolationLevel

    try:
        result = _run_async(
            context["_loop"],
            context["isolation_service"].switch_isolation_level(context["agent_id"], IsolationLevel(level), reason, ()),
        )
        context["switch_result"] = result
    except Exception as exc:  # 异常捕获存 context（BDD 三段式断言形态）
        context["caught"] = exc


@then("切换结果 switched 为 True")
def then_switched_true(context: dict[str, Any]) -> None:
    """切换成功断言."""
    assert context["switch_result"].switched is True


@then("PG 检索取回日志六字段逐项一致（含 approval_chain JSONB roundtrip）")
def then_pg_log_six_fields(context: dict[str, Any]) -> None:
    """检索面取回断言（六字段逐项 + JSONB 审批链 roundtrip）."""
    from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogQuery

    result = _run_async(
        context["_loop"],
        context["log_repository"].search(IsolationSwitchLogQuery(agent_id=context["agent_id"])),
    )
    assert result.total == 1, f"期望 1 条日志，实际 {result.total}"
    log = result.items[0]
    event = context["switch_result"].event
    assert log.agent_id == event.agent_id
    assert log.previous_level == event.previous_level
    assert log.target_level == event.target_level
    assert log.trigger_reason == event.trigger_reason
    assert list(log.approval_chain) == ["合规负责人"]
    assert log.switch_timestamp == event.switch_timestamp
    assert log.worm_ref is None


@then("切换结果 switched 为 False")
def then_switched_false(context: dict[str, Any]) -> None:
    """no-op 断言（同等级幂等）."""
    assert context["switch_result"].switched is False


@then("检索该 Agent 日志 total 保持不变")
def then_search_total_unchanged(context: dict[str, Any]) -> None:
    """no-op 零日志（前置切换恰 1 条 → no-op 后仍恰 1 条）."""
    from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogQuery

    result = _run_async(
        context["_loop"],
        context["log_repository"].search(IsolationSwitchLogQuery(agent_id=context["agent_id"])),
    )
    assert result.total == 1, f"no-op 后 total 应保持 1，实际 {result.total}"


@then("抛出 StorageError 103")
def then_storage_error_103(context: dict[str, Any]) -> None:
    """fail-closed 断言（日志写失败 → 切换被拒——无审计痕迹的切换不允许发生）."""
    from src.domain.exceptions import StorageError

    exc = context.get("caught")
    assert isinstance(exc, StorageError), f"期望 StorageError，实际 {type(exc).__name__}"
    assert exc.code == "EXCEPTION_103"


@then("Redis 隔离等级未变（仍为 L4）")
def then_redis_level_unchanged(context: dict[str, Any]) -> None:
    """状态未变断言（audit-first——日志先于 Redis 写，日志失败零状态写）."""
    from src.domain.events.enums import IsolationLevel

    state = _run_async(context["_loop"], context["isolation_service"].get_isolation_state(context["agent_id"]))
    assert state.current_level is IsolationLevel.L4_HARD


@then("零事件发布")
def then_zero_events(context: dict[str, Any]) -> None:
    """零事件断言（_RecordingEventPublisher 恰零次）."""
    assert context["event_recorder"].published_events == []


@given("真实切换链已手动组装（含真实 audit_service）")
def given_real_chain_with_audit(context: dict[str, Any]) -> None:
    """链已在 _instantiate_agent 内组装（真实 AuditServiceImpl——PG 同事务联动）."""
    assert context.get("isolation_service") is not None


@then("audit_log 表含 isolation:switch 记录一条且 correlation_id 匹配事件")
def then_audit_log_record(context: dict[str, Any]) -> None:
    """测试 session 直查 audit_log 表（action_type + correlation_id 双过滤 SQL）."""
    from sqlalchemy import text

    event = context["switch_result"].event
    pg = _ensure_pg_session(context)
    rows = _run_async(
        context["_loop"],
        pg["session"].execute(
            text("SELECT actor, action_type, old_value, new_value FROM audit_log WHERE action_type = :action"),
            {"action": "isolation:switch"},
        ),
    ).fetchall()
    assert len(rows) >= 1, "audit_log 表缺 isolation:switch 记录"
    # correlation_id 匹配事件（AuditSearchCriteria 无 correlation_id 字段——直查表
    # 按事件 event_id 过滤，比客户端 items 匹配更直接）
    corr_rows = _run_async(
        context["_loop"],
        pg["session"].execute(
            text("SELECT COUNT(*) FROM audit_log WHERE correlation_id = :cid"),
            {"cid": str(event.event_id)},
        ),
    ).scalar()
    assert corr_rows == 1, f"correlation_id={event.event_id} 应恰命中 1 条 audit_log 行"
    context["audit_rows"] = rows


@then("old_value 与 new_value 形态正确（level 为 .value 字符串）")
def then_audit_value_shapes(context: dict[str, Any]) -> None:
    """联动载荷断言（old/new_value 的 level 为字符串——JSONB 序列化安全形态）."""
    rows = context["audit_rows"]
    row = rows[-1]
    old_value, new_value = row[2], row[3]
    assert old_value == {"level": "L4"}
    assert new_value["level"] == "L3"
    assert new_value["reason"] == "联动审计验证"
    assert isinstance(new_value.get("approval_chain"), list)


# =============================================================================
# AC-3: 多维检索（服务级——真实 PG）
# =============================================================================


@scenario(
    "test_acceptance_isolation_switch_log.feature",
    "AC-3.1 - 按 AGENT 检索",
)
def test_ac_3_1_search_by_agent(context: dict[str, Any]) -> None:
    """AC-3.1: agent_id 维度精确过滤 + 检索无 443 守卫."""


@scenario(
    "test_acceptance_isolation_switch_log.feature",
    "AC-3.2 - 时间范围与隔离等级组合检索（level 双向命中）",
)
def test_ac_3_2_search_time_level_combined(context: dict[str, Any]) -> None:
    """AC-3.2: 闭区间时间过滤 + level 双向命中（or_ 语义）+ AND 组合."""


@scenario(
    "test_acceptance_isolation_switch_log.feature",
    "AC-3.3 - 分页与排序",
)
def test_ac_3_3_pagination_and_ordering(context: dict[str, Any]) -> None:
    """AC-3.3: offset/limit 分页 + total 独立计数 + timestamp 降序."""


@given("多 Agent 切换日志已造数（3 Agent × 2 条，覆盖 L4→L3 与 L4→L2）")
def given_multi_agent_seed_data(context: dict[str, Any]) -> None:
    """统一造数：3 Agent × 2 条（每 Agent 一条 L4→L3 + 一条 L4→L2）.

    时间戳沿基准时刻递增（每条 +1 分钟）——时间范围检索维度可控。
    """
    from datetime import UTC, datetime, timedelta

    from src.domain.events.enums import IsolationLevel

    base = datetime(2026, 10, 25, 12, 0, 0, tzinfo=UTC)
    agent_ids = [uuid.uuid4() for _ in range(3)]
    logs = []
    for i, agent_id in enumerate(agent_ids):
        for j, target in enumerate((IsolationLevel.L3_SOFT, IsolationLevel.L2_COLLAB)):
            logs.append(
                _make_log_from_levels(
                    agent_id,
                    IsolationLevel.L4_HARD,
                    target,
                    f"造数-{i}-{j}",
                    base + timedelta(minutes=i * 10 + j),
                )
            )
    from src.infrastructure.storage.postgresql.repository.isolation_switch_log_repository import (
        PostgreSQLIsolationSwitchLogRepository,
    )

    _ensure_pg_session(context)
    repo = PostgreSQLIsolationSwitchLogRepository()
    for log in logs:
        _run_async(context["_loop"], repo.save(log))
    context["seed_agent_ids"] = agent_ids
    context["seed_base_time"] = base
    context["log_repository"] = repo


@given("单 Agent 五条切换日志已造数（独立分页造数）")
def given_single_agent_five_logs(context: dict[str, Any]) -> None:
    """独立分页造数（单 Agent 5 条——不共用 AC-3 Given 统一造数，total 断言基线 5）."""
    from datetime import UTC, datetime, timedelta

    from src.domain.events.enums import IsolationLevel
    from src.infrastructure.storage.postgresql.repository.isolation_switch_log_repository import (
        PostgreSQLIsolationSwitchLogRepository,
    )

    agent_id = uuid.uuid4()
    base = datetime(2026, 10, 25, 14, 0, 0, tzinfo=UTC)
    _ensure_pg_session(context)
    repo = PostgreSQLIsolationSwitchLogRepository()
    levels = (IsolationLevel.L3_SOFT, IsolationLevel.L2_COLLAB) * 3  # 六取五
    for j in range(5):
        log = _make_log_from_levels(
            agent_id,
            IsolationLevel.L4_HARD,
            levels[j],
            f"分页-{j}",
            base + timedelta(minutes=j),
        )
        _run_async(context["_loop"], repo.save(log))
    context["pagination_agent_id"] = agent_id
    context["log_repository"] = repo


@when("以 agent_id 维度检索切换日志")
def when_search_by_agent(context: dict[str, Any]) -> None:
    """按 AGENT 检索."""
    from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogQuery

    target = context["seed_agent_ids"][1]
    context["search_result"] = _run_async(
        context["_loop"],
        context["log_repository"].search(IsolationSwitchLogQuery(agent_id=target)),
    )
    context["search_agent_id"] = target


@then("仅返回该 Agent 的日志且 total 等于该 Agent 条数")
def then_only_target_agent(context: dict[str, Any]) -> None:
    """精确过滤断言（6 条总量中命中该 Agent 的 2 条）."""
    result = context["search_result"]
    assert result.total == 2, f"期望 total=2，实际 {result.total}"
    assert len(result.items) == 2
    for log in result.items:
        assert log.agent_id == context["search_agent_id"]


@then("检索不要求 Agent 现存（无 443 守卫）")
def then_no_agent_guard(context: dict[str, Any]) -> None:
    """审计检索语义（Agent TTL 过期后历史日志仍可查——与写入面守卫对照）."""
    from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogQuery

    random_agent = uuid.uuid4()  # 从未实例化的 Agent
    result = _run_async(
        context["_loop"],
        context["log_repository"].search(IsolationSwitchLogQuery(agent_id=random_agent)),
    )
    assert result.total == 0  # 空结果非异常（无 443——检索面零守卫）


@when(parsers.parse('以时间范围与隔离等级 "{level}" 组合检索'))
def when_search_time_level(context: dict[str, Any], level: str) -> None:
    """组合检索（三条件 AND：agent_id + 时间范围 + level 双向命中）."""
    from datetime import timedelta

    from src.domain.events.enums import IsolationLevel
    from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogQuery

    base = context["seed_base_time"]
    context["search_result"] = _run_async(
        context["_loop"],
        context["log_repository"].search(
            IsolationSwitchLogQuery(
                agent_id=context["seed_agent_ids"][0],
                start_time=base - timedelta(minutes=1),
                end_time=base + timedelta(minutes=30),
                level=IsolationLevel(level),
            )
        ),
    )


@then("命中日志满足 previous_level 或 target_level 任一为 L3")
def then_level_bidirectional_l3(context: dict[str, Any]) -> None:
    """or_ 命中语义（target 命中——L4→L3 的 target_level=L3）."""
    from src.domain.events.enums import IsolationLevel

    result = context["search_result"]
    assert result.total >= 1
    for log in result.items:
        assert IsolationLevel.L3_SOFT in (log.previous_level, log.target_level)


@then(parsers.parse('L4→L3 切换在 level "{level}" 检索亦返回（previous 命中）'))
def then_level_previous_hit(context: dict[str, Any], level: str) -> None:
    """previous 命中（L4→L3 的 previous_level=L4——or_ 两臂皆可命中）."""
    from datetime import timedelta

    from src.domain.events.enums import IsolationLevel
    from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogQuery

    base = context["seed_base_time"]
    result = _run_async(
        context["_loop"],
        context["log_repository"].search(
            IsolationSwitchLogQuery(
                agent_id=context["seed_agent_ids"][0],
                start_time=base - timedelta(minutes=1),
                end_time=base + timedelta(minutes=30),
                level=IsolationLevel(level),
            )
        ),
    )
    assert result.total >= 1, "level=L4 检索应命中 L4→L3 切换（previous 臂）"


@then("组合条件为 AND 语义")
def then_combined_and_semantics(context: dict[str, Any]) -> None:
    """AND 组合（时间范围外或等级不涉的行不返回——agent0 仅 2 条且均涉 L3? 否）.

    agent0 造数：L4→L3（涉 L3 与 L4）+ L4→L2（涉 L4 与 L2）——level=L3 组合
    仅命中第 1 条（第 2 条不涉 L3）。
    """
    result = context["search_result"]
    assert result.total == 1, f"AND 组合应仅命中 1 条（L4→L3），实际 {result.total}"


@when(parsers.parse("以 limit {limit:d} offset {offset:d} 检索"))
def when_search_paginated(context: dict[str, Any], limit: int, offset: int) -> None:
    """分页检索."""
    from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogQuery

    context["search_result"] = _run_async(
        context["_loop"],
        context["log_repository"].search(
            IsolationSwitchLogQuery(agent_id=context["pagination_agent_id"], limit=limit, offset=offset)
        ),
    )


@when(parsers.parse("以 offset {offset:d} 检索"))
@when(parsers.parse("以 offset {offset:d} 检索（空页边界）"))
def when_search_offset_only(context: dict[str, Any], offset: int) -> None:
    """offset 单独检索（limit 默认 50——尾页/空页边界形态）."""
    from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogQuery

    context["search_result"] = _run_async(
        context["_loop"],
        context["log_repository"].search(IsolationSwitchLogQuery(agent_id=context["pagination_agent_id"], offset=offset)),
    )


@then(parsers.parse("返回 {count:d} 条且 total 为 {total:d}"))
def then_items_and_total(context: dict[str, Any], count: int, total: int) -> None:
    """分页断言（items 长度 + total 独立计数——非 items 长度）."""
    result = context["search_result"]
    assert len(result.items) == count, f"期望 items {count} 条，实际 {len(result.items)}"
    assert result.total == total, f"期望 total={total}，实际 {result.total}"


@then(parsers.parse("返回 {count:d} 条"))
def then_items_count(context: dict[str, Any], count: int) -> None:
    """items 长度断言（offset=4 → 1 条）."""
    result = context["search_result"]
    assert len(result.items) == count


@then("排序为 switch_timestamp 降序（最新在前）")
def then_ordering_desc(context: dict[str, Any]) -> None:
    """降序断言（最新 switch_timestamp 在 items[0]）."""
    items = context["search_result"].items
    timestamps = [log.switch_timestamp for log in items]
    assert timestamps == sorted(timestamps, reverse=True), "switch_timestamp 应降序排列"


# =============================================================================
# AC-4: 持久化与不可篡改（服务级——真实 PG）
# =============================================================================


@scenario(
    "test_acceptance_isolation_switch_log.feature",
    "AC-4.1 - RLS 篡改拒绝",
)
def test_ac_4_1_rls_tamper_rejected(context: dict[str, Any]) -> None:
    """AC-4.1: deny UPDATE/DELETE 0 行（绕过环境动态 skip——superuser 恒 skip 属预期）."""


@scenario(
    "test_acceptance_isolation_switch_log.feature",
    "AC-4.2 - worm_ref 预留与表结构与 CheckConstraint 拒绝",
)
def test_ac_4_2_worm_ref_and_schema(context: dict[str, Any]) -> None:
    """AC-4.2: ORM 列集/索引五/worm_ref roundtrip None + CheckConstraint IntegrityError
    （CheckConstraint 实证不依赖 RLS 探测——superuser 环境下仍真实可达）。"""


@given("真实切换日志已落库一条")
def given_one_log_persisted(context: dict[str, Any]) -> None:
    """直构落库一条（RLS/CheckConstraint 实证载体）."""
    from datetime import UTC, datetime

    from src.domain.events.enums import IsolationLevel
    from src.infrastructure.storage.postgresql.repository.isolation_switch_log_repository import (
        PostgreSQLIsolationSwitchLogRepository,
    )

    _ensure_pg_session(context)
    repo = PostgreSQLIsolationSwitchLogRepository()
    agent_id = uuid.uuid4()
    log = _make_log_from_levels(
        agent_id,
        IsolationLevel.L4_HARD,
        IsolationLevel.L3_SOFT,
        "防篡改实证",
        datetime.now(UTC),
        ("审批人",),
    )
    _run_async(context["_loop"], repo.save(log))
    context["tamper_agent_id"] = agent_id
    context["tamper_log_id"] = log.log_id
    context["log_repository"] = repo


@given("已建立非绕过连接形态（非绕过直连或 superuser 临时降权 SET ROLE）")
def given_non_bypass_role(context: dict[str, Any]) -> None:
    """RLS 非绕过形态保障（任一环境真实实证——不依赖非 superuser 应用角色预置）.

    三分支:
    - 非绕过直连（非 superuser/非 bypassrls/非 owner）→ 直接走断言；
    - superuser（本地/CI 默认 postgres）→ 事务内 CREATE ROLE 临时降权角色 +
      GRANT + SET ROLE（PG 的 CREATE ROLE/GRANT 是事务性的——teardown rollback
      随测试事务自动回收，零残留；SET ROLE 后 current_user 非 owner 非
      superuser → FORCE RLS 真实生效，UPDATE/DELETE 断言 0 行）；
    - 非 superuser 且有 bypassrls/owner 属性（无 CREATE ROLE 权限且无法自建
      降权角色）→ 动态 skip（唯一残余 skip 面——理论环境，常规部署不出现）。

    owner 子查询限定 public schema：全量运行时其他测试的隔离 schema（真实服务
    Schema 隔离模式）中也存在同名表——不限定的子查询返回多行触发
    CardinalityViolationError（多 schema 干扰面，2026-10-25 全量复现定谳）。
    """
    from sqlalchemy import text

    pg = _ensure_pg_session(context)
    probe = _run_async(
        context["_loop"],
        pg["session"].execute(
            text(
                "SELECT (SELECT rolsuper OR rolbypassrls FROM pg_roles "
                "WHERE rolname = current_user) AS bypass, "
                "(SELECT rolsuper FROM pg_roles WHERE rolname = current_user) AS is_super, "
                "(SELECT pg_roles.rolname = current_user FROM pg_class "
                "JOIN pg_roles ON pg_roles.oid = pg_class.relowner "
                "WHERE pg_class.relname = 'isolation_switch_logs' "
                "AND pg_class.relnamespace = 'public'::regnamespace) AS is_owner"
            )
        ),
    ).fetchone()
    bypass, is_super, is_owner = probe[0], probe[1], probe[2]
    if not (bypass or is_owner):
        return  # 分支①: 非绕过直连——直接走断言
    if not is_super:
        pytest.skip(  # 分支③: 非 superuser 的 bypassrls/owner 绕过（无 CREATE ROLE 权限）
            "RLS deny 断言需非绕过连接（当前角色 bypassrls/owner 属性绕过 RLS 且非 "
            "superuser 无 CREATE ROLE 权限无法临时降权——需预置非绕过应用角色）"
        )
    # 分支②: superuser 临时降权（SET ROLE 后同 session 连接的 UPDATE/DELETE 受
    # FORCE RLS 约束——真实断言；角色经测试事务 rollback 自动回收）
    probe_role = f"rls_probe_{uuid.uuid4().hex[:8]}"
    probe_password = uuid.uuid4().hex
    _run_async(
        context["_loop"],
        pg["session"].execute(text(f"CREATE ROLE \"{probe_role}\" LOGIN PASSWORD '{probe_password}'")),
    )
    _run_async(
        context["_loop"],
        pg["session"].execute(text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON isolation_switch_logs TO "{probe_role}"')),
    )
    _run_async(
        context["_loop"],
        pg["session"].execute(text(f'SET ROLE "{probe_role}"')),
    )
    context["_rls_probe_role"] = probe_role


@when("尝试 UPDATE 修改日志行 target_level")
def when_try_update_log(context: dict[str, Any]) -> None:
    """篡改尝试（UPDATE target_level）."""
    from sqlalchemy import text

    pg = _ensure_pg_session(context)
    context["update_rowcount"] = _run_async(
        context["_loop"],
        pg["session"].execute(
            text("UPDATE isolation_switch_logs SET target_level = 'L2' WHERE log_id = :lid"),
            {"lid": str(context["tamper_log_id"])},
        ),
    ).rowcount


@then("影响 0 行（deny UPDATE）")
def then_update_zero_rows(context: dict[str, Any]) -> None:
    """deny UPDATE 断言（FORCE RLS 下 0 行受影响）."""
    assert context["update_rowcount"] == 0, "UPDATE 应被 RLS deny（0 行受影响）"


@when("尝试 DELETE 删除日志行")
def when_try_delete_log(context: dict[str, Any]) -> None:
    """篡改尝试（DELETE）."""
    from sqlalchemy import text

    pg = _ensure_pg_session(context)
    context["delete_rowcount"] = _run_async(
        context["_loop"],
        pg["session"].execute(
            text("DELETE FROM isolation_switch_logs WHERE log_id = :lid"),
            {"lid": str(context["tamper_log_id"])},
        ),
    ).rowcount


@then("影响 0 行（deny DELETE）")
def then_delete_zero_rows(context: dict[str, Any]) -> None:
    """deny DELETE 断言."""
    assert context["delete_rowcount"] == 0, "DELETE 应被 RLS deny（0 行受影响）"


@when("直插 previous_level 等于 target_level 行")
def when_try_insert_noop_row(context: dict[str, Any]) -> None:
    """CheckConstraint 实证（previous==target 直插）."""
    from sqlalchemy import text

    pg = _ensure_pg_session(context)
    try:
        _run_async(
            context["_loop"],
            pg["session"].execute(
                text(
                    "INSERT INTO isolation_switch_logs "
                    "(log_id, agent_id, previous_level, target_level, trigger_reason, "
                    "approval_chain, switch_timestamp) "
                    "VALUES (:lid, :aid, 'L3', 'L3', 'no-op 直插', '[]'::jsonb, NOW())"
                ),
                {"lid": str(uuid.uuid4()), "aid": str(uuid.uuid4())},
            ),
        )
        context["constraint_violation"] = None
    except Exception as exc:  # IntegrityError 捕获存 context
        context["constraint_violation"] = exc
        _run_async(context["_loop"], pg["session"].rollback())


@then("抛出 IntegrityError（CheckConstraint 拒绝 no-op 日志）")
def then_integrity_error(context: dict[str, Any]) -> None:
    """CheckConstraint 断言（DB 层拒绝——实体不变量的 DB 投影）."""
    exc = context.get("constraint_violation")
    assert exc is not None, "no-op 直插应触发 IntegrityError（CheckConstraint）"
    assert "check" in str(exc).lower() or "integrity" in type(exc).__name__.lower()


@when("检查 ORM 模型与表结构")
def when_inspect_orm_schema(context: dict[str, Any]) -> None:
    """ORM 模型内省（__table_args__ 与列集）."""
    from src.infrastructure.storage.postgresql.models.isolation_switch_log import (
        IsolationSwitchLogModel,
    )

    context["orm_model"] = IsolationSwitchLogModel


@then("列集完整（含 worm_ref nullable 与 created_at server_default）")
def then_columns_complete(context: dict[str, Any]) -> None:
    """列集断言（九列——八字段实体 + created_at 行创建审计列）."""
    model = context["orm_model"]
    columns = {c.name for c in model.__table__.columns}
    expected = {
        "log_id",
        "agent_id",
        "previous_level",
        "target_level",
        "trigger_reason",
        "approval_chain",
        "switch_timestamp",
        "worm_ref",
        "created_at",
    }
    assert columns == expected, f"列集不符: {columns ^ expected}"
    worm_col = model.__table__.columns["worm_ref"]
    assert worm_col.nullable is True
    created_col = model.__table__.columns["created_at"]
    assert created_col.server_default is not None


@then("索引五项齐备（agent_id/switch_timestamp/previous_level/target_level/组合索引）")
def then_five_indexes(context: dict[str, Any]) -> None:
    """索引五断言（level 双向命中 or_ 两臂皆索引化——BitmapOr 结构性前提）."""
    model = context["orm_model"]
    index_cols = {tuple(c.name for c in idx.columns) for idx in model.__table__.indexes}
    assert ("agent_id",) in index_cols
    assert ("switch_timestamp",) in index_cols
    assert ("previous_level",) in index_cols
    assert ("target_level",) in index_cols
    assert ("agent_id", "switch_timestamp") in index_cols


@then("worm_ref 检索 roundtrip 保持 None")
def then_worm_ref_roundtrip(context: dict[str, Any]) -> None:
    """OD-1 登记面断言（nullable 预留——检索投影 None 保持）."""
    from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogQuery

    result = _run_async(
        context["_loop"],
        context["log_repository"].search(IsolationSwitchLogQuery(agent_id=context["tamper_agent_id"])),
    )
    assert result.total == 1
    assert result.items[0].worm_ref is None


# =============================================================================
# AC-5: 性能与存储成功率（委托集成计时——Redis+PG）
# =============================================================================


@scenario(
    "test_acceptance_isolation_switch_log.feature",
    "AC-5.1 - 日志记录延迟 P95 小于 50ms",
)
def test_ac_5_1_write_p95(context: dict[str, Any]) -> None:
    """AC-5.1: 切换全链 P95<50ms（委托集成 _PERF_CACHE——禁 20 采样双跑）."""


@scenario(
    "test_acceptance_isolation_switch_log.feature",
    "AC-5.2 - 检索响应 P95 小于 500ms 与存储成功率 100%",
)
def test_ac_5_2_search_p95_and_success(context: dict[str, Any]) -> None:
    """AC-5.2: 检索 P95<500ms + 连续 20 次真实切换 20/20 落日志."""


@when("执行切换全链计时采样（委托集成缓存——禁 20 采样双跑）")
def when_write_perf_sampling(context: dict[str, Any]) -> None:
    """委托集成 helper（单槽缓存 + xdist_group 同 worker 命中）."""
    from tests.integration.test_integration_isolation_switch_log import sample_write_perf

    context["write_perf"] = _run_async(context["_loop"], sample_write_perf(context["_redis_client"]))


@then("P95 延迟小于 50ms")
def then_write_p95_below_50ms(context: dict[str, Any]) -> None:
    """写 P95 断言（常量单源——集成模块定义/验收 import）."""
    from tests.integration.test_integration_isolation_switch_log import (
        SWITCH_LOG_WRITE_P95_LIMIT_SECONDS,
    )

    p95 = context["write_perf"]["p95_seconds"]
    assert p95 < SWITCH_LOG_WRITE_P95_LIMIT_SECONDS, f"写 P95={p95}s 超限 {SWITCH_LOG_WRITE_P95_LIMIT_SECONDS}s"


@when("执行检索计时采样（委托集成缓存）与连续 20 次真实切换")
def when_search_perf_and_success(context: dict[str, Any]) -> None:
    """检索委托 + 20 次真实切换（成功率分子分母采样）."""
    from tests.integration.test_integration_isolation_switch_log import sample_search_perf

    context["search_perf"] = _run_async(context["_loop"], sample_search_perf(context["_redis_client"]))
    # 20 次真实切换（真实链——success_rate 同批采样委托集成缓存）
    from tests.integration.test_integration_isolation_switch_log import sample_success_rate

    context["success_rate"] = _run_async(context["_loop"], sample_success_rate(context["_redis_client"]))


@then("检索 P95 延迟小于 500ms")
def then_search_p95_below_500ms(context: dict[str, Any]) -> None:
    """检索 P95 断言."""
    from tests.integration.test_integration_isolation_switch_log import (
        SWITCH_LOG_SEARCH_P95_LIMIT_SECONDS,
    )

    p95 = context["search_perf"]["p95_seconds"]
    assert p95 < SWITCH_LOG_SEARCH_P95_LIMIT_SECONDS, f"检索 P95={p95}s 超限"


@then("20 次切换产生 20 条日志（20/20 分子分母）")
def then_success_rate_20_of_20(context: dict[str, Any]) -> None:
    """存储成功率断言（分子分母显式——含审批链非空场景混合）."""
    rate = context["success_rate"]
    assert rate["total_count"] == 20
    assert rate["success_count"] == 20, f"存储成功率 {rate['success_count']}/{rate['total_count']}——期望 20/20"


# =============================================================================
# AC-6: 端口接线、CLI、架构合规与回归
# =============================================================================


@scenario(
    "test_acceptance_isolation_switch_log.feature",
    "AC-6.1 - 组合根接线与端口注册",
)
def test_ac_6_1_composition_root_wiring(context: dict[str, Any]) -> None:
    """AC-6.1: resolve 可达 + PortSpec 元数据 + 接线内省锚（禁发真实命令）."""


@scenario(
    "test_acceptance_isolation_switch_log.feature",
    "AC-6.2 - CLI isolation-logs 真实链检索",
)
def test_ac_6_2_cli_isolation_logs(context: dict[str, Any]) -> None:
    """AC-6.2: CLI fallback 全链（生产真实形态——bootstrap→resolve→检索→输出）."""


@scenario(
    "test_acceptance_isolation_switch_log.feature",
    "AC-6.3 - 架构合规静态扫描",
)
def test_ac_6_3_architecture_compliance(context: dict[str, Any]) -> None:
    """AC-6.3: domain 零外部依赖 + 组合根外零实例化 + 端口方向."""


@scenario(
    "test_acceptance_isolation_switch_log.feature",
    "AC-6.4 - 回归面资产在位",
)
def test_ac_6_4_regression_assets(context: dict[str, Any]) -> None:
    """AC-6.4: 5-4/5-5 存量文件在位 + 枚举注册 + 事件双登记不漂移."""


@given("组合根已引导装配")
def given_bootstrap_done(context: dict[str, Any]) -> None:
    """装配确认（session 级 autouse conftest 已 bootstrap——二次调用会因
    lambda 工厂对象不同触发 ConflictError，此处仅确认可达 + 清缓存）."""
    from src.domain.ports.registry import _global_registry
    from src.domain.ports.resolver import get_resolver

    assert _global_registry.get("isolation_switch_log_repository") is not None
    get_resolver().clear_scoped()  # 清请求作用域缓存（接线断言拿新实例）


@then("isolation_switch_log_repository 端口 resolve 可达且 PortSpec 元数据完整（SINGLETON）")
def then_port_registered_singleton(context: dict[str, Any]) -> None:
    """注册断言（5-4 AC-6.1 同款——resolve + isinstance + lifetime）."""
    from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogRepository
    from src.domain.ports.registry import Lifetime, _global_registry
    from src.domain.ports.resolver import resolve

    spec = _global_registry.get("isolation_switch_log_repository")
    assert spec is not None, "isolation_switch_log_repository 未注册"
    assert spec.lifetime == Lifetime.SINGLETON
    assert spec.owner == "platform"
    assert spec.tags == ("agent", "isolation", "audit")
    instance = resolve("isolation_switch_log_repository")
    assert isinstance(instance, IsolationSwitchLogRepository)


@then("isolation_management_service 实例第五依赖为日志仓储端口实例（接线内省——禁发真实命令）")
def then_fifth_dependency_introspection(context: dict[str, Any]) -> None:
    """接线内省锚（lambda 漏注入即红——服务实例属性 isinstance 检查）."""
    from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogRepository
    from src.domain.ports.resolver import resolve

    service = resolve("isolation_management_service")
    fifth = getattr(service, "_isolation_switch_log_repository", None)
    assert isinstance(fifth, IsolationSwitchLogRepository), "第五依赖漏注入（lambda 扩展缺失）"


@then("第六依赖 audit_service 可选注入可达")
def then_sixth_dependency_optional(context: dict[str, Any]) -> None:
    """可选注入断言（resolve_optional 可达——非 None 即真实 audit_service）."""
    from src.domain.ports.audit_service import AuditServicePort
    from src.domain.ports.resolver import get_resolver

    sixth = get_resolver().resolve_optional("audit_service")
    if sixth is not None:
        assert isinstance(sixth, AuditServicePort)
    context["introspected_audit"] = sixth is not None


@given("切换日志已直构落库一条（fallback 独立会话 commit——生产 CLI 真实形态）")
def given_cli_seed_log(context: dict[str, Any]) -> None:
    """CLI 造数（独立会话 commit——跨循环实验定谳形态，见模块 docstring 实施注记）."""
    from datetime import UTC, datetime

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.infrastructure.config.postgresql import PostgreSQLConfig
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
    from src.infrastructure.storage.postgresql.repository.isolation_switch_log_repository import (
        PostgreSQLIsolationSwitchLogRepository,
    )
    from src.infrastructure.storage.postgresql.session_context import reset_session
    from tests.environments import get_test_env

    # 前提复核：CLI 场景不共享请求 session（fresh fallback 全链）
    pg = context.get("_pg")
    if pg is not None:
        reset_session(pg["token"])
        context["_pg"] = None

    env = get_test_env().postgres
    pg_config = PostgreSQLConfig(
        host=env.host, port=env.port, database=env.database, username=env.username, password=env.password
    )
    manager = PostgreSQLManager(pg_config)
    factory = __import__("sqlalchemy.ext.asyncio", fromlist=["async_sessionmaker"]).async_sessionmaker(
        bind=manager.get_async_engine(), class_=AsyncSession, expire_on_commit=False
    )
    repo = PostgreSQLIsolationSwitchLogRepository(session_factory=factory)
    from src.domain.events.enums import IsolationLevel

    agent_id = uuid.uuid4()
    log = _make_log_from_levels(
        agent_id,
        IsolationLevel.L4_HARD,
        IsolationLevel.L3_SOFT,
        "CLI 检索验证原因",
        datetime.now(UTC),
        ("审批人",),
    )
    _run_async(context["_loop"], repo.save(log))  # fallback 独立会话 commit
    context["cli_agent_id"] = agent_id
    context["cli_log_id"] = log.log_id
    # superuser 探测（清理前提——非绕过环境本场景后续清理步骤 skip）
    probe_session = AsyncSession(manager.get_async_engine())
    row = _run_async(
        context["_loop"],
        probe_session.execute(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")),
    ).fetchone()
    _run_async(context["_loop"], probe_session.close())
    context["cli_superuser"] = bool(row[0]) if row else False


@when("进程内执行 isolation-logs 命令（CLI fallback 全链）")
def when_run_cli_isolation_logs(context: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    """in-process 调 main()（CLI 内部 bootstrap→resolve→fallback 检索→输出）."""
    from src.domain.ports.resolver import get_resolver
    from src.entrypoints import agent_cli

    get_resolver().clear_singleton()
    get_resolver().clear_scoped()
    context["cli_exit_code"] = agent_cli.main(
        [
            "isolation-logs",
            "--agent-id",
            str(context["cli_agent_id"]),
        ]
    )
    context["cli_stdout"] = capsys.readouterr().out


@then("退出码为 0 且 stdout 含等级与原因行")
def then_cli_exit_zero_with_output(context: dict[str, Any]) -> None:
    """CLI 输出断言（多行摘要——previous → target / trigger_reason）."""
    assert context["cli_exit_code"] == 0
    out = context["cli_stdout"]
    assert "L4" in out and "L3" in out, f"stdout 缺等级行: {out!r}"
    assert "CLI 检索验证原因" in out, f"stdout 缺原因: {out!r}"


@then("造数行清理零残留（superuser 连接 DELETE——非绕过环境跳过）")
def then_cli_seed_cleaned(context: dict[str, Any]) -> None:
    """造数行清理（superuser 绕过 RLS deny DELETE——非绕过环境本步骤 skip）."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.infrastructure.config.postgresql import PostgreSQLConfig
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
    from tests.environments import get_test_env

    if not context.get("cli_superuser", False):
        pytest.skip("CLI 造数清理需 superuser 连接（RLS deny DELETE 对普通角色不设防例外）")
    env = get_test_env().postgres
    manager = PostgreSQLManager(
        PostgreSQLConfig(
            host=env.host,
            port=env.port,
            database=env.database,
            username=env.username,
            password=env.password,
        )
    )
    session = AsyncSession(manager.get_async_engine())
    _run_async(
        context["_loop"],
        session.execute(
            text("DELETE FROM isolation_switch_logs WHERE log_id = :lid"),
            {"lid": str(context["cli_log_id"])},
        ),
    )
    _run_async(context["_loop"], session.commit())
    remain = _run_async(
        context["_loop"],
        session.execute(
            text("SELECT COUNT(*) FROM isolation_switch_logs WHERE log_id = :lid"),
            {"lid": str(context["cli_log_id"])},
        ),
    ).scalar()
    _run_async(context["_loop"], session.close())
    _run_async(context["_loop"], manager.get_async_engine().dispose())
    assert remain == 0, "CLI 造数行未清理"


@when("扫描 domain 实体与端口文件 import")
def when_scan_domain_imports(context: dict[str, Any]) -> None:
    """AST 扫描（白名单标准库+同层，黑名单 pydantic/sqlalchemy/redis 等）."""
    import ast

    targets = [
        SRC_DIR / "domain" / "entities" / "isolation_switch_log.py",
        SRC_DIR / "domain" / "ports" / "isolation_switch_log_repository.py",
    ]
    forbidden = {"pydantic", "sqlalchemy", "redis", "fastapi", "typer", "langgraph", "prefect"}
    violations: list[str] = []
    for path in targets:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [(node.module or "").split(".")[0]] if node.module else []
            else:
                continue
            for mod in modules:
                if mod in forbidden:
                    violations.append(f"{path.name}: {mod}")
    context["domain_import_violations"] = violations


@then("零外部依赖（仅标准库与同层 import）")
def then_zero_external_deps(context: dict[str, Any]) -> None:
    """domain 零外部依赖断言（import-linter 契约的测试级双保险）."""
    assert context["domain_import_violations"] == [], f"domain 文件存在外部依赖: {context['domain_import_violations']}"


@when("扫描组合根外 PostgreSQLIsolationSwitchLogRepository 实例化点")
def when_scan_instantiation_points(context: dict[str, Any]) -> None:
    """src/ 全扫描（组合根是唯一实例化点——验证器 B）."""
    import ast

    class_name = "PostgreSQLIsolationSwitchLogRepository"
    violations: list[str] = []
    for path in SRC_DIR.rglob("*.py"):
        if "composition_root" in path.name:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = getattr(func, "id", None) or getattr(func, "attr", None)
                if name == class_name:
                    violations.append(str(path.relative_to(REPO_ROOT)))
    context["instantiation_violations"] = violations


@then("仅组合根与测试文件出现")
def then_only_composition_root(context: dict[str, Any]) -> None:
    """组合根外零实例化断言."""
    assert context["instantiation_violations"] == [], f"组合根外存在实例化点: {context['instantiation_violations']}"


@then("CLI import 白名单合规（domain/application 合法，infrastructure 禁入）")
def then_cli_import_whitelist(context: dict[str, Any]) -> None:
    """端口方向断言（agent_cli 的 isolation-logs 面直消费仓储端口）."""
    import ast

    cli_path = SRC_DIR / "entrypoints" / "agent_cli.py"
    tree = ast.parse(cli_path.read_text(encoding="utf-8"))
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("src.infrastructure"):
                violations.append(node.module)
    assert violations == [], f"CLI 违规 import infrastructure: {violations}"


@then("5-4 与 5-5 验收及探针测试文件存在")
def then_regression_files_exist(context: dict[str, Any]) -> None:
    """回归面资产在位断言（Task 3 构造点同步的靶文件）."""
    tests_dir = REPO_ROOT / "tests"
    expected = [
        tests_dir / "acceptance" / "test_acceptance_agent_isolation.py",
        tests_dir / "acceptance" / "test_acceptance_agent_triple_isolation.py",
        tests_dir / "integration" / "test_integration_agent_isolation.py",
        tests_dir / "integration" / "test_integration_agent_triple_isolation.py",
        tests_dir / "integration" / "test_integration_isolation_security.py",
    ]
    for path in expected:
        assert path.exists(), f"回归面资产缺失: {path.relative_to(REPO_ROOT)}"


@then("AuditActionType.ISOLATION_SWITCH 枚举项已注册（值 isolation:switch）")
def then_audit_action_type_registered(context: dict[str, Any]) -> None:
    """枚举第 8 组断言（isolation 组——DC-9）."""
    from src.domain.events.audit_events import AuditActionType

    assert AuditActionType.ISOLATION_SWITCH.value == "isolation:switch"


@then("IsolationLevelSwitched 事件双登记不漂移（yaml 与 DEFAULT_MAPPINGS）")
def then_event_dual_registration(context: dict[str, Any]) -> None:
    """事件面零改动复验（5-4 验收锚沿用）."""
    import yaml

    from src.infrastructure.messaging.channel_router import ChannelRouter

    channels_path = REPO_ROOT / "configs" / "event_channels.yaml"
    data = yaml.safe_load(channels_path.read_text(encoding="utf-8"))
    yaml_text = str(data)
    assert "IsolationLevelSwitched" in yaml_text or "isolation_level_switched" in yaml_text
    # DEFAULT_MAPPINGS: dict[str, ChannelMapping]——event_type 字段即映射键
    assert "IsolationLevelSwitched" in ChannelRouter.DEFAULT_MAPPINGS


# =============================================================================
# 收尾: 交付完成清单（Task 6 追加——18 场景终态）
# =============================================================================


@scenario(
    "test_acceptance_isolation_switch_log.feature",
    "收尾 - 交付完成清单",
)
def test_final_delivery_checklist(context: dict[str, Any]) -> None:
    """收尾清单: src 八文件 + tests 四目录交付物在位（missing 断言——5-5 同款）。"""


@then("src 交付八文件全部在位（实体/端口/模型/迁移/仓储/服务/CLI/组合根）")
def then_src_eight_files_present(context: dict[str, Any]) -> None:
    """src 交付清单（实体/端口/ORM/迁移/仓储/服务/CLI/组合根）."""
    src_files = [
        SRC_DIR / "domain" / "entities" / "isolation_switch_log.py",
        SRC_DIR / "domain" / "ports" / "isolation_switch_log_repository.py",
        SRC_DIR / "infrastructure" / "storage" / "postgresql" / "models" / "isolation_switch_log.py",
        REPO_ROOT / "deploy" / "postgresql" / "alembic" / "versions" / "015_isolation_switch_logs.py",
        SRC_DIR / "infrastructure" / "storage" / "postgresql" / "repository" / "isolation_switch_log_repository.py",
        SRC_DIR / "application" / "services" / "isolation_management_service.py",
        SRC_DIR / "entrypoints" / "agent_cli.py",
        SRC_DIR / "composition_root.py",
    ]
    missing = [str(p.relative_to(REPO_ROOT)) for p in src_files if not p.exists()]
    assert not missing, f"src 交付文件缺失: {missing}"


@then("tests 四目录交付文件全部在位（unit/contracts/integration/acceptance）")
def then_tests_four_dirs_present(context: dict[str, Any]) -> None:
    """tests 交付清单（unit/contracts/integration/acceptance 四目录）."""
    tests_dir = REPO_ROOT / "tests"
    test_files = [
        tests_dir / "unit" / "domain" / "entities" / "test_isolation_switch_log.py",
        tests_dir / "unit" / "domain" / "ports" / "test_isolation_switch_log_repository_port.py",
        tests_dir / "unit" / "infrastructure" / "storage" / "postgresql" / "test_isolation_switch_log_repository.py",
        tests_dir / "unit" / "application" / "services" / "test_isolation_management_service.py",
        tests_dir / "unit" / "architecture" / "test_arch_isolation_switch_log.py",
        tests_dir / "contracts" / "test_port_contract_isolation_switch_log_repository.py",
        tests_dir / "integration" / "test_integration_isolation_switch_log.py",
        tests_dir / "acceptance" / "test_acceptance_isolation_switch_log.feature",
        tests_dir / "acceptance" / "test_acceptance_isolation_switch_log.py",
    ]
    missing = [str(p.relative_to(REPO_ROOT)) for p in test_files if not p.exists()]
    assert not missing, f"tests 交付文件缺失: {missing}"


# =============================================================================
# teardown 钩子：坏引擎清理（AC-2.3——context teardown 前关闭坏 engine 防 warning）
# =============================================================================


@pytest.fixture(autouse=True)
def _cleanup_bad_engine(context: dict[str, Any]) -> Generator[None, None, None]:
    """AC-2.3 坏 engine 场景级关闭（连接失败不产生连接——dispose 幂等安全）."""
    yield
    bad_engine = context.get("_bad_engine")
    if bad_engine is not None:
        try:
            _run_async(context["_loop"], bad_engine.dispose())
        except Exception:  # 清理兜底（坏引擎 dispose 异常不阻断场景结果）
            pass
