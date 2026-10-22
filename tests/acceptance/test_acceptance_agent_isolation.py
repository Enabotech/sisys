"""Story 5.4: EIP 弹性隔离协议基础 — 验收测试（BDD 步骤实现）

模板基准: test_acceptance_postgresql_relational_layer.py（PG 模板——
多行 @scenario 字面量路径 + 场景绑定与步骤实现交替排列 + AC 横幅分组）；
R6 改造（用户裁定 2026-10-22）: 组织结构对齐 PG 模板，保留真实断言
（禁 then-pass 占位——PG 模板历史缺陷）、AC 前缀场景名、Redis 步骤化
门控（5-1 D4 核销形态——禁全 feature 背景块）、场景级 benchmark 标记。

17 场景三属性分档表（Task 0.6 定稿——层级/Redis 依赖/事件断言三档）:
| #  | 场景          | 层级                 | Redis | 事件断言    |
|----|---------------|----------------------|-------|-------------|
| 1  | AC-1.1 策略表 | 端口级               | 无    | 无          |
| 2  | AC-1.2 默认集 | 端口级               | 无    | 无          |
| 3  | AC-2.1 即 L4  | 服务级               | 真实  | 无          |
| 4  | AC-2.2 双键   | 服务级               | 真实  | 无          |
| 5  | AC-2.3 往返   | 服务级               | 真实  | 无          |
| 6  | AC-3.1 查询   | 服务级               | 真实  | 无          |
| 7  | AC-3.2 异常   | 服务级               | 真实  | 无          |
| 8  | AC-4.1 切换链 | 服务级               | 真实  | 无          |
| 9  | AC-4.2 事件   | 服务级               | 真实  | recording   |
| 10 | AC-4.3 no-op  | 服务级               | 真实  | recording   |
| 11 | AC-4.4 守卫   | 服务级               | 真实  | 无          |
| 12 | AC-5.1 P95    | 服务级（委托集成）   | 真实  | 无          |
| 13 | AC-5.2 成功率 | 服务级（委托集成）   | 真实  | 无          |
| 14 | AC-5.3 并发   | 服务级               | 真实  | 无          |
| 15 | AC-6.1 接线   | 端口级（resolve 禁发命令） | 无 | 无       |
| 16 | AC-6.2 CLI    | CLI 级               | 真实  | 无          |
| 17 | AC-6.3 架构   | 端口级（AST 静态）   | 无    | 无          |

场景序约束: 按 AC 编号序（本 Story 零 LLM 依赖无端口覆写，无 5-3 DC-12 特殊序；
AC-6.2 每次 main() 调用前重执行双清——clear_singleton 驱逐 SINGLETON
redis_adapter 连接池（池绑首个事件循环，跨 asyncio.run 循环复用必抛
"Event loop is closed"）+ clear_scoped 驱逐 SCOPED agent_repository 同款死实例）。

测试隔离条款:
- 场景级独立 Redis 客户端（session 级客户端跨场景 "Event loop is closed"——
  4-1b R2-2-C2 移除共享 fixture 的原因）+ _run_async 同循环纪律
- teardown 双键精确删除（agent/isolation 两 namespace）+ exists 复核删净；
  禁 delete_pattern/flush/全库 scan_iter（多 worker 共享 6380 实例）
- 手动组装纪律: 禁 resolve("isolation_repository") 等发真实命令——一律场景级
  客户端手动组装；resolve 仅做 AC-6.1 接线断言且禁发命令
- BDD 步骤禁 @pytest.mark.asyncio（context 数据丢失）；步骤函数同步 def +
  _run_async 调度
- 延迟 import 纪律: 本 Story 新模块一律步骤函数体内延迟 import（顶部 import
  收集期炸文件，无法逐 Task 转绿）

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/acceptance/test_acceptance_agent_isolation.py -v
"""

from __future__ import annotations

import asyncio
import re
import uuid
from pathlib import Path
from typing import Any, Coroutine, Generator

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from src.infrastructure.storage.redis.key_builder import build_key

REPO_ROOT = Path(__file__).parents[2]

# 文件名不含 "redis" 关键词，acceptance conftest 自动 marker 不生效——显式声明；
# xdist_group("agent-isolation-perf") 与集成性能场景同组——同 worker 串行化计时
pytestmark = [
    pytest.mark.acceptance,
    pytest.mark.redis,
    pytest.mark.xdist_group("agent-isolation-perf"),
]


# ===================================================================
# 共享基建: context fixture + _run_async + 事件记录器 + 手动组装链
# ===================================================================


class _RecordingEventPublisher:
    """手写 duck-typing 事件捕获类（直接实现 EventPublisher 端口契约——5-3 先例）。

    publish 追加事件到 published_events 并返回真实 PublishResult（成功单通道），
    供「恰好一次/零次」计数断言（no-op 判别力——比「至少一次」强）。
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
    """同循环调度（BDD 步骤禁 @pytest.mark.asyncio——context 数据丢失）。"""
    return event_loop.run_until_complete(coro)


@pytest.fixture
def context(
    event_loop: asyncio.AbstractEventLoop,
    acceptance_env_config: Any,
) -> Generator[dict[str, Any], None, None]:
    """场景级独立 Redis 客户端 + 同循环关闭 + 双键精确清理（agent/isolation）。

    session 级客户端跨场景抛 "Event loop is closed"（4-1b R2-2-C2 移除共享
    fixture 的原因）；teardown 顺序: 先还原端口覆写（预留位）→ 逐键精确删除
    双 namespace → exists 复核删净 → 同循环 close。
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
        "_restorers": [],
    }
    yield ctx

    # teardown: 先还原端口覆写，再逐键精确删除（禁 delete_pattern/flush——
    # 多 worker 共享测试 Redis 实例），delete 幂等使被测删除键的二次删除无害
    for restore in ctx["_restorers"]:
        restore()
    for agent_id in ctx["_agent_ids"]:
        for namespace in ("agent", "isolation"):
            _run_async(event_loop, redis_client.delete(build_key(namespace, str(agent_id))))
    # exists 复核: 自产键删净（唯一例外——446 拒绝路径的预生成 uuid 不登记）
    for agent_id in ctx["_agent_ids"]:
        for namespace in ("agent", "isolation"):
            key = build_key(namespace, str(agent_id))
            assert not _run_async(event_loop, redis_client.exists(key)), f"自产键未清理: {key}"
    _run_async(event_loop, redis_client.close())


