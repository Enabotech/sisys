"""Story 5.5 集成测试 — 三重隔离全链 + 性能三指标（真实 Redis 6380）。

六场景:
① 守卫矩阵真实链抽查（A/B 构造 → 三面断言[448×4 + 449×1 + 放行×1] +
   ensure_tool_access 三路[放行/L3 共享池放行/共享面矩阵]）
② P95: ensure_agent_executable 服务全链计时（warmup 1 + 20 采样
   quantiles[18] < TRIPLE_ISOLATION_P95_LIMIT_SECONDS——委托缓存 helper 与
   验收 AC-5.1/5.2 共享，禁 20 采样双跑）
③ 通过率: 20 轮连续检查全放行（分子分母显式 20/20——与缓存共享同批）
④ 并发 10×50: 10 Agent 并发构造 + 每 Agent 50 跨 Agent 穿透探针（gather
   return_exceptions 逐条分类 + actor 等级互异[奇 L4 偶 L3] + 448 reason
   等级名下钻——并发状态串扰即 reason 错配可检测 + 拦截率 500/500）
⑤ 入口 fail-closed 真实链: 真实 RunAgentWorkflowUseCase（guard 真实 + Fake
   LLM 隔离）→ 删隔离键 → execute 抛 447 先于档案加载
⑥ execute 白名单 449 真实拒: 真实 AgentWorkflowService（guard 真实 + 窄白名单
   loader）+ A 真实 instantiate + plan 白名单外工具步骤 → 449 且注册表零调用

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/integration/test_integration_agent_triple_isolation.py -v

测试隔离:
    - 真实 Redis 6380 门控 ping 失败 skip；手动组装全链（场景级客户端）
    - keys 即时登记 + finally 批量双键删除 + exists 复核（禁 delete_pattern/flush）
    - 计时组 xdist_group("agent-triple-isolation-perf")——与验收侧同组
      同 worker 串行保证 _TRIPLE_PERF_CACHE 缓存命中
"""

from __future__ import annotations

import asyncio
import shutil
import statistics
import time
import uuid
from pathlib import Path
from typing import Any

import pytest
import yaml as yaml_lib

from src.domain.events.enums import IsolationLevel
from src.infrastructure.storage.redis.key_builder import build_key

pytestmark = [
    pytest.mark.integration,
    pytest.mark.redis,
    pytest.mark.benchmark,
    pytest.mark.xdist_group("agent-triple-isolation-perf"),
]

# P95 阈值同源派生常量（一处定义——验收侧 import 本常量断言，禁双真源；
# epics L1653 隔离检查 P95<50ms——本地 Redis 两读 ~2ms 预算 25 倍裕量）
TRIPLE_ISOLATION_P95_LIMIT_SECONDS = 0.05

# 采样规格（warmup 1 + 20 采样——与 5-4 PERF_* 常量同款形态）
TRIPLE_PERF_WARMUP_ROUNDS = 1
TRIPLE_PERF_SAMPLE_ROUNDS = 20

#: P95/通过率采样缓存（模块级单槽——集成场景②③与验收 AC-5.1/5.2 共享同批
#: 结果，同 xdist_group 同 worker 串行保证缓存命中；禁 20 采样双跑拖慢套件）
_TRIPLE_PERF_CACHE: dict[str, Any] = {}

REPO_ROOT = Path(__file__).resolve().parents[2]


# ===================================================================
# 组装基建（手动组装——场景级客户端禁 resolve 发命令）
# ===================================================================


class _RecordingEventPublisher:
    """事件发布端口记录替身（基础设施豁免面——非被测面）。"""

    def __init__(self) -> None:
        self.published_events: list[Any] = []

    async def publish(self, event: Any) -> Any:
        from src.domain.events.publish_result import ChannelResult, PublishResult

        self.published_events.append(event)
        return PublishResult(
            event_id=str(uuid.uuid4()),
            results=(ChannelResult(channel_name="inmemory", success=True),),
        )


