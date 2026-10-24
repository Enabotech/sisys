"""Story 5.5 — Agent 三重硬隔离保证验收测试（BDD 场景步骤实现）。

模板基准: test_acceptance_postgresql_relational_layer.py（PG 模板 R6——
多行 @scenario 字面量路径 + 场景绑定与步骤实现交替排列 + AC 横幅分组 +
门控 given + AST 扫描 when）；R6 改造（用户裁定，5-3 先例）: 保留真实断言
（禁 then-pass 占位——PG 模板历史缺陷）、AC 前缀场景名、Redis 步骤化门控
（禁全 feature 背景块）、context dict fixture 场景级客户端 + _run_async
同循环 + 双键清理（5-4 Redis 验收形态）。

19 场景三属性分档表（Task 0 Subtask 0.6 定稿——层级/Redis 依赖/断言面）：

| #  | 场景   | 层级           | Redis 依赖 | 断言面                          |
|----|--------|----------------|-----------|--------------------------------|
| 1  | AC-1.1 | 端口级         | 无        | 判定矩阵全格（MVP 三级+L1 前向） |
| 2  | AC-1.2 | 端口级         | 无        | 资源归属 11 成员+工具判定        |
| 3  | AC-2.1 | 服务级         | 真实      | 放行对照（返回 L4 策略三维度）   |
| 4  | AC-2.2 | 服务级         | 真实      | 异常矩阵（447 fail-closed）     |
| 5  | AC-2.3 | 服务级         | 真实      | 异常矩阵（443 透传）            |
| 6  | AC-3.1 | 服务级         | 真实      | 异常矩阵（Prompt 面 448×10 组合）|
| 7  | AC-3.2 | 服务级         | 真实      | 异常矩阵（私有数据面 448×8 组合）|
| 8  | AC-3.3 | 服务级         | 真实      | 放行+异常矩阵（共享面 L4/L2）   |
| 9  | AC-3.4 | 服务级         | 真实      | 异常+放行（工具白名单/L3 共享池）|
| 10 | AC-3.5 | 服务级         | 真实      | 放行对照（自身 private）+449    |
| 11 | AC-4.1 | 资产面（端口级）| 无        | PROBE_MATRIX 结构断言           |
| 12 | AC-4.2 | 资产面（端口级）| 无        | 拦截率口径断言（逐条比对+辅用例）|
| 13 | AC-5.1 | 服务级         | 真实      | 性能（委托集成计时 helper P95）  |
| 14 | AC-5.2 | 服务级         | 真实      | 性能（通过率 20/20 委托共享采样）|
| 15 | AC-5.3 | 服务级         | 真实      | 性能（并发 10×50 自跑+reason 下钻）|
| 16 | AC-6.1 | 端口级         | 无（禁命令）| 组合根接线（PortSpec+resolve）  |
| 17 | AC-6.2 | 服务级         | 真实      | 真实链行为锚（resolve 用例 447）|
| 18 | AC-6.3 | 端口级         | 无        | AST 静态扫描（验证器三面）       |
| 19 | AC-6.4 | 资产面（端口级）| 无        | 探针套件归位集成范畴（专项裁撤）|

场景序约束: AC-6.2 resolve 用例场景内自清 SINGLETON（AC-6.1 resolve 缓存的
guard 实例绑已关循环——clear_singleton 后重建绑当前场景循环，restorer 收尾
再清，5-3 DC-12 同款问题的自解形态）。

新模块延迟 import 纪律：本 Story 新交付模块（isolation_access / isolation_guard
端口与实现 / 448-449 异常 / 探针套件[归位集成目录] / 集成计时 helper）一律在步骤
函数体内延迟 import——模块顶部 import 会使 pytest 收集期整文件 collection
error，无法逐 Task 转绿（5-3 纪律）。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/acceptance/test_acceptance_agent_triple_isolation.py -v

测试隔离:
    - 验收禁 mock（真实服务纪律）——手动组装纪律：场景级 Redis 客户端构造
      RedisAgentRepository/RedisIsolationRepository/IsolationManagementService/
      IsolationGuardService/InstantiateAgentUseCase 全真实链；agent_config_loader
      经 resolve 取无状态实例合法（5-4 先例）
    - _RecordingEventPublisher 是事件发布端口的记录替身（基础设施豁免面）
    - teardown 双键精确清理（agent/isolation 双 namespace）+ exists 复核删净；
      443 拒绝路径的随机 uuid 不登记（无键产生）
    - 场景级独立 Redis 客户端 + _run_async 同循环（跨循环教训存档）
    - BDD 步骤禁 @pytest.mark.asyncio（context 数据丢失）
    - 验收禁调用 bootstrap()（session 级 _bootstrap_once 已引导）
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any, Coroutine, Generator

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from src.infrastructure.storage.redis.key_builder import build_key

REPO_ROOT = Path(__file__).parents[2]

# 验收侧硬编码期望清单（与探针套件 PROBE_MATRIX 双源比对——程序可内省通道）
_EXPECTED_PROBES: tuple[tuple[str, str], ...] = (
    ("P-01", "EXCEPTION_448"),
    ("P-02", "EXCEPTION_448"),
    ("P-03", "EXCEPTION_448"),
    ("P-04", "EXCEPTION_448"),
    ("P-05", "EXCEPTION_448"),
    ("P-06", "EXCEPTION_448"),
    ("P-07", "EXCEPTION_448"),
    ("T-01", "EXCEPTION_449"),
    ("T-02", "EXCEPTION_448"),
    ("T-03", "EXCEPTION_448"),
    ("T-04", "EXCEPTION_449"),
    ("D-01", "EXCEPTION_448"),
    ("D-02", "EXCEPTION_448"),
    ("D-03", "EXCEPTION_448"),
    ("D-04", "EXCEPTION_448"),
    ("D-05", "EXCEPTION_448"),
    ("D-06", "EXCEPTION_448"),
    ("D-07", "EXCEPTION_448"),
    ("D-08", "EXCEPTION_449"),
    ("D-09", "EXCEPTION_449"),
    ("D-10", "EXCEPTION_449"),
)

# 安全套件 8 条辅助用例函数名（对照 4 + 透传 2 + 纯函数直调 1 + 目录真实名守护 1——不计拦截率分子分母）
_EXPECTED_AUX_CASES: tuple[str, ...] = (
    "test_allow_self_private_resource_read",
    "test_allow_blackboard_read_l4",
    "test_allow_tool_in_allowlist_l4",
    "test_allow_ensure_agent_executable_l4_policy",
    "test_passthrough_443_random_uuid",
    "test_passthrough_447_isolation_key_missing",
    "test_pure_decide_l1_forward_and_invariants",
    "test_t04_tool_name_in_catalog",
)

# 文件名不含 "redis" 关键词，acceptance conftest 自动 marker 不生效——显式声明；
# xdist_group("agent-triple-isolation-perf") 与集成计时场景逐字同组——
# 同 worker 串行化计时保证 _TRIPLE_PERF_CACHE 缓存命中（5-4 委托先例）
pytestmark = [
    pytest.mark.acceptance,
    pytest.mark.redis,
    pytest.mark.xdist_group("agent-triple-isolation-perf"),
]


# ===================================================================
# 共享基建: context fixture + _run_async + 事件记录器 + 手动组装链
# ===================================================================


class _RecordingEventPublisher:
    """手写 duck-typing 事件捕获类（直接实现 EventPublisher 端口契约——5-3/5-4 先例）。

    publish 追加事件到 published_events 并返回真实 PublishResult（成功单通道），
    供「恰好一次/零次」计数断言（隔离切换事件 IsolationLevelSwitched 断言面）。
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

    session 级客户端跨场景抛 "Event loop is closed"（存档教训）；teardown 顺序:
    先还原端口覆写（AC-6.2 SINGLETON 清理 restorer）→ 逐键精确删除双 namespace →
    exists 复核删净 → 同循环 close。
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

    # teardown: 先还原全局缓存/端口覆写，再逐键精确删除（禁 delete_pattern/flush——
    # 多 worker 共享测试 Redis 实例），delete 幂等使被测删除键的二次删除无害
    for restore in ctx["_restorers"]:
        restore()
    for agent_id in ctx["_agent_ids"]:
        for namespace in ("agent", "isolation"):
            _run_async(event_loop, redis_client.delete(build_key(namespace, str(agent_id))))
    # exists 复核: 自产键删净（唯一例外——443 拒绝路径的随机 uuid 不登记）
    for agent_id in ctx["_agent_ids"]:
        for namespace in ("agent", "isolation"):
            key = build_key(namespace, str(agent_id))
            assert not _run_async(event_loop, redis_client.exists(key)), f"自产键未清理: {key}"
    _run_async(event_loop, redis_client.close())