def _instantiate_ceo_agent(context: dict[str, Any]) -> None:
    """手动组装真实四依赖链并实例化 CEO Agent（场景 Given/When 共用 helper）。

    手动组装纪律: 场景级客户端构造 RedisAgentRepository/RedisIsolationRepository；
    真实 IsolationManagementService（隔离键必须真实写入——验收禁 mock）+
    InstantiateAgentUseCase 第四依赖接线（AC-2 端到端锚）；agent_config_loader
    经 resolve 取（无状态零连接 resolve 安全——5-3 集成 _instantiate_agent 先例）。

    实例化事件（AgentInstantiated）走 InMemoryEventBus 非断言面；隔离切换事件
    走 _RecordingEventPublisher（AC-4.2/4.3 断言面）。
    """
    from src.application.services.isolation_management_service import IsolationManagementService
    from src.application.use_cases.agent_instantiation import InstantiateAgentUseCase
    from src.domain.entities.agent import AgentRole
    from src.domain.ports.resolver import resolve
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository
    from src.infrastructure.storage.redis.redis_isolation_repository import RedisIsolationRepository

    loop: asyncio.AbstractEventLoop = context["_loop"]
    redis_client = context["_redis_client"]
    agent_repository = RedisAgentRepository(adapter=RedisAdapter(redis_client=redis_client))
    isolation_repository = RedisIsolationRepository(adapter=RedisAdapter(redis_client=redis_client))
    recorder = _RecordingEventPublisher()
    isolation_service = IsolationManagementService(
        isolation_repository=isolation_repository,
        agent_repository=agent_repository,
        event_publisher=recorder,
        agent_config_loader=resolve("agent_config_loader"),
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
    context["agent_repository"] = agent_repository
    context["isolation_repository"] = isolation_repository
    context["isolation_service"] = isolation_service
    context["event_recorder"] = recorder


def _run_cli(context: dict[str, Any], argv: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    """进程内 main() 调用（每次前双清——SINGLETON redis_adapter 池绑循环驱逐 +
    SCOPED agent_repository 同款死实例；instantiate 不经 main()——conftest 已
    bootstrap 的进程内二次 bootstrap 必抛 ConflictError，5-3 先例）。"""
    from src.domain.ports.resolver import get_resolver
    from src.entrypoints.agent_cli import main

    get_resolver().clear_singleton()
    get_resolver().clear_scoped()
    context["cli_exit_code"] = main(argv)
    context["cli_captured"] = capsys.readouterr()


# ===================================================================
# AC-1: EIP 四级隔离协议模型（端口级——无 Redis 依赖）
# ===================================================================


@scenario(
    "test_acceptance_agent_isolation.feature",
    "AC-1.1 - 四级隔离策略表完备覆盖",
)
def test_ac_1_1_isolation_policy_table_complete(context: dict[str, Any]) -> None:
    """AC-1.1: 四级 12 维度逐行 + DataIsolationMode 四值。"""


@given("EIP 协议领域模型已定义")
def given_isolation_domain_model(context: dict[str, Any]) -> None:
    """加载策略表领域模型（端口级——无 Redis 依赖，模块缺失即红）。

    各 when/then 步骤直接延迟 import 同一符号（Task 1 交付后模块稳定存在）。
    """
    from src.domain.value_objects.isolation_policy import (
        ISOLATION_POLICIES,
        MVP_ALLOWED_LEVELS,
        DataIsolationMode,
        get_isolation_policy,
    )

    # 存在性锚: 四符号齐备（模块缺失时 import 即红——本断言锁定导入面完整）
    assert ISOLATION_POLICIES and MVP_ALLOWED_LEVELS
    assert callable(DataIsolationMode)
    assert callable(get_isolation_policy)


@when("查询四级隔离等级的策略表")
def when_query_policy_table(context: dict[str, Any]) -> None:
    """四级全量查询（get_isolation_policy 工厂）。"""
    from src.domain.events.enums import IsolationLevel
    from src.domain.value_objects.isolation_policy import get_isolation_policy

    context["queried_policies"] = {
        level: get_isolation_policy(level)
        for level in (
            IsolationLevel.L4_HARD,
            IsolationLevel.L3_SOFT,
            IsolationLevel.L2_COLLAB,
            IsolationLevel.L1_FUSED,
        )
    }


@then("每级策略名称与三重隔离维度逐行一致")
def then_policy_table_matches_architecture(context: dict[str, Any]) -> None:
    """四级 × 三维度逐行断言（12 项 + 每级名称——architecture.md §5.1 硬编码表）。"""
    from src.domain.events.enums import IsolationLevel
    from src.domain.value_objects.isolation_policy import DataIsolationMode

    policies = context["queried_policies"]
    expected = {
        IsolationLevel.L4_HARD: ("硬隔离", True, True, DataIsolationMode.READ_ONLY),
        IsolationLevel.L3_SOFT: ("软隔离", True, False, DataIsolationMode.RESTRICTED_WRITE),
        IsolationLevel.L2_COLLAB: ("协作态", True, False, DataIsolationMode.FREE_WRITE),
        IsolationLevel.L1_FUSED: ("融合态", False, False, DataIsolationMode.FULL_SHARED),
    }
    assert set(policies) == set(expected), "策略表键集与四级不完备一致"
    for level, (name, prompt, tool, data) in expected.items():
        policy = policies[level]
        assert policy.name == name, f"{level.value} 名称漂移: {policy.name!r}"
        assert policy.prompt_isolation is prompt, f"{level.value} prompt_isolation 漂移"
        assert policy.tool_isolation is tool, f"{level.value} tool_isolation 漂移"
        assert policy.data_isolation is data, f"{level.value} data_isolation 漂移"
        assert policy.level is level, f"{level.value} level 字段与键不自洽"


@then("数据隔离模式枚举恰为四值")
def then_data_isolation_mode_four_values(context: dict[str, Any]) -> None:
    """DataIsolationMode 四值断言（core-domain §17.3.3 四值）。"""
    from src.domain.value_objects.isolation_policy import DataIsolationMode

    assert {mode.value for mode in DataIsolationMode} == {
        "read_only",
        "restricted_write",
        "free_write",
        "full_shared",
    }


@scenario(
    "test_acceptance_agent_isolation.feature",
    "AC-1.2 - 默认 L4 与 MVP 允许等级集",
)
def test_ac_1_2_default_level_and_mvp_allowed(context: dict[str, Any]) -> None:
    """AC-1.2: L4 is_default 唯一 + MVP_ALLOWED_LEVELS 恰三值。"""


@when("查询默认等级与 MVP 允许等级集")
def when_query_default_and_mvp(context: dict[str, Any]) -> None:
    """默认等级（is_default 标记）与 MVP_ALLOWED_LEVELS。"""
    from src.domain.value_objects.isolation_policy import ISOLATION_POLICIES

    context["default_marked_levels"] = [level for level, policy in ISOLATION_POLICIES.items() if policy.is_default]


@then("默认等级为 L4 硬隔离且默认标记唯一")
def then_default_level_is_l4_unique(context: dict[str, Any]) -> None:
    """is_default 唯一标记在 L4。"""
    from src.domain.events.enums import IsolationLevel

    assert context["default_marked_levels"] == [IsolationLevel.L4_HARD], "is_default 标记必须唯一且为 L4"


@then("MVP 允许等级集恰为 L4/L3/L2 不含 L1")
def then_mvp_allowed_levels(context: dict[str, Any]) -> None:
    """MVP_ALLOWED_LEVELS 集合断言（L1 融合态 V2 开放）。"""
    from src.domain.events.enums import IsolationLevel
    from src.domain.value_objects.isolation_policy import MVP_ALLOWED_LEVELS

    assert MVP_ALLOWED_LEVELS == frozenset({IsolationLevel.L4_HARD, IsolationLevel.L3_SOFT, IsolationLevel.L2_COLLAB}), (
        "MVP 允许等级集必须恰为 {L4, L3, L2}"
    )


# ===================================================================
# AC-2: 默认 L4 初始化与 Redis 持久化（服务级——真实 Redis）
# ===================================================================


@given("Redis 缓存服务可用")
def given_redis_service_available(context: dict[str, Any]) -> None:
    """Redis 门控（ping 失败动态 skip——禁写死 @pytest.mark.skip）。"""
    try:
        _run_async(context["_loop"], context["_redis_client"].ping())
    except Exception as exc:
        pytest.skip(f"Redis not available: {exc}")


@scenario(
    "test_acceptance_agent_isolation.feature",
    "AC-2.1 - 实例化即 L4 硬隔离持久化",
)
def test_ac_2_1_instantiation_initializes_l4(context: dict[str, Any]) -> None:
    """AC-2.1: 实例化后隔离键真实存在且 L4 + initial_default。"""


@when("实例化一个 CEO Agent")
def when_instantiate_ceo_agent(context: dict[str, Any]) -> None:
    """实例化（AC-2.1/2.2 的被测动作）。"""
    _instantiate_ceo_agent(context)


@then("Redis 存在隔离键且当前等级为 L4")
def then_isolation_key_exists_with_l4(context: dict[str, Any]) -> None:
    """隔离键真实存在（独立键空间 sisys:isolation:{agent_id}）且等级 L4。"""
    import json

    from src.domain.events.enums import IsolationLevel

    key = build_key("isolation", str(context["agent_id"]))
    assert key == f"sisys:isolation:{context['agent_id']}", "隔离键形态漂移"
    raw = _run_async(context["_loop"], context["_redis_client"].hget(key, "latest"))
    assert raw is not None, f"隔离键未持久化: {key}"
    payload = json.loads(raw)
    assert payload["current_level"] == IsolationLevel.L4_HARD.value


@then("隔离状态最近触发原因为 initial_default")
def then_last_trigger_reason_initial_default(context: dict[str, Any]) -> None:
    """初始化触发原因锚。"""
    state = _run_async(context["_loop"], context["isolation_repository"].get_by_agent_id(context["agent_id"]))
    assert state.last_trigger_reason == "initial_default"


@scenario(
    "test_acceptance_agent_isolation.feature",
    "AC-2.2 - 双键空间并存与 TTL 同源",
)
def test_ac_2_2_dual_keyspace_and_ttl(context: dict[str, Any]) -> None:
    """AC-2.2: agent/isolation 双键并存 + TTL 落在配置容差区间。"""


@then("Agent 键与隔离键并存且互不侵入")
def then_dual_keyspace_coexist(context: dict[str, Any]) -> None:
    """双键并存（隔离键不写入 Agent 键空间）。"""
    agent_key = build_key("agent", str(context["agent_id"]))
    isolation_key = build_key("isolation", str(context["agent_id"]))
    client = context["_redis_client"]
    assert _run_async(context["_loop"], client.exists(agent_key)), "Agent 键缺失"
    assert _run_async(context["_loop"], client.exists(isolation_key)), "隔离键缺失"
    # 互不侵入: Agent 键的 Hash 无 isolation field（隔离状态独立键空间）
    agent_fields = _run_async(context["_loop"], client.hkeys(agent_key))
    assert "isolation" not in agent_fields, "隔离状态侵入 Agent 键空间"


@then("两键 TTL 均落在配置 TTL 容差区间")
def then_ttl_within_tolerance(context: dict[str, Any]) -> None:
    """TTL 同源断言（86400 容差 [ttl-5, ttl]——禁真实等待过期）。"""
    client = context["_redis_client"]
    configured_ttl = 86400  # ceo_agent.yaml memory_config.state_ttl 真源
    for namespace in ("agent", "isolation"):
        key = build_key(namespace, str(context["agent_id"]))
        remaining = _run_async(context["_loop"], client.ttl(key))
        assert configured_ttl - 5 <= remaining <= configured_ttl, (
            f"{namespace} 键 TTL 漂移: {remaining}（期望区间 [{configured_ttl - 5}, {configured_ttl}]）"
        )


@scenario(
    "test_acceptance_agent_isolation.feature",
    "AC-2.3 - 持久化往返重建与初始化异常",
)
def test_ac_2_3_roundtrip_and_init_guards(context: dict[str, Any], tmp_path: Path) -> None:
    """AC-2.3: 往返重建逐项相等 + L1 初始化 446 零残留 + TTL 越界 440。"""


@given("已实例化一个 CEO Agent 并切换等级到 L3")
def given_instantiated_and_switched_to_l3(context: dict[str, Any]) -> None:
    """实例化后切 L3（往返重建的字段丰富性前置——updated_at 与原因异于初始态）。"""
    from src.domain.events.enums import IsolationLevel

    _instantiate_ceo_agent(context)
    context["switch_result"] = _run_async(
        context["_loop"],
        context["isolation_service"].switch_isolation_level(context["agent_id"], IsolationLevel.L3_SOFT, "往返前切换"),
    )
    context["state"] = context["switch_result"].state


@when("从仓储重新读取隔离状态")
def when_reload_state_from_repository(context: dict[str, Any]) -> None:
    """仓储直读重建（往返断言面——显式重建 UUID/IsolationLevel/datetime）。"""
    context["rebuilt_state"] = _run_async(
        context["_loop"], context["isolation_repository"].get_by_agent_id(context["agent_id"])
    )


@then("往返重建字段逐项相等")
def then_roundtrip_fields_equal(context: dict[str, Any]) -> None:
    """save → get 重建的 IsolationState 字段逐项相等（显式重建纪律——
    UUID/IsolationLevel/datetime isinstance 断言，透传 str 必红）。"""
    import uuid as uuid_module
    from datetime import datetime as datetime_module

    from src.domain.events.enums import IsolationLevel

    original = context["state"]
    rebuilt = context["rebuilt_state"]
    assert rebuilt is not None, "往返读回为 None"
    assert isinstance(rebuilt.agent_id, uuid_module.UUID), "agent_id 未显式重建 UUID"
    assert isinstance(rebuilt.current_level, IsolationLevel), "current_level 未显式重建枚举"
    assert isinstance(rebuilt.updated_at, datetime_module), "updated_at 未显式重建 datetime"
    assert rebuilt.agent_id == original.agent_id
    assert rebuilt.current_level == original.current_level
    assert rebuilt.current_level is IsolationLevel.L3_SOFT
    assert rebuilt.initialized_at == original.initialized_at
    assert rebuilt.updated_at == original.updated_at
    assert rebuilt.last_trigger_reason == original.last_trigger_reason == "往返前切换"


@when("以配置等级 L1 初始化隔离状态")
def when_initialize_with_configured_l1(context: dict[str, Any], tmp_path: Path) -> None:
    """临时 yaml（L1）+ 真实 loader 驱动服务级 initialize → 446（R1-F35 合规驱动）。

    ceo_agent.yaml 全文基线复制到 tmp 仅改 eip_config.default_isolation_level: L1
    （最小 yaml 过不了 loader 逐段强校验——440 先炸）；加载经
    YamlAgentConfigLoader(config_dir=tmp_path) 构造注入；断言经服务级真实链直调
    （场景预生成 uuid——446 零残留键，不经 InstantiateAgentUseCase——其 agent_id
    内部生成不可回收）。
    """
    from src.application.services.isolation_management_service import IsolationManagementService
    from src.domain.entities.agent import AgentRole
    from src.infrastructure.agent_orch.yaml_agent_config_loader import YamlAgentConfigLoader
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_isolation_repository import RedisIsolationRepository

    baseline = (REPO_ROOT / "configs" / "agents" / "ceo_agent.yaml").read_text(encoding="utf-8")
    assert 'default_isolation_level: "L4"' in baseline, "基线配置锚漂移（default_isolation_level）"
    tampered = baseline.replace('default_isolation_level: "L4"', 'default_isolation_level: "L1"')
    config_dir = tmp_path / "agents"
    config_dir.mkdir()
    (config_dir / "ceo_agent.yaml").write_text(tampered, encoding="utf-8")

    loader = YamlAgentConfigLoader(config_dir=config_dir)
    config = _run_async(context["_loop"], loader.load(AgentRole.CEO))
    assert config.default_isolation_level.value == "L1", "临时 yaml L1 注入未生效"

    # 服务级真实链直调（同场景客户端组装——隔离服务级 446 断言面）
    recorder = _RecordingEventPublisher()
    service = IsolationManagementService(
        isolation_repository=RedisIsolationRepository(adapter=RedisAdapter(redis_client=context["_redis_client"])),
        agent_repository=context["agent_repository"],
        event_publisher=recorder,
        agent_config_loader=loader,
    )
    context["l1_init_agent_id"] = uuid.uuid4()  # 场景预生成（446 零残留断言锚）
    context["l1_init_error"] = None
    try:
        _run_async(
            context["_loop"],
            service.initialize_agent_isolation(context["l1_init_agent_id"], config.default_isolation_level, config.state_ttl),
        )
    except Exception as exc:  # BDD 捕获面——then 逐字段断言类型与编码（统一异常体系）
        context["l1_init_error"] = exc


@then("非法 MVP 等级初始化被 446 拒绝且零残留")
def then_l1_init_rejected_446_no_residue(context: dict[str, Any]) -> None:
    """合法枚举越 MVP 白名单 → 446（实体 initialize 守卫）+ 零残留键。"""
    from src.domain.exceptions import IsolationLevelNotSupportedError

    error = context["l1_init_error"]
    assert isinstance(error, IsolationLevelNotSupportedError), f"非 446 异常: {error!r}"
    assert error.code == "EXCEPTION_446"
    assert error.context["supported_levels"] == ["L4", "L3", "L2"]
    residue_key = build_key("isolation", str(context["l1_init_agent_id"]))
    assert not _run_async(context["_loop"], context["_redis_client"].exists(residue_key)), "446 拒绝路径残留隔离键"


@when("以越界 TTL 持久化隔离状态")
def when_save_with_out_of_range_ttl(context: dict[str, Any]) -> None:
    """仓储防御校验（TTL=59 < 60 下界 → 440）。"""
    context["ttl_error"] = None
    try:
        _run_async(
            context["_loop"],
            context["isolation_repository"].save(context["state"], ttl=59),
        )
    except Exception as exc:  # BDD 捕获面——then 断言 440 编码（统一异常体系）
        context["ttl_error"] = exc


@then("越界 TTL 被仓储以 440 拒绝")
def then_out_of_range_ttl_rejected_440(context: dict[str, Any]) -> None:
    """仓储防御校验（TTL 真源是配置——配置语义异常 440）。"""
    from src.domain.exceptions import AgentConfigError

    error = context["ttl_error"]
    assert isinstance(error, AgentConfigError), f"非 440 异常: {error!r}"
    assert error.code == "EXCEPTION_440"
    assert "state_ttl" in error.context.get("reason", "")


# ===================================================================
# AC-3: 隔离状态查询（服务级——真实 Redis）
# ===================================================================


@scenario(
    "test_acceptance_agent_isolation.feature",
    "AC-3.1 - 隔离状态查询与策略联查",
)
def test_ac_3_1_get_state_and_policy_join(context: dict[str, Any]) -> None:
    """AC-3.1: get_isolation_state 字段完整 + L4 策略联查三维度。"""


@given("已实例化一个 CEO Agent")
def given_instantiated_ceo_agent(context: dict[str, Any]) -> None:
    """场景 Given 前置（手动组装真实链实例化——非断言面）。"""
    _instantiate_ceo_agent(context)


@when("查询该 Agent 的隔离状态")
def when_get_isolation_state(context: dict[str, Any]) -> None:
    """服务级隔离检查入口（AC-5.1 计时锚——443 守卫 + 隔离态读两次真实读）。

    异常捕获面: AC-3.2 的 447 路径（成功场景存 queried_state——then 按场景断言）。
    """
    context["state_query_error"] = None
    try:
        context["queried_state"] = _run_async(
            context["_loop"], context["isolation_service"].get_isolation_state(context["agent_id"])
        )
    except Exception as exc:  # BDD 捕获面——then 逐字段断言类型与编码（统一异常体系）
        context["state_query_error"] = exc


@then("返回完整隔离状态字段")
def then_queried_state_complete(context: dict[str, Any]) -> None:
    """get_isolation_state 返回字段逐项（端口签名 -> IsolationState——策略联查
    由消费方持 state 派生，服务返回值不含策略）。"""
    import uuid as uuid_module
    from datetime import datetime as datetime_module

    from src.domain.events.enums import IsolationLevel

    state = context["queried_state"]
    assert isinstance(state.agent_id, uuid_module.UUID) and state.agent_id == context["agent_id"]
    assert isinstance(state.current_level, IsolationLevel)
    assert state.current_level is IsolationLevel.L4_HARD
    assert isinstance(state.initialized_at, datetime_module)
    assert isinstance(state.updated_at, datetime_module)
    assert state.last_trigger_reason == "initial_default"


@then("联查 L4 策略三维度为硬隔离只读")
def then_policy_join_l4(context: dict[str, Any]) -> None:
    """策略联查（入口/消费方持 state 派生——L4 → 独立/严格隔离/只读）。"""
    from src.domain.value_objects.isolation_policy import DataIsolationMode, get_isolation_policy

    policy = get_isolation_policy(context["queried_state"].current_level)
    assert policy.prompt_isolation is True
    assert policy.tool_isolation is True
    assert policy.data_isolation is DataIsolationMode.READ_ONLY


@scenario(
    "test_acceptance_agent_isolation.feature",
    "AC-3.2 - 447 与 443 异常路径",
)
def test_ac_3_2_not_initialized_and_not_found(context: dict[str, Any]) -> None:
    """AC-3.2: 删隔离键后查询 447（context 携带 agent_id）；随机 UUID 443。"""


@given("已实例化一个 CEO Agent 并删除隔离键")
def given_instantiated_and_isolation_key_deleted(context: dict[str, Any]) -> None:
    """实例化后删除隔离键制造 447 缺失态（agent 键保留——443 守卫通过后 447）。"""
    _instantiate_ceo_agent(context)
    key = build_key("isolation", str(context["agent_id"]))
    _run_async(context["_loop"], context["_redis_client"].delete(key))


@then("抛出 447 隔离状态未初始化异常")
def then_raises_447(context: dict[str, Any]) -> None:
    """447（context 携带 agent_id——同码多因区分锚）。"""
    from src.domain.exceptions import IsolationStateNotInitializedError

    error = context.get("state_query_error")
    assert isinstance(error, IsolationStateNotInitializedError), f"非 447 异常: {error!r}"
    assert error.code == "EXCEPTION_447"
    assert error.context["agent_id"] == str(context["agent_id"])


@when("以随机 UUID 查询隔离状态")
def when_get_state_with_random_uuid(context: dict[str, Any]) -> None:
    """随机 UUID → 443 路径（get 守卫序第一道）。"""
    context["random_uuid"] = uuid.uuid4()
    context["random_query_error"] = None
    try:
        _run_async(
            context["_loop"],
            context["isolation_service"].get_isolation_state(context["random_uuid"]),
        )
    except Exception as exc:  # BDD 捕获面——then 断言 443 编码（统一异常体系）
        context["random_query_error"] = exc


@then("抛出 443 Agent 不存在异常")
def then_raises_443(context: dict[str, Any]) -> None:
    """443（复用——随机 UUID 守卫序第一道）。"""
    from src.domain.exceptions import AgentNotFoundError

    error = context.get("random_query_error") or context.get("random_switch_error")
    assert isinstance(error, AgentNotFoundError), f"非 443 异常: {error!r}"
    assert error.code == "EXCEPTION_443"


# ===================================================================
# AC-4: 隔离等级切换与事件发布（服务级——真实 Redis）
# ===================================================================


@scenario(
    "test_acceptance_agent_isolation.feature",
    "AC-4.1 - 合法链切换 L4 到 L3 到 L2",
)
def test_ac_4_1_switch_chain_l4_l3_l2(context: dict[str, Any]) -> None:
    """AC-4.1: 合法链切换成功 + Redis 状态一致 + updated_at/原因更新。"""


@when(parsers.parse('请求切换隔离等级到 "{level}" 原因 "{reason}"'))
def when_switch_isolation_level(context: dict[str, Any], level: str, reason: str) -> None:
    """服务级切换（MVP 唯一触发通道；"L1" 合法枚举——446 由实体守卫抛出）。

    异常捕获面: AC-4.4 的 446 路径（成功场景存 switch_result——then 按场景断言）。
    """
    from src.domain.events.enums import IsolationLevel

    context["switch_error"] = None
    try:
        context["switch_result"] = _run_async(
            context["_loop"],
            context["isolation_service"].switch_isolation_level(context["agent_id"], IsolationLevel(level), reason),
        )
    except Exception as exc:  # BDD 捕获面——then 逐字段断言类型与编码（统一异常体系）
        context["switch_error"] = exc


@then("Redis 隔离状态为 L2 且返回结果一致")
def then_switched_to_l2_consistent(context: dict[str, Any]) -> None:
    """切换后 Redis 状态与返回结果一致。"""
    import json

    from src.domain.events.enums import IsolationLevel

    result = context["switch_result"]
    assert result.switched is True
    assert result.state.current_level is IsolationLevel.L2_COLLAB
    key = build_key("isolation", str(context["agent_id"]))
    payload = json.loads(_run_async(context["_loop"], context["_redis_client"].hget(key, "latest")))
    assert payload["current_level"] == IsolationLevel.L2_COLLAB.value


@then("更新时间与最近触发原因已更新")
def then_updated_at_and_reason_refreshed(context: dict[str, Any]) -> None:
    """updated_at 推进 + last_trigger_reason 为最后一次切换原因。"""
    state = context["switch_result"].state
    assert state.updated_at > state.initialized_at, "updated_at 未推进（初始化后至少两次切换）"
    assert state.last_trigger_reason == "协作分析需要"
    assert state.initialized_at != state.updated_at


@scenario(
    "test_acceptance_agent_isolation.feature",
    "AC-4.2 - 切换事件字段精确断言",
)
def test_ac_4_2_event_fields_asserted(context: dict[str, Any]) -> None:
    """AC-4.2: IsolationLevelSwitched 恰一次 + 六字段逐项 + reliable 通道复验。"""


@then("IsolationLevelSwitched 事件恰好发布一次")
def then_event_published_exactly_once(context: dict[str, Any]) -> None:
    """恰一次（非「至少一次」——no-op 判别力）。"""
    events = [e for e in context["event_recorder"].published_events if type(e).__name__ == "IsolationLevelSwitched"]
    assert len(events) == 1, f"IsolationLevelSwitched 应恰发布一次（实际 {len(events)}）"
    context["switched_event"] = events[0]


@then("事件六字段逐项断言一致")
def then_event_six_fields(context: dict[str, Any]) -> None:
    """六字段（previous/target 枚举值、trigger_reason、aggregate 派生、时间戳）。"""
    from src.domain.events.enums import IsolationLevel

    event = context["switched_event"]
    assert event.previous_level is IsolationLevel.L4_HARD
    assert event.target_level is IsolationLevel.L3_SOFT
    assert event.trigger_reason == "事件字段验证"
    assert event.approval_chain == []
    assert event.aggregate_id == context["agent_id"]
    assert event.aggregate_type == "Agent"
    assert event.switch_timestamp.tzinfo is not None


@then("事件通道登记复验为 reliable 单通道")
def then_event_channel_registration_verified() -> None:
    """yaml + DEFAULT_MAPPINGS 双登记复验（防漂移——零登记改动故事的验收锚）。"""
    import yaml as yaml_module

    from src.infrastructure.messaging.channel_router import ChannelRouter

    channels = yaml_module.safe_load((REPO_ROOT / "configs" / "event_channels.yaml").read_text(encoding="utf-8"))
    mapping = channels["event_channels"]["IsolationLevelSwitched"]
    assert mapping["delivery_mode"] == "reliable"
    assert mapping["rabbitmq_routing_key"] == "sisys.events.reliable.isolation_level_switched"
    default_mapping = ChannelRouter.DEFAULT_MAPPINGS["IsolationLevelSwitched"]
    assert default_mapping.delivery_mode.value == "reliable"


@scenario(
    "test_acceptance_agent_isolation.feature",
    "AC-4.3 - 同等级切换 no-op 幂等",
)
def test_ac_4_3_same_level_noop(context: dict[str, Any]) -> None:
    """AC-4.3: L4 切 L4 switched=False + 零事件 + updated_at 不变。"""


@then("切换结果为 no-op 且未发布任何事件")
def then_noop_zero_events(context: dict[str, Any]) -> None:
    """no-op（switched=False + 零事件——幂等语义）。"""
    result = context["switch_result"]
    assert result.switched is False
    assert result.event is None
    isolation_events = [e for e in context["event_recorder"].published_events if type(e).__name__ == "IsolationLevelSwitched"]
    assert not isolation_events, "no-op 切换不得发布事件"


@then("隔离状态更新时间未变")
def then_updated_at_unchanged(context: dict[str, Any]) -> None:
    """no-op 后 updated_at 与切换前一致（字段级判别——零仓储写）。"""
    state = _run_async(context["_loop"], context["isolation_repository"].get_by_agent_id(context["agent_id"]))
    assert state.updated_at == context["switch_result"].state.updated_at
    assert state.last_trigger_reason == "initial_default", "no-op 不得改写触发原因"


@scenario(
    "test_acceptance_agent_isolation.feature",
    "AC-4.4 - 446 双路径与 443 切换守卫",
)
def test_ac_4_4_level_not_supported_and_not_found(context: dict[str, Any]) -> None:
    """AC-4.4: L1_FUSED 切换 446（context 原始输入与支持列表）；随机 UUID 443。"""


@then("抛出 446 隔离等级不支持异常")
def then_raises_446(context: dict[str, Any]) -> None:
    """446（合法枚举但 MVP 禁用——context 携带原始输入与支持列表）。"""
    from src.domain.exceptions import IsolationLevelNotSupportedError

    error = context.get("switch_error") or context.get("l1_init_error")
    assert isinstance(error, IsolationLevelNotSupportedError), f"非 446 异常: {error!r}"
    assert error.code == "EXCEPTION_446"
    assert error.context["level"] == "L1"
    assert error.context["supported_levels"] == ["L4", "L3", "L2"]


@when(parsers.parse('以随机 UUID 请求切换隔离等级到 "{level}" 原因 "{reason}"'))
def when_switch_with_random_uuid(context: dict[str, Any], level: str, reason: str) -> None:
    """随机 UUID 切换 → 443 路径（switch 守卫序第一道）。"""
    from src.domain.events.enums import IsolationLevel

    context["random_switch_uuid"] = uuid.uuid4()
    context["random_switch_error"] = None
    try:
        _run_async(
            context["_loop"],
            context["isolation_service"].switch_isolation_level(context["random_switch_uuid"], IsolationLevel(level), reason),
        )
    except Exception as exc:  # BDD 捕获面——then 断言 443 编码（统一异常体系）
        context["random_switch_error"] = exc


# ===================================================================
# AC-5: 性能指标（服务级——真实 Redis；AC-5.1/5.2 委托集成计时 helper）
# ===================================================================


@pytest.mark.benchmark  # 性能场景级标记（不打文件级——5-2 R1-F8 先例）
@scenario(
    "test_acceptance_agent_isolation.feature",
    "AC-5.1 - 隔离检查延迟 P95 小于 100 毫秒",
)
def test_ac_5_1_p95_under_100ms(context: dict[str, Any]) -> None:
    """AC-5.1: 委托集成计时 helper——warmup 1 + 20 采样 quantiles[18] < 0.1s。"""


@when("委托集成计时 helper 采样隔离检查延迟")
def when_delegate_perf_sampling_latency(context: dict[str, Any]) -> None:
    """委托集成模块计时 helper（_PERF_CACHE 单槽缓存——同 xdist_group 同 worker
    命中即返，禁 20 采样双跑；helper 每轮 initialize 产生 agent+isolation 双键
    即时清理）。"""
    from tests.integration.test_integration_agent_isolation import (
        ISOLATION_P95_LIMIT_SECONDS,
        sample_isolation_perf,
    )

    context["perf_result"] = _run_async(context["_loop"], sample_isolation_perf(context["_redis_client"]))
    context["p95_limit"] = ISOLATION_P95_LIMIT_SECONDS


@then("P95 延迟小于 100 毫秒")
def then_p95_under_100ms(context: dict[str, Any]) -> None:
    """P95（perf_counter 服务全链计时——443 守卫 + 隔离态读两次真实读）。"""
    p95 = context["perf_result"]["p95_seconds"]
    assert p95 < context["p95_limit"], f"隔离检查 P95={p95 * 1000:.1f}ms 超阈值 100ms"


@pytest.mark.benchmark
@scenario(
    "test_acceptance_agent_isolation.feature",
    "AC-5.2 - 隔离状态持久化成功率 100%",
)
def test_ac_5_2_persistence_success_rate(context: dict[str, Any]) -> None:
    """AC-5.2: 同批派生——20 次 initialize+读回全成功（分母 20 分子 20）。"""


@when("委托集成计时 helper 采样隔离持久化")
def when_delegate_perf_sampling_persistence(context: dict[str, Any]) -> None:
    """同批派生成功率分子分母（缓存命中即返——独立可跑不依赖 AC-5.1 先行）。"""
    from tests.integration.test_integration_agent_isolation import sample_isolation_perf

    context["perf_result"] = _run_async(context["_loop"], sample_isolation_perf(context["_redis_client"]))


@then("20 次持久化读回全部成功")
def then_persistence_all_success(context: dict[str, Any]) -> None:
    """成功率（同批派生分子分母——20/20）。"""
    result = context["perf_result"]
    assert result["total_count"] == 20, f"采样分母应为 20（实际 {result['total_count']}）"
    assert result["success_count"] == 20, f"持久化成功率不足 100%: {result['success_count']}/{result['total_count']}"


@pytest.mark.benchmark
@scenario(
    "test_acceptance_agent_isolation.feature",
    "AC-5.3 - 并发隔离 Agent 不小于 10",
)
def test_ac_5_3_concurrent_10_agents(context: dict[str, Any]) -> None:
    """AC-5.3: gather 并发 init+switch+get 全成功 + 奇偶互异等级不串扰。"""


@when("10 个 Agent 并发初始化切换与查询")
def when_concurrent_10_agents(context: dict[str, Any]) -> None:
    """10 agent gather 并发 init+switch+get（目标等级互异——奇数 L3 偶数 L2，
    使串扰在主断言即可红而非仅靠变异兜底；单进程并发先例）。"""
    from src.application.services.isolation_management_service import IsolationManagementService
    from src.application.use_cases.agent_instantiation import InstantiateAgentUseCase
    from src.domain.entities.agent import AgentRole
    from src.domain.events.enums import IsolationLevel
    from src.domain.ports.resolver import resolve
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository
    from src.infrastructure.storage.redis.redis_isolation_repository import RedisIsolationRepository

    redis_client = context["_redis_client"]
    agent_repository = RedisAgentRepository(adapter=RedisAdapter(redis_client=redis_client))
    isolation_repository = RedisIsolationRepository(adapter=RedisAdapter(redis_client=redis_client))
    isolation_service = IsolationManagementService(
        isolation_repository=isolation_repository,
        agent_repository=agent_repository,
        event_publisher=_RecordingEventPublisher(),
        agent_config_loader=resolve("agent_config_loader"),
    )
    use_case = InstantiateAgentUseCase(
        config_loader=resolve("agent_config_loader"),
        repository=agent_repository,
        event_publisher=InMemoryEventBus(),
        isolation_service=isolation_service,
    )

    async def _one_agent(index: int) -> dict[str, Any]:
        instantiation = await use_case.execute(role=AgentRole.CEO)
        target = IsolationLevel.L3_SOFT if index % 2 == 0 else IsolationLevel.L2_COLLAB
        switch = await isolation_service.switch_isolation_level(instantiation.agent_id, target, f"并发切换-{index}")
        state = await isolation_service.get_isolation_state(instantiation.agent_id)
        return {"agent_id": instantiation.agent_id, "target": target, "switch": switch, "state": state}

    loop: asyncio.AbstractEventLoop = context["_loop"]

    async def _gather() -> list[dict[str, Any]]:
        return list(await asyncio.gather(*(_one_agent(i) for i in range(10))))

    context["concurrent_results"] = _run_async(loop, _gather())
    for item in context["concurrent_results"]:
        context["_agent_ids"].append(item["agent_id"])


@then("全部成功且目标等级互异互不串扰")
def then_concurrent_all_success_isolated(context: dict[str, Any]) -> None:
    """10 agent 全成功 + 个体等级断言（互异目标——键隔离判别力）。"""
    from src.domain.events.enums import IsolationLevel

    results = context["concurrent_results"]
    assert len(results) == 10
    for item in results:
        assert item["switch"].switched is True
        assert item["state"].current_level is item["target"], f"agent {item['agent_id']} 状态串扰: 期望 {item['target'].value}"
    targets = {item["agent_id"]: item["target"] for item in results}
    assert IsolationLevel.L3_SOFT in targets.values()
    assert IsolationLevel.L2_COLLAB in targets.values()


# ===================================================================
# AC-6: 端口接线、架构合规与 CLI 全链
# ===================================================================


@scenario(
    "test_acceptance_agent_isolation.feature",
    "AC-6.1 - 组合根接线与注入链",
)
def test_ac_6_1_composition_root_wiring(context: dict[str, Any]) -> None:
    """AC-6.1: 两端口 PortSpec 元数据 + resolve isinstance + 用例第四依赖。"""


@given("组合根已完成端口注册")
def given_composition_root_bootstrapped(context: dict[str, Any]) -> None:
    """conftest session 级 _bootstrap_once 已引导——本步骤登记接线断言上下文。"""
    from src.domain.ports.registry import _global_registry

    context["isolation_repo_spec"] = _global_registry.get("isolation_repository")
    context["isolation_service_spec"] = _global_registry.get("isolation_management_service")
    context["use_case_spec"] = _global_registry.get("agent_instantiation_use_case")


@when("解析隔离两端口与实例化用例")
def when_resolve_isolation_ports(context: dict[str, Any]) -> None:
    """resolve 接线断言（构造零 IO 禁发命令——AC-6.1 专属）。"""
    from src.domain.ports.resolver import resolve

    context["resolved_isolation_repo"] = resolve("isolation_repository")
    context["resolved_isolation_service"] = resolve("isolation_management_service")
    context["resolved_use_case"] = resolve("agent_instantiation_use_case")


@then("两端口 PortSpec 元数据完整且 lifetime 为 SINGLETON")
def then_port_spec_complete_singleton(context: dict[str, Any]) -> None:
    """PortSpec 全参数（DC-7——isolation_repository SINGLETON 从源头避免 D7）。"""
    from src.domain.ports.registry import Lifetime

    repo_spec = context["isolation_repo_spec"]
    service_spec = context["isolation_service_spec"]
    assert repo_spec is not None, "isolation_repository 未注册"
    assert service_spec is not None, "isolation_management_service 未注册"
    assert repo_spec.version == "v1.0.0"
    assert repo_spec.lifetime == Lifetime.SINGLETON, "isolation_repository 必须 SINGLETON（DC-7）"
    assert repo_spec.owner == "platform"
    assert repo_spec.tags == ("redis", "agent", "isolation")
    assert repo_spec.module == "src.infrastructure.storage.redis.redis_isolation_repository"
    assert service_spec.version == "v1.0.0"
    assert service_spec.lifetime == Lifetime.SINGLETON
    assert service_spec.owner == "platform"
    assert service_spec.tags == ("agent", "isolation")
    assert service_spec.module == "src.application.services.isolation_management_service"


@then("实例化用例注入隔离服务第四依赖")
def then_use_case_wired_with_isolation(context: dict[str, Any]) -> None:
    """resolve 可达 + 注入链完整（端到端锚由 AC-2.1 真实隔离键背书）。"""
    from src.application.ports.isolation_management import IsolationManagementServicePort
    from src.domain.ports.isolation_repository import IsolationRepository
    from src.domain.ports.registry import Lifetime

    assert isinstance(context["resolved_isolation_repo"], IsolationRepository)
    assert isinstance(context["resolved_isolation_service"], IsolationManagementServicePort)
    use_case = context["resolved_use_case"]
    assert hasattr(use_case, "_isolation_service"), "用例未注入第四依赖 isolation_service"
    assert isinstance(use_case._isolation_service, IsolationManagementServicePort)
    assert context["use_case_spec"].lifetime == Lifetime.SINGLETON


@scenario(
    "test_acceptance_agent_isolation.feature",
    "AC-6.2 - CLI 全链贯通",
)
def test_ac_6_2_cli_full_chain(context: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    """AC-6.2: instantiate(手动组装)→isolation-status→set-isolation→复核 + 守卫路径。"""


@when("执行 CLI isolation-status 查询该 Agent")
def when_cli_isolation_status(context: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    """isolation-status 场景 Agent（成功路径）。"""
    _run_cli(context, ["isolation-status", "--agent-id", str(context["agent_id"])], capsys)


@then("CLI 退出码为 0 且输出 L4 等级与硬隔离策略摘要")
def then_cli_exit0_l4_summary(context: dict[str, Any]) -> None:
    """isolation-status L4 成功输出（等级 + 三维度策略——时间 isoformat 钉死）。"""
    assert context["cli_exit_code"] == 0
    captured = context["cli_captured"]
    assert "L4" in captured.out
    assert "read_only" in captured.out, "策略三维度未随状态输出"
    assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", captured.out), "时间输出须为 isoformat 全格式"


@when(parsers.parse('执行 CLI set-isolation 切换到 "{level}" 原因 "{reason}"'))
def when_cli_set_isolation(context: dict[str, Any], level: str, reason: str, capsys: pytest.CaptureFixture[str]) -> None:
    """set-isolation（成功/L1/L9 共用——446 双路径经统一异常出口）。"""
    _run_cli(
        context,
        [
            "set-isolation",
            "--agent-id",
            str(context["agent_id"]),
            "--level",
            level,
            "--reason",
            reason,
        ],
        capsys,
    )


@then("CLI 退出码为 0 且输出切换摘要 L4 到 L3")
def then_cli_exit0_switch_summary(context: dict[str, Any]) -> None:
    """set-isolation 切换摘要（previous -> target）。"""
    assert context["cli_exit_code"] == 0
    assert "L4 -> L3" in context["cli_captured"].out, "切换摘要须含 L4 -> L3"


@then("CLI 退出码为 0 且输出 L3 等级")
def then_cli_exit0_l3(context: dict[str, Any]) -> None:
    """切换后复核（当前等级 L3）。"""
    assert context["cli_exit_code"] == 0
    captured = context["cli_captured"]
    assert "当前隔离等级: L3" in captured.out
    assert "restricted_write" in captured.out


@when("执行 CLI isolation-status 查询随机不存在的 Agent")
def when_cli_isolation_status_random(context: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    """isolation-status 随机 UUID（443 守卫路径）。"""
    context["cli_random_uuid"] = uuid.uuid4()
    _run_cli(context, ["isolation-status", "--agent-id", str(context["cli_random_uuid"])], capsys)


@then("CLI 退出码为 1 且 stderr 携带异常编码")
def then_cli_exit1_with_exception_code(context: dict[str, Any]) -> None:
    """守卫路径（443/446/447/201 族——正则同时匹配两族）。"""
    assert context["cli_exit_code"] == 1
    assert re.search(r"\[EXCEPTION_(?:201|4[0-9]{2})\]", context["cli_captured"].err), (
        f"stderr 缺统一异常编码: {context['cli_captured'].err!r}"
    )


@scenario(
    "test_acceptance_agent_isolation.feature",
    "AC-6.3 - 架构合规静态扫描",
)
def test_ac_6_3_architecture_static_scan(context: dict[str, Any]) -> None:
    """AC-6.3: domain 零外部依赖 + 组合根外零实例化 + 端口方向（AST）。"""


@given("隔离协议源码文件已交付")
def given_isolation_sources_delivered(context: dict[str, Any]) -> None:
    """交付文件存在性锚（缺失即断言红——收集期不炸）。"""
    expected = [
        "src/domain/value_objects/isolation_policy.py",
        "src/domain/entities/isolation_state.py",
        "src/domain/ports/isolation_repository.py",
        "src/application/ports/isolation_management.py",
        "src/application/services/isolation_management_service.py",
        "src/infrastructure/storage/redis/redis_isolation_repository.py",
    ]
    missing = [rel for rel in expected if not (REPO_ROOT / rel).exists()]
    assert not missing, f"隔离协议源码文件缺失: {missing}"
    context["delivered_sources"] = expected


@when("扫描 domain 层 import 与组合根外实例化")
def when_scan_architecture(context: dict[str, Any]) -> None:
    """AST 静态扫描三面（domain 外部依赖/组合根外实例化/端口方向）。"""
    import ast

    domain_files = [
        "src/domain/value_objects/isolation_policy.py",
        "src/domain/entities/isolation_state.py",
        "src/domain/events/isolation_events.py",
        "src/domain/exceptions/agent_exceptions.py",
        "src/domain/ports/isolation_repository.py",
    ]
    allowed_top_modules = {
        "__future__",
        "typing",
        "dataclasses",
        "uuid",
        "enum",
        "datetime",
        "collections",
        "src",
    }
    violations: dict[str, list[str]] = {"domain_external": [], "outside_root": [], "port_direction": []}

    for rel in domain_files:
        tree = ast.parse((REPO_ROOT / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] not in allowed_top_modules:
                        violations["domain_external"].append(f"{rel}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                if node.module.split(".")[0] not in allowed_top_modules:
                    violations["domain_external"].append(f"{rel}: from {node.module}")

    for class_name in ("RedisIsolationRepository", "IsolationManagementService"):
        for py_file in (REPO_ROOT / "src").rglob("*.py"):
            rel = py_file.relative_to(REPO_ROOT).as_posix()
            if rel == "src/composition_root.py":
                continue
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                target = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
                if target == class_name:
                    violations["outside_root"].append(f"{class_name}: {rel}")

    context["port_direction_imports"] = []
    for rel in (
        "src/application/services/isolation_management_service.py",
        "src/application/use_cases/agent_instantiation.py",
    ):
        tree = ast.parse((REPO_ROOT / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("src.infrastructure"):
                    violations["port_direction"].append(f"{rel}: {node.module}")
                context["port_direction_imports"].append(f"{rel}: {node.module}")

    context["arch_violations"] = violations


@then("domain 隔离文件零外部依赖")
def then_domain_zero_external(context: dict[str, Any]) -> None:
    """AST 扫描（domain-no-external-dependencies 契约——禁 pydantic/redis）。"""
    assert not context["arch_violations"]["domain_external"], (
        f"domain 隔离文件引入外部依赖: {context['arch_violations']['domain_external']}"
    )


@then("服务与仓储仅在组合根实例化")
def then_instantiation_only_in_composition_root(context: dict[str, Any]) -> None:
    """组装纪律（业务代码禁直接 new）。"""
    assert not context["arch_violations"]["outside_root"], f"组合根外直接实例化: {context['arch_violations']['outside_root']}"


@then("端口依赖方向合法")
def then_port_direction_legal(context: dict[str, Any]) -> None:
    """application→domain 合法 + application.ports 同层合法 + 禁 infrastructure。"""
    assert not context["arch_violations"]["port_direction"], f"端口方向违规: {context['arch_violations']['port_direction']}"
    imports_text = "\n".join(context["port_direction_imports"])
    assert "src.application.ports.isolation_management" in imports_text, (
        "IsolationManagementService 实现应用端口 import 缺失（R2 组合注入锚）"
    )
    assert "src.domain.ports.isolation_repository" in imports_text, "仓储端口 import 缺失"


# ===================================================================
# Task 8 收尾: 完成清单场景（src 六文件 + tests 四目录）
# ===================================================================


@scenario(
    "test_acceptance_agent_isolation.feature",
    "收尾 - Story 5.4 完成清单确认",
)
def test_completion_checklist(context: dict[str, Any]) -> None:
    """收尾: src 交付六文件 + tests 四目录齐备（5-2/5-3 AC-6.4 同款）。"""


@when("检查 src 与 tests 的隔离协议交付文件清单")
def when_check_delivery_manifest(context: dict[str, Any]) -> None:
    """存在性清单断言（src 六文件 + tests 四目录关键文件）。"""
    src_files = [
        "src/domain/value_objects/isolation_policy.py",
        "src/domain/entities/isolation_state.py",
        "src/domain/ports/isolation_repository.py",
        "src/application/ports/isolation_management.py",
        "src/application/services/isolation_management_service.py",
        "src/infrastructure/storage/redis/redis_isolation_repository.py",
    ]
    test_files = [
        "tests/unit/domain/value_objects/test_isolation_policy.py",
        "tests/unit/domain/entities/test_isolation_state.py",
        "tests/unit/infrastructure/storage/redis/test_redis_isolation_repository.py",
        "tests/unit/application/services/test_isolation_management_service.py",
        "tests/unit/application/use_cases/test_agent_instantiation.py",
        "tests/unit/interfaces/cli/test_agent_cli.py",
        "tests/unit/architecture/test_arch_agent_isolation.py",
        "tests/contracts/test_port_contract_isolation_repository.py",
        "tests/contracts/test_port_contract_isolation_management_service.py",
        "tests/integration/test_integration_agent_isolation.py",
        "tests/acceptance/test_acceptance_agent_isolation.feature",
        "tests/acceptance/test_acceptance_agent_isolation.py",
    ]
    missing = [rel for rel in src_files + test_files if not (REPO_ROOT / rel).exists()]
    context["manifest_missing"] = missing
    context["manifest_src_count"] = len(src_files)
    context["manifest_test_count"] = len(test_files)


@then("隔离协议源码六文件全部存在")
def then_src_six_files_delivered(context: dict[str, Any]) -> None:
    """src 交付面完整（六新建文件——见 Story File List）。"""
    assert context["manifest_src_count"] == 6
    assert not context["manifest_missing"], f"交付文件缺失: {context['manifest_missing']}"


@then("测试文件四目录齐备")
def then_test_four_directories_complete(context: dict[str, Any]) -> None:
    """unit（7 文件——含追加）/contracts（2）/integration（1）/acceptance（2）齐备。"""
    assert context["manifest_test_count"] == 12
    assert not context["manifest_missing"], f"测试文件缺失: {context['manifest_missing']}"