def _assemble_chain(redis_client: Any, config_loader: Any = None) -> dict[str, Any]:
    """手动组装守卫真实链（guard + isolation_service + instantiate 用例 + 双仓储）。"""
    from unittest.mock import AsyncMock

    from src.application.services.isolation_guard_service import IsolationGuardService
    from src.application.services.isolation_management_service import IsolationManagementService
    from src.application.use_cases.agent_instantiation import InstantiateAgentUseCase
    from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogRepository
    from src.domain.ports.resolver import resolve
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository
    from src.infrastructure.storage.redis.redis_isolation_repository import RedisIsolationRepository

    effective_loader = config_loader if config_loader is not None else resolve("agent_config_loader")
    agent_repository = RedisAgentRepository(adapter=RedisAdapter(redis_client=redis_client))
    isolation_repository = RedisIsolationRepository(adapter=RedisAdapter(redis_client=redis_client))
    recorder = _RecordingEventPublisher()
    isolation_service = IsolationManagementService(
        isolation_repository=isolation_repository,
        agent_repository=agent_repository,
        event_publisher=recorder,
        agent_config_loader=effective_loader,
        # Story 5.6 五/六依赖：5-5 回归面断言锚是三重隔离判定——日志仓储以
        # AsyncMock(spec=端口) 替身注入（真实 PG 日志链归 5.6 集成文件）
        isolation_switch_log_repository=AsyncMock(spec=IsolationSwitchLogRepository),
        audit_service=None,
    )
    guard = IsolationGuardService(
        isolation_management_service=isolation_service,
        agent_repository=agent_repository,
        agent_config_loader=effective_loader,
    )
    instantiate_use_case = InstantiateAgentUseCase(
        config_loader=effective_loader,
        repository=agent_repository,
        event_publisher=InMemoryEventBus(),
        isolation_service=isolation_service,
    )
    return {
        "guard": guard,
        "isolation_service": isolation_service,
        "instantiate_use_case": instantiate_use_case,
        "agent_repository": agent_repository,
        "recorder": recorder,
    }