def _assemble_guard_chain(context: dict[str, Any]) -> None:
    """手动组装三重隔离守卫真实链（场景级客户端——禁 resolve 发命令纪律）。

    组装件: RedisAgentRepository + RedisIsolationRepository +
    IsolationManagementService（443→447 守卫序复用）+ IsolationGuardService
    （三依赖真实注入）+ InstantiateAgentUseCase（探针 A/B 构造通道）。
    agent_config_loader 经 resolve 取（无状态零连接 resolve 安全——5-4 先例）。
    """
    from src.application.services.isolation_management_service import IsolationManagementService
    from src.application.use_cases.agent_instantiation import InstantiateAgentUseCase
    from src.domain.ports.resolver import resolve
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository
    from src.infrastructure.storage.redis.redis_isolation_repository import RedisIsolationRepository

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

    from src.application.services.isolation_guard_service import IsolationGuardService

    guard = IsolationGuardService(
        isolation_management_service=isolation_service,
        agent_repository=agent_repository,
        agent_config_loader=resolve("agent_config_loader"),
    )
    instantiate_use_case = InstantiateAgentUseCase(
        config_loader=resolve("agent_config_loader"),
        repository=agent_repository,
        event_publisher=InMemoryEventBus(),
        isolation_service=isolation_service,
    )
    context["agent_repository"] = agent_repository
    context["isolation_repository"] = isolation_repository
    context["isolation_service"] = isolation_service
    context["guard"] = guard
    context["instantiate_use_case"] = instantiate_use_case
    context["event_recorder"] = recorder


def _instantiate_agent(context: dict[str, Any], key: str = "agent_id") -> None:
    """经真实实例化用例构造 CEO Agent（默认 L4）并登记双键清理。"""
    from src.domain.entities.agent import AgentRole

    loop: asyncio.AbstractEventLoop = context["_loop"]
    result = _run_async(loop, context["instantiate_use_case"].execute(role=AgentRole.CEO))
    context["_agent_ids"].append(result.agent_id)
    context[key] = result.agent_id


# ===================================================================
# AC-1: 三重隔离判定核心（端口级——无 Redis 依赖）
# ===================================================================


@scenario(
    "test_acceptance_agent_triple_isolation.feature",
    "AC-1.1 - 判定矩阵完备性覆盖",
)
def test_ac_1_1_decision_matrix_complete(context: dict[str, Any]) -> None:
    """AC-1.1: MVP 三级全格 + L1 前向格（矩阵从策略字段派生）。"""


@given("三重隔离判定核心纯函数已定义")
def given_isolation_access_defined(context: dict[str, Any]) -> None:
    """加载判定核心领域模型（端口级——无 Redis 依赖，模块缺失即红）。"""
    from src.domain.value_objects.isolation_access import (
        AccessOperation,
        IsolationAccessDecision,
        IsolationResource,
        IsolationViolationKind,
        decide_isolation_access,
        decide_tool_access,
        resource_is_private,
    )

    # 存在性锚: 七符号齐备（模块缺失时 import 即红——锁定导入面完整）
    assert callable(decide_isolation_access)
    assert callable(decide_tool_access)
    assert callable(resource_is_private)
    assert len(list(AccessOperation)) == 2, "AccessOperation 应恰两成员"
    assert len(list(IsolationResource)) == 11, "IsolationResource 应恰 11 成员"
    assert len(list(IsolationViolationKind)) == 2, "IsolationViolationKind 应恰两成员"
    assert IsolationAccessDecision is not None


@when("以 MVP 三级与 L1 全组合调用跨 Agent 判定矩阵")
def when_call_decision_matrix_all_cells(context: dict[str, Any]) -> None:
    """MVP 三级 × 三类代表资源 × 读写 × 跨/自身全格采样（类级全格构造性覆盖）。"""
    from src.domain.events.enums import IsolationLevel
    from src.domain.value_objects.isolation_access import AccessOperation, IsolationResource, decide_isolation_access
    from src.domain.value_objects.isolation_policy import get_isolation_policy

    resources = (
        IsolationResource.PROFILE,  # private·Prompt 面代表
        IsolationResource.AGENT_STATE,  # private·数据面代表
        IsolationResource.BLACKBOARD,  # shared 代表
    )
    decisions: dict[tuple[str, str, str, str], Any] = {}
    for level in (IsolationLevel.L4_HARD, IsolationLevel.L3_SOFT, IsolationLevel.L2_COLLAB):
        policy = get_isolation_policy(level)
        for resource in resources:
            for operation in (AccessOperation.READ, AccessOperation.WRITE):
                for cross in (True, False):
                    decision = decide_isolation_access(policy, cross_agent=cross, resource=resource, operation=operation)
                    decisions[(level.value, resource.value, operation.value, str(cross))] = decision
    # L1 前向格（MVP 禁用但矩阵格完整——单测锁定 V2 前向）
    policy_l1 = get_isolation_policy(IsolationLevel.L1_FUSED)
    for resource in resources:
        for operation in (AccessOperation.READ, AccessOperation.WRITE):
            for cross in (True, False):
                decision = decide_isolation_access(policy_l1, cross_agent=cross, resource=resource, operation=operation)
                decisions[("L1", resource.value, operation.value, str(cross))] = decision
    context["decisions"] = decisions


@then("private 资源跨 Agent 访问全等级拒绝且 violation 为 ACCESS_VIOLATION")
def then_private_cross_all_denied(context: dict[str, Any]) -> None:
    """MVP 三级 private+cross 全拒（「独立」贯穿三级）。"""
    from src.domain.value_objects.isolation_access import IsolationViolationKind

    decisions = context["decisions"]
    for key, decision in decisions.items():
        level, resource, operation, cross = key
        if level == "L1" or cross != "True":
            continue
        if resource in ("profile", "agent_state"):
            assert decision.allowed is False, f"{key} 应拒绝"
            assert decision.violation is IsolationViolationKind.ACCESS_VIOLATION, f"{key} violation 漂移"


@then("private 资源自身访问放行")
def then_private_self_allowed(context: dict[str, Any]) -> None:
    """private+self（actor==target）自由读写——全等级。"""
    decisions = context["decisions"]
    for key, decision in decisions.items():
        level, resource, _operation, cross = key
        if cross != "False" or resource not in ("profile", "agent_state"):
            continue
        assert decision.allowed is True, f"{key} 自身 private 访问应放行"
        assert decision.violation is None


@then("shared 资源读全等级放行")
def then_shared_read_allowed(context: dict[str, Any]) -> None:
    """shared+READ 全等级放行（含 L1）。"""
    decisions = context["decisions"]
    for key, decision in decisions.items():
        _level, resource, operation, _cross = key
        if resource == "blackboard" and operation == "read":
            assert decision.allowed is True, f"{key} 共享面读应放行"