def _make_narrow_loader(tmp_path: Any, allowlist: tuple[str, ...]) -> Any:
    """配置篡改: ceo_agent.yaml 复制 tmp 收窄 allowed_tools（5-4 AC-2.3 先例）。"""
    from src.infrastructure.agent_orch.yaml_agent_config_loader import YamlAgentConfigLoader

    source = REPO_ROOT / "configs" / "agents" / "ceo_agent.yaml"
    data = yaml_lib.safe_load(source.read_text(encoding="utf-8"))
    data["eip_config"]["allowed_tools"] = list(allowlist)
    target = tmp_path / "ceo_agent.yaml"
    target.write_text(yaml_lib.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    shutil.copystat(source, target)
    return YamlAgentConfigLoader(config_dir=tmp_path)


def _make_registry() -> Any:
    """手工组装工具注册服务（InMemoryToolRepository + register_all——5-3 集成先例）。"""
    from src.application.services.tool_registry_service import ToolRegistryService
    from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository

    registry = ToolRegistryService(InMemoryToolRepository())
    registry.register_all()
    return registry


def _agent_keys(agent_id: uuid.UUID) -> list[str]:
    """构造 agent/isolation 双键（登记与删除共用——键形态单源）。"""
    return [build_key("agent", str(agent_id)), build_key("isolation", str(agent_id))]


# ===================================================================
# 委托计时 helper（验收 AC-5.1/5.2 共享——单槽缓存禁双跑）
# ===================================================================


async def sample_triple_isolation_perf(redis_client: Any) -> dict[str, Any]:
    """P95/通过率采样（warmup 1 + 20 采样——单槽缓存命中即返）。

    计时锚 = ensure_agent_executable 服务全链（get_isolation_state[443 守卫 +
    隔离态读真实 Redis] + 策略联查——工程回归锚非统计置信断言）；通过率分子 =
    每轮 initialize + ensure 全放行。采样键双键登记 + try/finally 删除置
    finally（中途异常零残留——优于 5-4 裸 delete 形态）。
    """
    if "result" in _TRIPLE_PERF_CACHE:
        cached: dict[str, Any] = _TRIPLE_PERF_CACHE["result"]
        return cached

    from src.domain.entities.agent import AgentRole

    chain = _assemble_chain(redis_client)
    latencies: list[float] = []
    success_count = 0
    sample_agent_ids: list[uuid.UUID] = []

    async def _one_round(record: bool) -> float:
        nonlocal success_count
        instantiation = await chain["instantiate_use_case"].execute(role=AgentRole.CEO)
        sample_agent_ids.append(instantiation.agent_id)
        started = time.perf_counter()
        policy = await chain["guard"].ensure_agent_executable(instantiation.agent_id)
        elapsed = time.perf_counter() - started
        if record and policy.tool_isolation is True:  # L4 策略三维度之 tool 隔离锚
            success_count += 1
        return elapsed

    try:
        for _ in range(TRIPLE_PERF_WARMUP_ROUNDS):
            await _one_round(record=False)  # warmup: 计时与通过率分母均不含
        for _ in range(TRIPLE_PERF_SAMPLE_ROUNDS):
            latencies.append(await _one_round(record=True))
    finally:
        if sample_agent_ids:  # 采样键精确清理（异常路径也清——零残留）
            keys: list[str] = []
            for agent_id in sample_agent_ids:
                keys.extend(_agent_keys(agent_id))
            await redis_client.delete(*keys)

    result: dict[str, Any] = {
        "p95_seconds": statistics.quantiles(latencies, n=TRIPLE_PERF_SAMPLE_ROUNDS)[18],
        "success_count": success_count,
        "total_count": TRIPLE_PERF_SAMPLE_ROUNDS,
        "samples": latencies,
    }
    _TRIPLE_PERF_CACHE["result"] = result
    return result


# ===================================================================
# 场景① 守卫矩阵真实链抽查
# ===================================================================


class TestGuardMatrixRealChain:
    """场景①: A/B 构造 + 三面断言（448×4 + 449×1 + 放行×1）+ 工具三路。"""

    async def test_guard_matrix_three_faces(self, real_redis: Any) -> None:
        """三面抽查: Prompt 面 448 / 数据面 448×4 / 共享面 L4 写 449 + 读放行 +
        工具三路（宽白名单放行 / L3 共享池放行[切 B 到 L3]）。"""
        from src.domain.entities.agent import AgentRole
        from src.domain.exceptions import IsolationAccessViolationError, IsolationOperationForbiddenError
        from src.domain.value_objects.isolation_access import AccessOperation, IsolationResource

        chain = _assemble_chain(real_redis)
        keys: list[str] = []
        try:
            instantiation_a = await chain["instantiate_use_case"].execute(role=AgentRole.CEO)
            instantiation_b = await chain["instantiate_use_case"].execute(role=AgentRole.CEO)
            for inst in (instantiation_a, instantiation_b):
                keys.extend(_agent_keys(inst.agent_id))
            actor, target = instantiation_a.agent_id, instantiation_b.agent_id
            guard = chain["guard"]

            # Prompt 面 448（PROFILE READ 跨 Agent）
            with pytest.raises(IsolationAccessViolationError) as prompt_exc:
                await guard.ensure_agent_access(actor, target, IsolationResource.PROFILE, AccessOperation.READ)
            assert prompt_exc.value.code == "EXCEPTION_448"
            assert prompt_exc.value.context["actor_agent_id"] == str(actor)

            # 数据面 448×4（AGENT_STATE 读写 + MEMORY 读写）
            for resource in (IsolationResource.AGENT_STATE, IsolationResource.MEMORY):
                for operation in (AccessOperation.READ, AccessOperation.WRITE):
                    with pytest.raises(IsolationAccessViolationError):
                        await guard.ensure_agent_access(actor, target, resource, operation)

            # 共享面: BLACKBOARD READ 放行 / L4 WRITE 449
            await guard.ensure_agent_access(actor, target, IsolationResource.BLACKBOARD, AccessOperation.READ)
            with pytest.raises(IsolationOperationForbiddenError) as shared_exc:
                await guard.ensure_agent_access(actor, target, IsolationResource.BLACKBOARD, AccessOperation.WRITE)
            assert shared_exc.value.code == "EXCEPTION_449"
            assert shared_exc.value.context["reason"] == "data_isolation:read_only"

            # 工具三路: 生产宽白名单内放行 / L3 共享池放行（切 B 到 L3——任意名放行）
            await guard.ensure_tool_access(actor, "PESTEL 分析")
            await chain["isolation_service"].switch_isolation_level(target, IsolationLevel.L3_SOFT, "集成-共享池")
            await guard.ensure_tool_access(target, "任意工具名")
        finally:
            if keys:
                await real_redis.delete(*keys)
        for key in keys:
            assert not await real_redis.exists(key), f"场景①键未清理: {key}"


# ===================================================================
# 场景②③ P95 + 通过率（委托缓存——验收共享）
# ===================================================================


class TestPerformanceMetrics:
    """场景②③: P95 < 50ms + 通过率 20/20（单批采样双断言）。"""

    async def test_p95_under_50ms(self, real_redis: Any) -> None:
        """P95 计时锚 = ensure_agent_executable 全链（含 443 守卫 + 真实 Redis 读）。"""
        result = await sample_triple_isolation_perf(real_redis)
        p95_ms = result["p95_seconds"] * 1000
        assert result["p95_seconds"] < TRIPLE_ISOLATION_P95_LIMIT_SECONDS, (
            f"隔离检查 P95={p95_ms:.1f}ms 超阈值 {TRIPLE_ISOLATION_P95_LIMIT_SECONDS * 1000:.0f}ms"
        )

    async def test_pass_rate_20_of_20(self, real_redis: Any) -> None:
        """通过率 20/20（分子分母显式——与 P95 同批缓存共享）。"""
        result = await sample_triple_isolation_perf(real_redis)
        assert result["total_count"] == TRIPLE_PERF_SAMPLE_ROUNDS
        assert result["success_count"] == TRIPLE_PERF_SAMPLE_ROUNDS, (
            f"通过率 {result['success_count']}/{result['total_count']} 应全放行"
        )


# ===================================================================
# 场景④ 并发 10×50（actor 等级互异 + reason 下钻 + 500/500）
# ===================================================================


class TestConcurrent10x50Probes:
    """场景④: 10 Agent 并发 × 50 探针零泄露（epics L1655）。"""

    async def test_concurrent_probes_500_of_500_intercepted(self, real_redis: Any) -> None:
        """并发穿透: gather[return_exceptions] 逐条分类 + actor 等级互异
        （奇 L4 偶 L3——448 reason 含 policy.name 随 actor 等级互异，串扰即
        reason 错配可检测）+ 拦截率 500/500 + keys 即时登记 finally 批删。"""
        from src.domain.entities.agent import AgentRole
        from src.domain.exceptions import IsolationAccessViolationError
        from src.domain.value_objects.isolation_access import AccessOperation, IsolationResource

        chain = _assemble_chain(real_redis)
        keys: list[str] = []  # key 即时登记（gather 部分失败时已完成写键仍可清理）

        target_instantiation = await chain["instantiate_use_case"].execute(role=AgentRole.CEO)
        keys.extend(_agent_keys(target_instantiation.agent_id))
        target_id = target_instantiation.agent_id

        async def _one_probe_actor(index: int) -> list[tuple[str, Any]]:
            instantiation = await chain["instantiate_use_case"].execute(role=AgentRole.CEO)
            keys.extend(_agent_keys(instantiation.agent_id))
            actor_id = instantiation.agent_id
            level_name = "硬隔离"
            if index % 2 == 0:  # 偶数 actor 切 L3——奇 L4 偶 L3 等级互异
                await chain["isolation_service"].switch_isolation_level(actor_id, IsolationLevel.L3_SOFT, f"并发互异-{index}")
                level_name = "软隔离"
            outcomes: list[tuple[str, Any]] = []
            for _ in range(50):
                try:
                    await chain["guard"].ensure_agent_access(
                        actor_id, target_id, IsolationResource.PROFILE, AccessOperation.READ
                    )
                    outcomes.append((level_name, None))
                except Exception as exc:  # 探针预期异常逐条收集（448 分类计数形态）
                    outcomes.append((level_name, exc))
            return outcomes

        try:
            gathered = await asyncio.gather(*(_one_probe_actor(i) for i in range(10)), return_exceptions=True)
            outcomes: list[tuple[str, Any]] = []
            for actor_outcomes in gathered:  # isinstance 显式收窄（return_exceptions 联合类型）
                assert not isinstance(actor_outcomes, BaseException), f"并发构造异常: {actor_outcomes}"
                outcomes.extend(actor_outcomes)
        finally:
            if keys:
                await real_redis.delete(*keys)

        assert len(outcomes) == 500
        blocked = 0
        for level_name, outcome in outcomes:
            assert isinstance(outcome, IsolationAccessViolationError), f"探针应 448 拦截（{level_name}）: {outcome!r}"
            assert outcome.code == "EXCEPTION_448"
            assert level_name in outcome.context["reason"], (
                f"448 reason 等级名错配（期望 {level_name}）: {outcome.context['reason']!r}"
            )
            blocked += 1
        assert blocked == 500, f"拦截率 {blocked}/500 应全拦截"
        for key in keys:
            assert not await real_redis.exists(key), f"并发场景键未清理: {key}"


# ===================================================================
# 场景⑤ 入口 fail-closed 真实链
# ===================================================================


class TestEntryFailClosedRealChain:
    """场景⑤: 真实 RunAgentWorkflowUseCase（guard 真实）→ 删隔离键 → 447。"""

    async def test_entry_447_after_isolation_key_deleted(self, real_redis: Any) -> None:
        """入口 fail-closed: 真实装配入口链（Fake LLM 是外部 SaaS 豁免替身——
        447 在档案加载前抛出，LLM 不触达）→ 删隔离键 → execute 抛 447。"""
        from unittest.mock import AsyncMock

        from src.application.services.agent_workflow_service import AgentWorkflowService
        from src.application.use_cases.agent_profile_loading import LoadAgentProfileUseCase
        from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase
        from src.domain.entities.agent import AgentRole
        from src.domain.exceptions import IsolationStateNotInitializedError
        from src.domain.ports.llm_client import LLMClientPort
        from src.domain.ports.resolver import resolve
        from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
        from src.infrastructure.config.langgraph import LangGraphConfig
        from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus

        chain = _assemble_chain(real_redis)
        instantiation = await chain["instantiate_use_case"].execute(role=AgentRole.CEO)
        agent_id = instantiation.agent_id
        keys = _agent_keys(agent_id)
        try:
            workflow_service = AgentWorkflowService(
                llm_client=AsyncMock(spec=LLMClientPort),
                tool_execution_service=AsyncMock(),
                skill_loader=resolve("skill_loader"),
                tool_registry_service=_make_registry(),
                isolation_guard=chain["guard"],
            )
            profile_use_case = LoadAgentProfileUseCase(
                profile_loader=resolve("agent_profile_loader"),
                repository=chain["agent_repository"],
                skill_selector=resolve("skill_selector"),
                event_publisher=InMemoryEventBus(),
            )
            engine = LangGraphEngine(
                config=LangGraphConfig.from_env(),
                event_publisher=InMemoryEventBus(),
                workflow_service=workflow_service,
            )
            use_case = RunAgentWorkflowUseCase(
                agent_repository=chain["agent_repository"],
                agent_profile_use_case=profile_use_case,
                agent_engine=engine,
                agent_workflow_service=workflow_service,
                isolation_guard=chain["guard"],
            )

            # fail-closed 验证: 删隔离键 → 447（guard 在档案加载前抛——LLM/档案零触达）
            await real_redis.delete(build_key("isolation", str(agent_id)))
            with pytest.raises(IsolationStateNotInitializedError) as exc_info:
                await use_case.execute(agent_id=agent_id, task="验证入口 fail-closed")
            assert exc_info.value.code == "EXCEPTION_447"
            assert exc_info.value.context["agent_id"] == str(agent_id)
        finally:
            if keys:
                await real_redis.delete(*keys)


# ===================================================================
# 场景⑥ execute 白名单 449 真实拒
# ===================================================================


class TestExecuteWhitelistReal449:
    """场景⑥: 真实 AgentWorkflowService（窄白名单 loader）+ A 真实 instantiate
    + plan 白名单外工具步骤 → 449 且注册表零调用。"""

    async def test_execute_preflight_449_real_rejection(self, real_redis: Any, tmp_path: Any) -> None:
        """A 须真实 instantiate（guard 先经 443/447 守卫序——不在案得 443 非 449；
        state.agent_id 用 A 真实 id）。"""
        from unittest.mock import AsyncMock, Mock

        from src.application.ports.agent_workflow import PlanResult, WorkflowContext
        from src.application.services.agent_workflow_service import AgentWorkflowService
        from src.domain.entities.agent import AgentRole
        from src.domain.exceptions import IsolationOperationForbiddenError
        from src.domain.ports.llm_client import LLMClientPort
        from src.domain.ports.resolver import resolve

        narrow_allowlist = ("PESTEL 分析",)
        narrow_loader = _make_narrow_loader(tmp_path, narrow_allowlist)
        narrow_config = await narrow_loader.load(AgentRole.CEO)
        assert narrow_config.allowed_tools == narrow_allowlist, "窄配置基线锚失败"

        chain = _assemble_chain(real_redis, config_loader=narrow_loader)
        instantiation = await chain["instantiate_use_case"].execute(role=AgentRole.CEO)
        agent_id = instantiation.agent_id
        keys = _agent_keys(agent_id)
        try:
            registry = Mock()
            workflow_service = AgentWorkflowService(
                llm_client=AsyncMock(spec=LLMClientPort),
                tool_execution_service=AsyncMock(),
                skill_loader=resolve("skill_loader"),
                tool_registry_service=registry,
                isolation_guard=chain["guard"],
            )
            context = WorkflowContext(
                system_prompt="## 身份档案（IDENTITY）\n\nCEO",
                tools_l1=(),
                task="窄白名单验证任务",
                tenant_id=uuid.uuid4(),
                assembled_context_tokens=10,
            )
            state: dict[str, Any] = {
                "agent_id": str(agent_id),
                "task": "窄白名单验证任务",
                "context": context,
                "plan": PlanResult(
                    steps=(
                        ("合法步骤", "PESTEL 分析", {}),
                        ("越权步骤", "GE-麦肯锡矩阵", {}),
                    )
                ),
            }

            with pytest.raises(IsolationOperationForbiddenError) as exc_info:
                await workflow_service.execute(state)
            assert exc_info.value.code == "EXCEPTION_449"
            assert exc_info.value.context["reason"] == "tool_not_in_allowlist:GE-麦肯锡矩阵"
            assert registry.get_tool.call_count == 0, "449 须先于 get_tool（注册表零调用）"
        finally:
            if keys:
                await real_redis.delete(*keys)
        for key in keys:
            assert not await real_redis.exists(key), f"场景⑥键未清理: {key}"