@then("shared 资源写按 data_isolation 派生")
def then_shared_write_by_data_isolation(context: dict[str, Any]) -> None:
    """shared+WRITE 按 data_isolation 派生（L4 拒/L3 拒/L2 放行/L1 放行）。"""
    from src.domain.value_objects.isolation_access import IsolationViolationKind

    expectations = {"L4": False, "L3": False, "L2": True, "L1": True}
    decisions = context["decisions"]
    for key, decision in decisions.items():
        level, resource, operation, _cross = key
        if resource != "blackboard" or operation != "write":
            continue
        expected = expectations[level]
        assert decision.allowed is expected, f"{key} 共享面写判定与 data_isolation 派生漂移"
        if expected is False:
            assert decision.violation is IsolationViolationKind.OPERATION_FORBIDDEN, f"{key} violation 漂移"


@then("L1 前向格跨 Agent 私有访问放行")
def then_l1_forward_private_cross_allowed(context: dict[str, Any]) -> None:
    """L1 融合态前向格: private+cross 放行（FULL_SHARED 语义自洽——单边 actor 侧）。"""
    decisions = context["decisions"]
    for key, decision in decisions.items():
        level, resource, _operation, cross = key
        if level == "L1" and cross == "True" and resource in ("profile", "agent_state"):
            assert decision.allowed is True, f"{key} L1 前向格应放行（V2 前向锁定）"


@scenario(
    "test_acceptance_agent_triple_isolation.feature",
    "AC-1.2 - 资源归属分类与工具白名单判定",
)
def test_ac_1_2_resource_taxonomy_and_tool_decision(context: dict[str, Any]) -> None:
    """AC-1.2: IsolationResource 11 成员归属 + decide_tool_access 白名单判定。"""


@then("IsolationResource 恰含 11 成员且 9 私有 2 共享")
def then_isolation_resource_taxonomy(context: dict[str, Any]) -> None:
    """11 成员穷举断言（9 private + 2 shared——值小写下划线形态）。"""
    from src.domain.value_objects.isolation_access import IsolationResource, resource_is_private

    expected_private = {
        "profile",
        "system_prompt",
        "workflow_context",
        "agent_state",
        "isolation_state",
        "session",
        "sandbox_session",
        "tool_execution_history",
        "memory",
    }
    expected_shared = {"blackboard", "shared_workspace"}
    members = {member.value for member in IsolationResource}
    assert members == expected_private | expected_shared, f"资源成员漂移: {members ^ (expected_private | expected_shared)}"
    for member in IsolationResource:
        assert resource_is_private(member) is (member.value in expected_private), f"{member.value} 归属分类漂移"


@when("调用工具白名单判定函数")
def when_call_tool_decision(context: dict[str, Any]) -> None:
    """decide_tool_access 三路采样（L4 白名单内/外 + L3 共享池）。"""
    from src.domain.events.enums import IsolationLevel
    from src.domain.value_objects.isolation_access import decide_tool_access
    from src.domain.value_objects.isolation_policy import get_isolation_policy

    allowlist = ("PESTEL 分析", "SWOT-TOWS")
    policy_l4 = get_isolation_policy(IsolationLevel.L4_HARD)
    policy_l3 = get_isolation_policy(IsolationLevel.L3_SOFT)
    context["tool_decisions"] = {
        "l4_in": decide_tool_access(policy_l4, tool_name="PESTEL 分析", allowed_tools=allowlist),
        "l4_out": decide_tool_access(policy_l4, tool_name="不存在于白名单的工具", allowed_tools=allowlist),
        "l3_any": decide_tool_access(policy_l3, tool_name="不存在于白名单的工具", allowed_tools=allowlist),
    }


@then("tool_isolation 关闭等级放行全部工具")
def then_tool_isolation_off_shared_pool(context: dict[str, Any]) -> None:
    """L3（tool_isolation=False）共享工具池——白名单外名也放行。"""
    decision = context["tool_decisions"]["l3_any"]
    assert decision.allowed is True
    assert decision.violation is None


@then("L4 白名单内放行且白名单外拒绝为 OPERATION_FORBIDDEN")
def then_l4_allowlist_decision(context: dict[str, Any]) -> None:
    """L4 严格白名单: 内放行/外拒（OPERATION_FORBIDDEN——reason 携带工具名）。"""
    from src.domain.value_objects.isolation_access import IsolationViolationKind

    decisions = context["tool_decisions"]
    assert decisions["l4_in"].allowed is True
    assert decisions["l4_in"].violation is None
    out = decisions["l4_out"]
    assert out.allowed is False
    assert out.violation is IsolationViolationKind.OPERATION_FORBIDDEN
    assert "不存在于白名单的工具" in out.reason, f"reason 须携带工具名: {out.reason!r}"


# ===================================================================
# AC-2: 工作流入口 fail-closed 隔离检查（服务级——真实 Redis）
# ===================================================================


@given("Redis 缓存服务可用")
def given_redis_service_available(context: dict[str, Any]) -> None:
    """Redis 门控（ping 失败动态 skip——禁写死 @pytest.mark.skip）。"""
    try:
        _run_async(context["_loop"], context["_redis_client"].ping())
    except Exception as exc:
        pytest.skip(f"Redis not available: {exc}")


@given("三重隔离守卫链已组装")
def given_guard_chain_assembled(context: dict[str, Any]) -> None:
    """组装守卫真实链（AC-2.3 随机 UUID 场景——guard 是被调对象无需真实 Agent）。"""
    _assemble_guard_chain(context)


@given("已实例化一个默认 L4 隔离的 CEO Agent")
def given_one_l4_agent_instantiated(context: dict[str, Any]) -> None:
    """组装守卫链 + 实例化 Agent A（默认 L4）——双键登记清理。"""
    _assemble_guard_chain(context)
    _instantiate_agent(context, "agent_a")


@given("已实例化两个默认 L4 隔离的 CEO Agent")
def given_two_l4_agents_instantiated(context: dict[str, Any]) -> None:
    """组装守卫链 + 实例化 A/B 两 Agent（均默认 L4）——双键登记清理。"""
    _assemble_guard_chain(context)
    _instantiate_agent(context, "agent_a")
    _instantiate_agent(context, "agent_b")


@scenario(
    "test_acceptance_agent_triple_isolation.feature",
    "AC-2.1 - L4 执行前检查放行返回策略",
)
def test_ac_2_1_executable_check_returns_l4_policy(context: dict[str, Any]) -> None:
    """AC-2.1: ensure_agent_executable 放行且返回 L4 策略（三维度可消费）。"""


@when("调用执行前隔离检查")
def when_call_executable_check(context: dict[str, Any]) -> None:
    """ensure_agent_executable(A)（AC-2.1 被测动作）。"""
    context["executable_policy"] = _run_async(context["_loop"], context["guard"].ensure_agent_executable(context["agent_a"]))


@then("检查放行且返回 L4 策略三维度")
def then_executable_returns_l4_policy(context: dict[str, Any]) -> None:
    """返回 IsolationPolicy——prompt/tool 隔离 True + data READ_ONLY。"""
    from src.domain.value_objects.isolation_policy import DataIsolationMode

    policy = context["executable_policy"]
    assert policy.prompt_isolation is True
    assert policy.tool_isolation is True
    assert policy.data_isolation is DataIsolationMode.READ_ONLY


@scenario(
    "test_acceptance_agent_triple_isolation.feature",
    "AC-2.2 - 隔离状态缺失时执行前检查拒绝",
)
def test_ac_2_2_missing_isolation_state_denies(context: dict[str, Any]) -> None:
    """AC-2.2: 删隔离键 → ensure_agent_executable 抛 447（fail-closed）。"""


@when("删除该 Agent 隔离键后调用执行前隔离检查")
def when_delete_key_then_executable_check(context: dict[str, Any]) -> None:
    """删 A 侧隔离键（模拟 TTL 过期/未初始化）→ 447。"""
    from src.domain.exceptions import IsolationStateNotInitializedError

    loop = context["_loop"]
    _run_async(loop, context["_redis_client"].delete(build_key("isolation", str(context["agent_a"]))))
    with pytest.raises(IsolationStateNotInitializedError) as exc_info:
        _run_async(loop, context["guard"].ensure_agent_executable(context["agent_a"]))
    context["caught"] = exc_info.value


@then("抛出 447 隔离状态未初始化异常")
def then_raises_447(context: dict[str, Any]) -> None:
    """异常三段式: isinstance（raises 已锁）→ code → context。"""
    error = context["caught"]
    assert error.code == "EXCEPTION_447"
    assert error.context["agent_id"] == str(context["agent_a"])


@scenario(
    "test_acceptance_agent_triple_isolation.feature",
    "AC-2.3 - Agent 不存在时执行前检查拒绝",
)
def test_ac_2_3_agent_not_found_denies(context: dict[str, Any]) -> None:
    """AC-2.3: 随机 UUID → 443 透传（守卫序 443 先于 447）。"""


@when("以随机 UUID 调用执行前隔离检查")
def when_random_uuid_executable_check(context: dict[str, Any]) -> None:
    """随机 UUID（不登记 _agent_ids——无键产生零残留）。"""
    from src.domain.exceptions import AgentNotFoundError

    context["random_uuid"] = uuid.uuid4()
    with pytest.raises(AgentNotFoundError) as exc_info:
        _run_async(context["_loop"], context["guard"].ensure_agent_executable(context["random_uuid"]))
    context["caught"] = exc_info.value


@then("抛出 443 Agent 不存在异常")
def then_raises_443(context: dict[str, Any]) -> None:
    """443 code + context（agent_id）。"""
    error = context["caught"]
    assert error.code == "EXCEPTION_443"
    assert error.context["agent_id"] == str(context["random_uuid"])


# ===================================================================
# AC-3: 三面运行时守卫（服务级——真实 Redis）
# ===================================================================


@scenario(
    "test_acceptance_agent_triple_isolation.feature",
    "AC-3.1 - Prompt 面跨 Agent 访问拦截",
)
def test_ac_3_1_prompt_face_cross_agent_blocked(context: dict[str, Any]) -> None:
    """AC-3.1: Prompt 面 5 资源 × 读写跨 Agent 访问全 448。"""


@when("对 Prompt 面资源发起跨 Agent 读写访问")
def when_prompt_face_cross_access(context: dict[str, Any]) -> None:
    """A→B: PROFILE/SYSTEM_PROMPT/WORKFLOW_CONTEXT/SESSION/SANDBOX_SESSION × READ/WRITE。"""
    from src.domain.exceptions import IsolationAccessViolationError
    from src.domain.value_objects.isolation_access import AccessOperation, IsolationResource

    loop = context["_loop"]
    guard = context["guard"]
    caught_list: list[tuple[str, str, Any]] = []
    for resource in (
        IsolationResource.PROFILE,
        IsolationResource.SYSTEM_PROMPT,
        IsolationResource.WORKFLOW_CONTEXT,
        IsolationResource.SESSION,
        IsolationResource.SANDBOX_SESSION,
    ):
        for operation in (AccessOperation.READ, AccessOperation.WRITE):
            with pytest.raises(IsolationAccessViolationError) as exc_info:
                _run_async(
                    loop,
                    guard.ensure_agent_access(context["agent_a"], context["agent_b"], resource, operation),
                )
            caught_list.append((resource.value, operation.value, exc_info.value))
    context["prompt_violations"] = caught_list


@then("全部抛出 448 跨 Agent 越权异常且 context 含五字段")
def then_all_448_with_five_context_fields(context: dict[str, Any]) -> None:
    """10 组合全 448 + context 五字段逐项（reason 含等级名——串扰判别锚）。"""
    violations = context["prompt_violations"]
    assert len(violations) == 10
    for resource, operation, error in violations:
        assert error.code == "EXCEPTION_448", f"{resource}/{operation} 应 448"
        assert error.context["actor_agent_id"] == str(context["agent_a"])
        assert error.context["target_agent_id"] == str(context["agent_b"])
        assert error.context["resource"] == resource
        assert error.context["operation"] == operation
        assert "硬隔离" in error.context["reason"], f"reason 须含等级名: {error.context['reason']!r}"


@scenario(
    "test_acceptance_agent_triple_isolation.feature",
    "AC-3.2 - 私有数据面跨 Agent 访问拦截",
)
def test_ac_3_2_data_face_cross_agent_blocked(context: dict[str, Any]) -> None:
    """AC-3.2: 数据面 4 资源 × 读写跨 Agent 访问全 448。"""


@when("对私有数据面资源发起跨 Agent 读写访问")
def when_data_face_cross_access(context: dict[str, Any]) -> None:
    """A→B: AGENT_STATE/ISOLATION_STATE/MEMORY/TOOL_EXECUTION_HISTORY × READ/WRITE。"""
    from src.domain.exceptions import IsolationAccessViolationError
    from src.domain.value_objects.isolation_access import AccessOperation, IsolationResource

    loop = context["_loop"]
    guard = context["guard"]
    caught_list: list[tuple[str, str, Any]] = []
    for resource in (
        IsolationResource.AGENT_STATE,
        IsolationResource.ISOLATION_STATE,
        IsolationResource.MEMORY,
        IsolationResource.TOOL_EXECUTION_HISTORY,
    ):
        for operation in (AccessOperation.READ, AccessOperation.WRITE):
            with pytest.raises(IsolationAccessViolationError) as exc_info:
                _run_async(
                    loop,
                    guard.ensure_agent_access(context["agent_a"], context["agent_b"], resource, operation),
                )
            caught_list.append((resource.value, operation.value, exc_info.value))
    context["data_violations"] = caught_list


@then("全部抛出 448 跨 Agent 越权异常")
def then_all_448(context: dict[str, Any]) -> None:
    """8 组合全 448（code + actor/target context 锚）。"""
    violations = context["data_violations"]
    assert len(violations) == 8
    for _resource, _operation, error in violations:
        assert error.code == "EXCEPTION_448"
        assert error.context["actor_agent_id"] == str(context["agent_a"])
        assert error.context["target_agent_id"] == str(context["agent_b"])


@scenario(
    "test_acceptance_agent_triple_isolation.feature",
    "AC-3.3 - 共享面访问矩阵",
)
def test_ac_3_3_shared_face_matrix(context: dict[str, Any]) -> None:
    """AC-3.3: BLACKBOARD 读放行/L4 写 449/L2 切换后写放行。"""


@when("L4 下读公共黑板")
def when_l4_read_blackboard(context: dict[str, Any]) -> None:
    """A→B BLACKBOARD READ（shared+READ 全等级放行格）。"""
    from src.domain.value_objects.isolation_access import AccessOperation, IsolationResource

    context["allowed_result"] = _run_async(
        context["_loop"],
        context["guard"].ensure_agent_access(
            context["agent_a"], context["agent_b"], IsolationResource.BLACKBOARD, AccessOperation.READ
        ),
    )


@then("放行")
def then_allowed(context: dict[str, Any]) -> None:
    """放行静默（断言型守卫——无异常即放行，结果 None 锚）。"""
    assert context["allowed_result"] is None


@when("L4 下写公共黑板")
def when_l4_write_blackboard(context: dict[str, Any]) -> None:
    """A→B BLACKBOARD WRITE（L4 READ_ONLY → 449）。"""
    from src.domain.exceptions import IsolationOperationForbiddenError
    from src.domain.value_objects.isolation_access import AccessOperation, IsolationResource

    with pytest.raises(IsolationOperationForbiddenError) as exc_info:
        _run_async(
            context["_loop"],
            context["guard"].ensure_agent_access(
                context["agent_a"], context["agent_b"], IsolationResource.BLACKBOARD, AccessOperation.WRITE
            ),
        )
    context["caught"] = exc_info.value


@then("抛出 449 策略禁止操作异常")
def then_raises_449(context: dict[str, Any]) -> None:
    """449 code + context（agent_id/operation/reason——reason 编码触发细分）。"""
    error = context["caught"]
    assert error.code == "EXCEPTION_449"
    assert error.context["agent_id"] == str(context["agent_a"])
    assert "operation" in error.context
    assert "reason" in error.context


@when(parsers.parse("切换等级到 {level} 后写公共黑板"))
def when_switch_level_then_write_blackboard(context: dict[str, Any], level: str) -> None:
    """A 服务级切换等级（真实 IsolationLevelSwitched 发布）→ BLACKBOARD WRITE。"""
    from src.domain.events.enums import IsolationLevel
    from src.domain.value_objects.isolation_access import AccessOperation, IsolationResource

    loop = context["_loop"]
    _run_async(
        loop,
        context["isolation_service"].switch_isolation_level(
            context["agent_a"], IsolationLevel(level), f"验收场景-{level}-共享面写"
        ),
    )
    if level == "L2":
        # L2 FREE_WRITE → 放行（无异常即通过）
        context["allowed_result"] = _run_async(
            loop,
            context["guard"].ensure_agent_access(
                context["agent_a"], context["agent_b"], IsolationResource.BLACKBOARD, AccessOperation.WRITE
            ),
        )
    else:
        from src.domain.exceptions import IsolationOperationForbiddenError

        with pytest.raises(IsolationOperationForbiddenError) as exc_info:
            _run_async(
                loop,
                context["guard"].ensure_agent_access(
                    context["agent_a"], context["agent_b"], IsolationResource.BLACKBOARD, AccessOperation.WRITE
                ),
            )
        context["caught"] = exc_info.value


@scenario(
    "test_acceptance_agent_triple_isolation.feature",
    "AC-3.4 - 工具白名单守卫",
)
def test_ac_3_4_tool_allowlist_guard(context: dict[str, Any]) -> None:
    """AC-3.4: L4 白名单外 449/白名单内放行/L3 共享池放行。"""


@when("以白名单外工具名调用工具守卫")
def when_tool_outside_allowlist(context: dict[str, Any]) -> None:
    """非白名单名直构造（guard 不查注册表——假名即 449，无需 tmp 通道）。"""
    from src.domain.exceptions import IsolationOperationForbiddenError

    context["outside_tool_name"] = "绝对不在白名单内的工具名"
    with pytest.raises(IsolationOperationForbiddenError) as exc_info:
        _run_async(context["_loop"], context["guard"].ensure_tool_access(context["agent_a"], context["outside_tool_name"]))
    context["caught"] = exc_info.value


@then("抛出 449 且 reason 携带工具名")
def then_449_reason_contains_tool_name(context: dict[str, Any]) -> None:
    """reason 形如 tool_not_in_allowlist:{tool_name}（DC-4 契约）。"""
    error = context["caught"]
    assert error.code == "EXCEPTION_449"
    assert error.context["reason"] == f"tool_not_in_allowlist:{context['outside_tool_name']}"


@when("以白名单内工具名调用工具守卫")
def when_tool_inside_allowlist(context: dict[str, Any]) -> None:
    """白名单内真实名（ceo_agent.yaml 全 23 名——经 AgentConfig.allowed_tools 真源）。"""
    context["allowed_result"] = _run_async(
        context["_loop"], context["guard"].ensure_tool_access(context["agent_a"], "PESTEL 分析")
    )


@when(parsers.parse("切换等级到 {level} 后以任意工具名调用工具守卫"))
def when_switch_level_then_tool_guard(context: dict[str, Any], level: str) -> None:
    """L3（tool_isolation=False）共享池——白名单外名也放行（切换真实发布）。"""
    from src.domain.events.enums import IsolationLevel

    loop = context["_loop"]
    _run_async(
        loop,
        context["isolation_service"].switch_isolation_level(
            context["agent_a"], IsolationLevel(level), f"验收场景-{level}-共享工具池"
        ),
    )
    context["allowed_result"] = _run_async(
        loop, context["guard"].ensure_tool_access(context["agent_a"], "绝对不在白名单内的工具名")
    )


@then("放行共享工具池")
def then_shared_tool_pool_allowed(context: dict[str, Any]) -> None:
    """L3 共享池放行（结果 None 锚）。"""
    assert context["allowed_result"] is None


@scenario(
    "test_acceptance_agent_triple_isolation.feature",
    "AC-3.5 - 自身私有资源访问放行",
)
def test_ac_3_5_self_private_access_allowed(context: dict[str, Any]) -> None:
    """AC-3.5: actor==target 的 private 资源全操作放行 + shared 写不因 self 豁免。"""


@when("对自身私有资源发起读写访问")
def when_self_private_access(context: dict[str, Any]) -> None:
    """A→A: 全部 9 private 资源 × READ/WRITE 全放行。"""
    from src.domain.value_objects.isolation_access import AccessOperation, IsolationResource

    loop = context["_loop"]
    guard = context["guard"]
    results = []
    for resource in IsolationResource:
        if resource in (IsolationResource.BLACKBOARD, IsolationResource.SHARED_WORKSPACE):
            continue  # shared 资源走独立断言（写不因 self 豁免）
        for operation in (AccessOperation.READ, AccessOperation.WRITE):
            results.append(
                _run_async(loop, guard.ensure_agent_access(context["agent_a"], context["agent_a"], resource, operation))
            )
    context["self_private_result"] = results


@then("全部放行")
def then_self_private_all_allowed(context: dict[str, Any]) -> None:
    """9 private × 2 操作 = 18 组合全放行（结果全 None）。"""
    results = context["self_private_result"]
    assert len(results) == 18
    assert all(result is None for result in results)


@when("对自身发起公共黑板写访问")
def when_self_blackboard_write(context: dict[str, Any]) -> None:
    """A→A BLACKBOARD WRITE（L4 READ_ONLY → 449——shared 面不分 cross/self）。"""
    from src.domain.exceptions import IsolationOperationForbiddenError
    from src.domain.value_objects.isolation_access import AccessOperation, IsolationResource

    with pytest.raises(IsolationOperationForbiddenError) as exc_info:
        _run_async(
            context["_loop"],
            context["guard"].ensure_agent_access(
                context["agent_a"], context["agent_a"], IsolationResource.BLACKBOARD, AccessOperation.WRITE
            ),
        )
    context["caught"] = exc_info.value


# ===================================================================
# AC-4: 跨 Agent 穿透探针矩阵（安全套件资产面——无 Redis 依赖）
# ===================================================================


@given("安全测试套件与探针矩阵常量已加载")
def given_probe_matrix_loaded(context: dict[str, Any]) -> None:
    """加载安全套件模块（资产面——无 Redis，套件缺失即红）。"""
    from tests.integration import test_integration_isolation_security as probe_module

    context["probe_matrix"] = probe_module.PROBE_MATRIX
    context["security_module"] = probe_module


@scenario(
    "test_acceptance_agent_triple_isolation.feature",
    "AC-4.1 - 穿透探针矩阵资产就绪",
)
def test_ac_4_1_probe_matrix_asset_ready(context: dict[str, Any]) -> None:
    """AC-4.1: PROBE_MATRIX 计数 + 三面/预期码分布断言。"""


@then("PROBE_MATRIX 恰含 21 条探针定义")
def then_probe_matrix_21(context: dict[str, Any]) -> None:
    """穷举枚举基数（21——拦截率分母锚）。"""
    assert len(context["probe_matrix"]) == 21, f"探针矩阵应 21 条: {len(context['probe_matrix'])}"


@then("三面分布为 Prompt 七条、工具四条、数据十条")
def then_probe_face_distribution(context: dict[str, Any]) -> None:
    """P×7/T×4/D×10 按 id 前缀计数。"""
    probes = context["probe_matrix"]
    faces = {"P": 0, "T": 0, "D": 0}
    for probe in probes:
        faces[probe.id.split("-")[0]] += 1
    assert faces == {"P": 7, "T": 4, "D": 10}, f"三面分布漂移: {faces}"


@then("预期码分布为 448 十六条、449 五条")
def then_probe_code_distribution(context: dict[str, Any]) -> None:
    """16×448 + 5×449（violation 语义轴分布锚）。"""
    probes = context["probe_matrix"]
    codes: dict[str, int] = {}
    for probe in probes:
        codes[probe.expected_code] = codes.get(probe.expected_code, 0) + 1
    assert codes == {"EXCEPTION_448": 16, "EXCEPTION_449": 5}, f"预期码分布漂移: {codes}"


@scenario(
    "test_acceptance_agent_triple_isolation.feature",
    "AC-4.2 - 拦截率断言口径完备",
)
def test_ac_4_2_interception_rate_criteria(context: dict[str, Any]) -> None:
    """AC-4.2: 逐条 (id, expected_code) 双源比对 + 辅用例 7 条 + 口径隔离。"""


@then("探针套件含 21 条独立参数化用例与 7 条辅助用例")
def then_probe_and_aux_cases_exist(context: dict[str, Any]) -> None:
    """参数化探针函数 + 7 条辅助用例函数存在性（命名即分档）。"""
    module = context["security_module"]
    assert callable(getattr(module, "test_probe_cross_agent_access", None)), "21 条参数化穿透探针函数缺失"
    missing = [name for name in _EXPECTED_AUX_CASES if not callable(getattr(module, name, None))]
    assert not missing, f"辅助用例函数缺失: {missing}"


@then("对照用例不计入拦截率分子分母")
def then_aux_cases_outside_matrix(context: dict[str, Any]) -> None:
    """辅用例与 PROBE_MATRIX 命名空间隔离（id 不含 allow/passthrough/pure 前缀）
    + 逐条 (id, expected_code) 双源硬编码比对（21/21 全比对——验收侧单真源通道）。"""
    probes = context["probe_matrix"]
    for probe in probes:
        assert not probe.id.startswith(("allow", "passthrough", "pure")), f"对照用例混入矩阵: {probe.id}"
    actual = tuple((probe.id, probe.expected_code) for probe in probes)
    assert actual == _EXPECTED_PROBES, f"探针矩阵与验收期望清单漂移: {set(actual) ^ set(_EXPECTED_PROBES)}"


# ===================================================================
# AC-5: 性能与并发（服务级——真实 Redis，委托集成计时）
# ===================================================================


def _delegate_perf_sampling(context: dict[str, Any]) -> Any:
    """委托集成计时 helper（_TRIPLE_PERF_CACHE 单槽缓存——同 xdist_group 同 worker
    缓存命中，禁 20 采样双跑拖慢套件；5-4 委托模式照抄）。"""
    from tests.integration.test_integration_agent_triple_isolation import sample_triple_isolation_perf

    return _run_async(context["_loop"], sample_triple_isolation_perf(context["_redis_client"]))


@scenario(
    "test_acceptance_agent_triple_isolation.feature",
    "AC-5.1 - 隔离检查延迟 P95 小于 50 毫秒",
)
def test_ac_5_1_p95_under_50ms(context: dict[str, Any]) -> None:
    """AC-5.1: ensure_agent_executable 全链 P95 < 50ms（委托计时）。"""


@when("委托集成计时 helper 采样执行前隔离检查延迟")
def when_delegate_perf_sampling(context: dict[str, Any]) -> None:
    """warmup 1 + 20 采样 quantiles[18]（常量单源 import 集成模块）。"""
    context["perf_result"] = _delegate_perf_sampling(context)


@then("P95 小于 50 毫秒")
def then_p95_under_50ms(context: dict[str, Any]) -> None:
    """TRIPLE_ISOLATION_P95_LIMIT_SECONDS = 0.05 常量单源断言。"""
    from tests.integration.test_integration_agent_triple_isolation import TRIPLE_ISOLATION_P95_LIMIT_SECONDS

    assert TRIPLE_ISOLATION_P95_LIMIT_SECONDS == 0.05, "P95 阈值常量漂移（单源锚）"
    p95 = context["perf_result"]["p95_seconds"]
    assert p95 < TRIPLE_ISOLATION_P95_LIMIT_SECONDS, (
        f"隔离检查 P95={p95 * 1000:.1f}ms 超阈值 {TRIPLE_ISOLATION_P95_LIMIT_SECONDS * 1000:.0f}ms"
    )


@scenario(
    "test_acceptance_agent_triple_isolation.feature",
    "AC-5.2 - 隔离检查通过率 100%",
)
def test_ac_5_2_pass_rate_100(context: dict[str, Any]) -> None:
    """AC-5.2: 20 轮连续检查全放行（分子分母显式——委托共享采样）。"""


@when("执行 20 轮连续执行前隔离检查")
def when_20_rounds_executable_check(context: dict[str, Any]) -> None:
    """通过率采样委托（缓存命中——与 AC-5.1 同批）。"""
    context["perf_result"] = _delegate_perf_sampling(context)


@then("通过率 20/20 全放行")
def then_pass_rate_20_of_20(context: dict[str, Any]) -> None:
    """分子分母显式断言（20/20）。"""
    result = context["perf_result"]
    assert result["total_count"] == 20, f"采样轮数漂移: {result['total_count']}"
    assert result["success_count"] == 20, f"通过率 {result['success_count']}/20 应全放行"


@scenario(
    "test_acceptance_agent_triple_isolation.feature",
    "AC-5.3 - 并发 10 Agent 穿透探针零泄露",
)
def test_ac_5_3_concurrent_10x50_no_leak(context: dict[str, Any]) -> None:
    """AC-5.3: 10 Agent（actor 等级互异）× 50 探针并发 500/500 拦截 + reason 下钻。"""


@when("10 个互异等级 Agent 并发各发 50 次跨 Agent 穿透探针")
def when_10_agents_50_probes_concurrent(context: dict[str, Any]) -> None:
    """并发自跑: 奇数 actor 保持 L4/偶数 actor 服务级切换 L3（等级互异——
    448 reason 含 policy.name 随 actor 等级互异，串扰即 reason 错配可检测）。"""
    from src.domain.entities.agent import AgentRole
    from src.domain.events.enums import IsolationLevel
    from src.domain.value_objects.isolation_access import AccessOperation, IsolationResource

    loop: asyncio.AbstractEventLoop = context["_loop"]
    guard = context["guard"]
    isolation_service = context["isolation_service"]

    # 探针目标 B（固定 target——10 actor 对同一 B 发探针）
    target = _run_async(loop, context["instantiate_use_case"].execute(role=AgentRole.CEO))
    context["_agent_ids"].append(target.agent_id)

    async def _one_probe_actor(index: int) -> list[tuple[str, Any]]:
        instantiation = await context["instantiate_use_case"].execute(role=AgentRole.CEO)
        context["_agent_ids"].append(instantiation.agent_id)  # keys 即时登记（gather 部分失败仍可清理）
        actor_id = instantiation.agent_id
        level_name = "硬隔离"
        if index % 2 == 0:  # 偶数 actor 切 L3（软隔离）——奇 L4 偶 L3 等级互异
            await isolation_service.switch_isolation_level(actor_id, IsolationLevel.L3_SOFT, f"并发互异-{index}")
            level_name = "软隔离"
        outcomes: list[tuple[str, Any]] = []
        for _ in range(50):
            try:
                await guard.ensure_agent_access(actor_id, target.agent_id, IsolationResource.PROFILE, AccessOperation.READ)
                outcomes.append((level_name, None))
            except Exception as exc:  # 探针预期异常逐条收集（448 分类计数形态——return_exceptions 语义的探针内化）
                outcomes.append((level_name, exc))
        return outcomes

    async def _gather_probes() -> list[Any]:
        return list(await asyncio.gather(*(_one_probe_actor(i) for i in range(10)), return_exceptions=True))

    gathered = _run_async(loop, _gather_probes())
    concurrent_outcomes: list[tuple[str, Any]] = []
    for actor_outcomes in gathered:  # isinstance 显式收窄（return_exceptions 联合类型）
        assert not isinstance(actor_outcomes, BaseException), f"并发构造异常: {actor_outcomes}"
        concurrent_outcomes.extend(actor_outcomes)
    context["concurrent_outcomes"] = concurrent_outcomes


@then("拦截率 500/500 且 448 原因含等级名随 actor 等级互异")
def then_interception_500_and_reason_level_distinct(context: dict[str, Any]) -> None:
    """逐条分类计数（448 拦截/其他失败）+ reason 等级名下钻（串扰判别锚）。"""
    from src.domain.exceptions import IsolationAccessViolationError

    outcomes = context["concurrent_outcomes"]
    assert len(outcomes) == 500
    blocked = 0
    for level_name, outcome in outcomes:
        assert isinstance(outcome, IsolationAccessViolationError), f"探针应全部 448 拦截（level={level_name}）: {outcome!r}"
        assert outcome.code == "EXCEPTION_448"
        # reason 等级名下钻: actor 取到他人 state（串扰）即 reason 等级名错配可检测
        assert level_name in outcome.context["reason"], (
            f"448 reason 等级名错配（期望 {level_name}）: {outcome.context['reason']!r}"
        )
        blocked += 1
    assert blocked == 500, f"拦截率 {blocked}/500 应全拦截"


# ===================================================================
# AC-6: 端口接线、架构合规与安全测试基建
# ===================================================================


@scenario(
    "test_acceptance_agent_triple_isolation.feature",
    "AC-6.1 - 组合根接线与双接线点注入",
)
def test_ac_6_1_composition_root_wiring(context: dict[str, Any]) -> None:
    """AC-6.1: guard PortSpec 元数据 + resolve isinstance + 双接线 lambda 注入。"""


@given("组合根已完成端口注册")
def given_composition_root_bootstrapped(context: dict[str, Any]) -> None:
    """conftest session 级 _bootstrap_once 已引导——登记接线断言上下文。"""
    from src.domain.ports.registry import _global_registry

    context["guard_spec"] = _global_registry.get("isolation_guard_service")
    assert context["guard_spec"] is not None, "isolation_guard_service 未注册"


@then("隔离守卫端口 PortSpec 元数据完整且 lifetime 为 SINGLETON")
def then_guard_port_spec_complete(context: dict[str, Any]) -> None:
    """PortSpec 全参数（name/version/interface/lifetime/owner/module/tags）。"""
    from src.application.ports.isolation_guard import IsolationGuardPort
    from src.domain.ports.registry import Lifetime

    spec = context["guard_spec"]
    assert spec.version == "v1.0.0"
    assert spec.lifetime == Lifetime.SINGLETON
    assert spec.owner == "platform"
    assert spec.tags == ("agent", "isolation", "security")
    assert spec.module == "src.application.services.isolation_guard_service"
    assert spec.interface is IsolationGuardPort


@then("resolve 可达且实现类满足端口契约")
def then_guard_resolve_reachable(context: dict[str, Any]) -> None:
    """resolve 构造零 IO 禁发命令（AC-6.1 专属纪律）。"""
    from src.application.ports.isolation_guard import IsolationGuardPort
    from src.domain.ports.resolver import resolve

    guard = resolve("isolation_guard_service")
    assert isinstance(guard, IsolationGuardPort)
    assert type(guard).__name__ == "IsolationGuardService"


@then("双接线点 lambda 注入第五依赖")
def then_both_wiring_points_injected(context: dict[str, Any]) -> None:
    """组合根源码断言: isolation_guard=resolver.resolve(...) 恰两处
    （RunAgentWorkflowUseCase + AgentWorkflowService——lambda 漏注入的静态锚）。"""
    source = (REPO_ROOT / "src" / "composition_root.py").read_text(encoding="utf-8")
    expected_fragment = 'isolation_guard=resolver.resolve("isolation_guard_service")'
    assert source.count(expected_fragment) == 2, f"双接线点 lambda 注入应恰两处（实际 {source.count(expected_fragment)}）"


@scenario(
    "test_acceptance_agent_triple_isolation.feature",
    "AC-6.2 - 工作流入口 fail-closed 真实链",
)
def test_ac_6_2_entry_fail_closed_real_chain(context: dict[str, Any]) -> None:
    """AC-6.2: resolve 用例（组合根 lambda 全真实链）→ 删隔离键 → execute 447。"""


@when("删除隔离键后经组合根用例执行工作流")
def when_delete_key_then_resolve_use_case_execute(context: dict[str, Any]) -> None:
    """resolve("agent_workflow_use_case")（第五依赖 lambda 注入端到端锚）。

    SINGLETON 自清: AC-6.1 resolve 缓存的 guard/repository 实例绑已关循环——
    clear_singleton 后重建绑当前场景循环（restorer 收尾再清，5-3 DC-12 同款）。
    """
    from src.domain.exceptions import IsolationStateNotInitializedError
    from src.domain.ports.resolver import get_resolver, resolve

    loop = context["_loop"]
    get_resolver().clear_singleton()

    def _restore() -> None:
        get_resolver().clear_singleton()

    context["_restorers"].append(_restore)

    _run_async(loop, context["_redis_client"].delete(build_key("isolation", str(context["agent_a"]))))
    use_case = resolve("agent_workflow_use_case")
    with pytest.raises(IsolationStateNotInitializedError) as exc_info:
        _run_async(loop, use_case.execute(context["agent_a"], "验证入口 fail-closed 拒绝执行"))
    context["caught"] = exc_info.value


@then("工作流抛出 447 隔离状态未初始化异常")
def then_workflow_raises_447(context: dict[str, Any]) -> None:
    """入口 fail-closed: 447 类型本身即守卫序锚（guard 在档案加载前抛——
    若档案先加载则异常面完全不同；单测级序断言见 Task 3）。"""
    error = context["caught"]
    assert error.code == "EXCEPTION_447"
    assert error.context["agent_id"] == str(context["agent_a"])


@scenario(
    "test_acceptance_agent_triple_isolation.feature",
    "AC-6.3 - 架构合规静态扫描",
)
def test_ac_6_3_architecture_static_scan(context: dict[str, Any]) -> None:
    """AC-6.3: domain 零外部依赖 + 组合根外零实例化 + 端口方向/判定真源（AST）。"""


@given("三重隔离执行面源码已交付")
def given_triple_isolation_sources_delivered(context: dict[str, Any]) -> None:
    """交付文件存在性锚（缺失即断言红——收集期不炸）。"""
    expected = [
        "src/domain/value_objects/isolation_access.py",
        "src/domain/exceptions/agent_exceptions.py",
        "src/application/ports/isolation_guard.py",
        "src/application/services/isolation_guard_service.py",
        "src/application/use_cases/run_agent_workflow.py",
        "src/application/services/agent_workflow_service.py",
    ]
    missing = [rel for rel in expected if not (REPO_ROOT / rel).exists()]
    assert not missing, f"三重隔离执行面源码文件缺失: {missing}"
    context["delivered_sources"] = expected


@when("扫描执行面架构约束")
def when_scan_triple_isolation_architecture(context: dict[str, Any]) -> None:
    """AST 静态扫描四面（domain 外部依赖/组合根外实例化/端口方向/判定真源）。"""
    import ast

    domain_files = [
        "src/domain/value_objects/isolation_access.py",
        "src/domain/exceptions/agent_exceptions.py",
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
    violations: dict[str, list[str]] = {
        "domain_external": [],
        "outside_root": [],
        "port_direction": [],
        "decision_source": [],
    }

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
            if target == "IsolationGuardService":
                violations["outside_root"].append(f"IsolationGuardService: {rel}")

    context["port_direction_imports"] = []
    for rel in (
        "src/application/services/isolation_guard_service.py",
        "src/application/use_cases/run_agent_workflow.py",
        "src/application/services/agent_workflow_service.py",
    ):
        tree = ast.parse((REPO_ROOT / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("src.infrastructure"):
                    violations["port_direction"].append(f"{rel}: {node.module}")
                context["port_direction_imports"].append(f"{rel}: {node.module}")

    # 判定真源防线: isolation_access 的 src/ 生产方 import 白名单（tests/ 豁免——
    # 把「矩阵唯一真源」升级为 AST 门禁，防第三处判定面绕过守卫自建异常翻译；
    # 白名单 = 守卫服务[唯一判定消费方] + 守卫端口[方法签名类型契约] +
    # value_objects/__init__[包聚合导出惯例——非判定面]）
    allowed_access_consumers = {
        "src/application/services/isolation_guard_service.py",
        "src/application/ports/isolation_guard.py",
        "src/domain/value_objects/__init__.py",
    }
    for py_file in (REPO_ROOT / "src").rglob("*.py"):
        rel = py_file.relative_to(REPO_ROOT).as_posix()
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "src.domain.value_objects.isolation_access":
                if rel not in allowed_access_consumers:
                    violations["decision_source"].append(f"isolation_access 消费方越界: {rel}")

    # 接线静态锚: 两接线文件均含 isolation_guard 引用（lambda 漏注入的架构面防线）
    for rel in (
        "src/application/use_cases/run_agent_workflow.py",
        "src/application/services/agent_workflow_service.py",
    ):
        source = (REPO_ROOT / rel).read_text(encoding="utf-8")
        if "isolation_guard" not in source:
            violations["port_direction"].append(f"{rel}: isolation_guard 接线引用缺失")

    context["arch_violations"] = violations


@then("domain 判定核心与守卫异常零外部依赖")
def then_domain_zero_external(context: dict[str, Any]) -> None:
    """AST 扫描（domain-no-external-dependencies 契约——禁 pydantic/redis）。"""
    assert not context["arch_violations"]["domain_external"], (
        f"domain 执行面文件引入外部依赖: {context['arch_violations']['domain_external']}"
    )


@then("守卫服务仅在组合根实例化")
def then_guard_only_in_composition_root(context: dict[str, Any]) -> None:
    """组装纪律（业务代码禁直接 new——对齐 5-4 验证器 B 仅扫 src 面形态）。"""
    assert not context["arch_violations"]["outside_root"], f"组合根外直接实例化: {context['arch_violations']['outside_root']}"


@then("端口方向与判定真源 import 白名单合规")
def then_port_direction_and_decision_source_legal(context: dict[str, Any]) -> None:
    """application→domain/ports 合法 + 禁 infrastructure + 判定真源单消费方。"""
    violations = context["arch_violations"]
    assert not violations["port_direction"], f"端口方向违规: {violations['port_direction']}"
    assert not violations["decision_source"], f"判定真源消费方越界: {violations['decision_source']}"
    imports_text = "\n".join(context["port_direction_imports"])
    assert "src.application.ports.isolation_guard" in imports_text, (
        "IsolationGuardService 实现应用端口 import 缺失（R2 组合注入锚）"
    )


@scenario(
    "test_acceptance_agent_triple_isolation.feature",
    "AC-6.4 - 探针套件归位集成测试范畴",
)
def test_ac_6_4_probe_suite_integration_placement(context: dict[str, Any]) -> None:
    """AC-6.4 修订（2026-10-24 用户裁定）: 探针套件归入集成范畴——专项裁撤 +
    marker 非必要不新增。"""


@given("探针套件交付形态待核验")
def given_probe_suite_placement_context(context: dict[str, Any]) -> None:
    """归位断言上下文（文件缺失即断言红）。"""
    context["probe_suite_path"] = "tests/integration/test_integration_isolation_security.py"


@then("探针套件位于集成目录且随既有 CI 挂载面运行")
def then_probe_suite_in_integration_directory(context: dict[str, Any]) -> None:
    """探针套件文件存在于 tests/integration（CI integration job pytest 路径
    `tests/integration` 天然涵盖——无需独立目录/挂载）。"""
    assert (REPO_ROOT / context["probe_suite_path"]).exists(), (
        "探针套件应位于 tests/integration/（集成范畴归位——2026-10-24 用户裁定）"
    )
    ci = (REPO_ROOT / ".gitea" / "workflows" / "ci.yaml").read_text(encoding="utf-8")
    assert "tests/integration" in ci, "CI integration job 应涵盖集成目录（探针随行）"


@then("独立安全目录与 security marker 均不存在")
def then_no_dedicated_security_infrastructure(context: dict[str, Any]) -> None:
    """专项裁撤钉子: tests/security 目录/security marker/test-security target
    均不存在（marker 非必要不新增——--strict-markers 下无注册即无声明）。"""
    assert not (REPO_ROOT / "tests" / "security").exists(), "tests/security 独立目录应裁撤"
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"security:' not in pyproject, "security marker 应不注册（非必要不新增）"
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    assert "test-security:" not in makefile, "test-security 专项 target 应裁撤"


# ===================================================================
# Task 7 收尾: 完成清单场景（src 执行面六文件 + tests 四目录——探针归集成范畴）
# ===================================================================


@scenario(
    "test_acceptance_agent_triple_isolation.feature",
    "收尾 - Story 5.5 完成清单确认",
)
def test_completion_checklist(context: dict[str, Any]) -> None:
    """收尾: 执行面源码六文件 + 测试四目录齐备（5-4 收尾同款——探针归集成）。"""


@when("检查三重隔离执行面与测试交付文件清单")
def when_check_triple_isolation_manifest(context: dict[str, Any]) -> None:
    """存在性清单断言（src 六文件——含修改件；tests 四目录关键文件——探针归集成）。"""
    src_files = [
        "src/domain/value_objects/isolation_access.py",
        "src/domain/value_objects/agent_config.py",
        "src/domain/exceptions/agent_exceptions.py",
        "src/application/ports/isolation_guard.py",
        "src/application/services/isolation_guard_service.py",
        "src/application/services/agent_workflow_service.py",
    ]
    test_files = [
        "tests/unit/domain/value_objects/test_isolation_access.py",
        "tests/unit/application/services/test_isolation_guard_service.py",
        "tests/unit/architecture/test_arch_agent_triple_isolation.py",
        "tests/contracts/test_port_contract_isolation_guard.py",
        "tests/integration/test_integration_agent_triple_isolation.py",
        "tests/integration/test_integration_isolation_security.py",
        "tests/acceptance/test_acceptance_agent_triple_isolation.feature",
        "tests/acceptance/test_acceptance_agent_triple_isolation.py",
    ]
    missing = [rel for rel in src_files + test_files if not (REPO_ROOT / rel).exists()]
    context["manifest_missing"] = missing
    context["manifest_src_count"] = len(src_files)
    context["manifest_test_count"] = len(test_files)


@then("执行面源码六文件全部存在")
def then_src_six_files_delivered(context: dict[str, Any]) -> None:
    """src 交付面完整（六文件——新建与修改件并计，见 Story File List）。"""
    assert context["manifest_src_count"] == 6
    assert not context["manifest_missing"], f"交付文件缺失: {context['manifest_missing']}"


@then("测试文件四目录齐备")
def then_test_isolation_test_assets_complete(context: dict[str, Any]) -> None:
    """unit（3 文件）/contracts（1）/integration（2——六场景 + 探针
    套件）/acceptance（2）齐备（v2.1.0 专项裁撤——无独立 security 目录）。"""
    assert context["manifest_test_count"] == 8
    assert not context["manifest_missing"], f"测试文件缺失: {context['manifest_missing']}"
