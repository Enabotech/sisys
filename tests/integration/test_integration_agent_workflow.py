"""单 Agent 工作流集成与性能测试（Story 5-3 — 真实 Redis + 真实图执行全链）

验证型集成/性能测试：被测链路已由 Task 1-6 交付，编写后直接转绿为合法
预期；断言活性由变异阶段（阈值/Fake 延迟/组装字段断供）背书。

场景：
① 全链：真实 Redis 仓储（instantiate→run-task 同 agent_id）+ 真实档案加载 +
  真实图执行 + Fake LLM（200ms/调用延迟模拟）+ 工具执行面替身边界
  （隔离约束①——真实服务链 + Fake llm 注入链内 + 沙箱执行器替身，e2e 先例
  mock SandboxExecutor 与 LLMClient 两项）→ 六阶段贯通 + 思维链 + 证据 +
  AgentDecided 事件捕获（recording publisher）
② P95：warmup 1 + 20 采样 statistics.quantiles(n=20)[18] < 10s + 计时下界
  （工作流级 4 调用 × 0.2s = 0.8s——DC-7 主口径）
③ 并发 10：asyncio.gather 10 agent_id 同时执行全链全部成功
④ 真实 LLM 冒烟：LLM_ENDPOINT + LLM_API_KEY 双 env 门控（from_env 的 model
  永非空不可作门控——恒真陷阱）动态 skip；跑通即证链路兼容不设硬阈值
⑤ 真实发布链路（R1-DF3 处置）：resolve 真实 event_publisher（DualChannelEventBus）
  + Fake LLM 执行 run-task 一次 → PG event_outbox 落行断言（按 event_type +
  payload aggregate_id 精确查询——真实发布下测试无从预知 event_id，禁全表
  计数；追加语义无清理面，PG 门控动态 skip）

发布面口径差声明（R1-DF3——场景①②③ 为内存/替身发布面（recording
publisher / InMemory），生产 CLI 路径发布经 DualChannelEventBus→PG outbox
写入（网络 RTT + 失败重试面）不在 P95 口径内——真实发布面归场景⑤单次时序
验证；完整生产口径计时（真实 LLM+真实发布 P95 采样）续期至部署验证）。

组装纪律（5-2 集成同款）：仓储 real_redis 场景级客户端手动组装；
agent_profile_loader / skill_selector 经组合根 resolve（本地静态文件只读、
无连接构造，跨循环安全）；引擎手动实例化（构造注入 workflow_service 与
recording publisher——R3-F4 注入位）；用例手动实例化（禁 resolve 用例端口
——SINGLETON redis_client 跨循环死连接）。

xdist_group("agent-workflow-perf")：计时场景与验收 AC-5 同 worker 串行化
（模块级采样缓存共享——禁 20 采样双跑）；仅保同组串行不保独占 CPU，
-n auto 下抖动超标时以 -n 0 结果为准。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/integration/test_integration_agent_workflow.py -v
"""

from __future__ import annotations

import asyncio
import statistics
import time
import uuid
from typing import Any

import pytest

from src.application.use_cases.agent_instantiation import InstantiateAgentUseCase
from src.domain.entities.agent import AgentRole
from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
from src.infrastructure.storage.redis.key_builder import build_key
from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository

pytestmark = [
    pytest.mark.integration,
    pytest.mark.redis,
    pytest.mark.benchmark,
    pytest.mark.xdist_group("agent-workflow-perf"),
]

#: Fake LLM 每调用延迟（秒）——DC-7 主口径（仓内 Fake 延迟先例 0.01-0.3s 区间内；
#: R1 耗时优化 0.2→0.05——单链 7 调用×0.05=0.35s 计时下界仍远高于噪声，判别力
#: 由「调用数锁」（scenario_2 逐轮 call_count 断言——漏 1 次即红）承载，灵敏度
#: 高于原计时下界形态（原 4d 阈值对漏 1-3 次调用本就不敏感——评审②数学推演）
FAKE_LLM_DELAY_SEC = 0.05

#: P95 计时采样缓存（模块级——集成场景②与验收 AC-5.1/5.2 共享同批结果，
#: 同 xdist_group 同 worker 串行保证缓存命中；禁 20 采样双跑）
_PERF_CACHE: dict[str, Any] = {}


class _RecordingEventPublisher:
    """记录发布事件的发布器（内存替身发布面——R3-F4 引擎构造注入位）。

    发布面口径差：本替身不触 PG outbox（真实发布面归场景⑤）；tool_version
    验收 _RecordingEventPublisher 同款形态。
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


def _make_fake_llm(
    *,
    verify_mode: str = "always_pass",
    delay_sec: float = FAKE_LLM_DELAY_SEC,
    plan_tool_names: tuple[str, ...] = ("PESTEL 分析",),
) -> Any:
    """六阶段 Fake LLM 端口替身（外部 SaaS 豁免面——隔离约束①）。

    工作流级 structured_generate 按 response_schema 身份分派（分派键与断言
    锚独立）；工具链级 generate 面（引擎 Think/Code/Validate——每工具步
    ≥2 次真实调用形态）按调用序轮转返回合法 LLMResponse（Schema 身份分派
    锚不覆盖该面——R3-F1）。

    Args:
        verify_mode: always_pass / fail_once / always_fail（序列 Fake——R2-F8）
        delay_sec: 每调用模拟延迟（工作流级与工具链级同值——DC-7 双层口径）
        plan_tool_names: 规划产出的工具步名（空 = 零工具步）
    """
    from unittest.mock import AsyncMock

    from src.application.services.agent_workflow_schemas import (
        ChainOfThoughtSchema,
        PerceptionSchema,
        PlanSchema,
        ReflectionSchema,
        VerificationSchema,
    )
    from src.domain.ports.llm_client import LLMClientPort, LLMResponse

    verify_calls = {"count": 0}
    tool_llm_calls = {"count": 0}

    async def _structured_generate(
        prompt: str, response_schema: type, config: Any = None, system_prompt: str | None = None
    ) -> Any:
        if delay_sec:
            await asyncio.sleep(delay_sec)
        if response_schema is PerceptionSchema:
            return PerceptionSchema(summary="任务摘要：新能源车进入战略分析")
        if response_schema is PlanSchema:
            from src.application.services.agent_workflow_schemas import PlanStep

            steps = [PlanStep(description=f"执行工具 {name}", tool_name=name, arguments={}) for name in plan_tool_names]
            return PlanSchema(
                steps=steps or [PlanStep(description="零工具直接推理", tool_name="", arguments={})],
                selected_tools=list(plan_tool_names),
            )
        if response_schema is VerificationSchema:
            verify_calls["count"] += 1
            if verify_mode == "always_pass":
                passed = True
            elif verify_mode == "fail_once":
                passed = verify_calls["count"] > 1
            else:
                passed = False
            return VerificationSchema(
                passed=passed,
                confidence=0.85 if passed else 0.42,
                rationale="结构化检查通过" if passed else f"第 {verify_calls['count']} 次验证未通过：约束缺失",
            )
        if response_schema is ReflectionSchema:
            return ReflectionSchema(
                error_analysis="工具输出缺少关键约束字段",
                revised_plan="补充约束参数后重新执行工具并复核",
                revised=True,
            )
        if response_schema is ChainOfThoughtSchema:
            # 回声值与真实轨迹相异（防 Fake 回声——覆写制判别力实证）
            return ChainOfThoughtSchema(
                input_summary="Fake 回声摘要（应被覆写）",
                reflection="Fake 回声反思（终局合成产物）",
                tools_used=["fake-echo:not-real"],
                constraints_check="Fake 回声约束（终局合成产物）",
                final_answer='{"answer": "三层次进入策略（终局合成）"}',
            )
        raise AssertionError(f"未预期 response_schema: {response_schema}")

    async def _generate(prompt: str, config: Any = None, system_prompt: str | None = None) -> LLMResponse:
        # 工具链 Think/Code/Validate 面（generate 非 structured）——按调用序轮转：
        # Think 分析文本 → Code Python 片段 → Validate JSON（e2e 先例计数器形态）
        if delay_sec:
            await asyncio.sleep(delay_sec)
        tool_llm_calls["count"] += 1
        stage = (tool_llm_calls["count"] - 1) % 3
        contents = (
            "1. PESTEL 六维度分析：政策支持、经济上行",
            'print("scores = [0.8, 0.7, 0.6]")',
            '{"valid": true, "confidence": 0.92, "issues": []}',
        )
        return LLMResponse(content=contents[stage], model="fake-llm")

    fake = AsyncMock(spec=LLMClientPort)
    fake.structured_generate.side_effect = _structured_generate
    fake.generate.side_effect = _generate
    return fake


def _build_tool_execution_service(fake_llm: Any) -> Any:
    """工具执行面替身边界（隔离约束①）：真实服务链 + Fake llm 注入链内 + 沙箱替身。

    e2e 先例形态（test_integration_strategic_tool_e2e.py L319-328）：
    ToolExecutionService(registry, ToolExecutionEngine(llm_client=Fake,
    sandbox=替身, retry_policy))——引擎 Think/Code/Validate 每工具步 ≥2 次
    generate 真实调用走 Fake（组合根 resolve 装配则链内 llm_client 是真实
    LitellmLLMClient 必打外网——R3-F1）。生产全装饰链（ValidationFeedback→
    SandboxSecurity→OutputValidator）依赖 PG session 上下文（SSD 的
    count_active 查询），无 PG 环境不可承载——本链为引擎层真实链，装饰层
    归 4-2/4-7 套件覆盖。
    """
    from unittest.mock import AsyncMock

    from src.application.services.retry_helpers import RetryPolicy
    from src.application.services.tool_execution_engine import ToolExecutionEngine
    from src.application.services.tool_execution_service import ToolExecutionService

    sandbox = AsyncMock()
    sandbox.start_container = AsyncMock(return_value="session-fake")
    sandbox.execute_code = AsyncMock(return_value={"status": "ok", "output": '{"P": 0.8, "E": 0.7, "S": 0.6}'})
    sandbox.stop_container = AsyncMock(return_value=None)

    engine = ToolExecutionEngine(
        llm_client=fake_llm,
        sandbox=sandbox,
        retry_policy=RetryPolicy(max_attempts=1, initial_delay_sec=0.01),
    )
    return ToolExecutionService(registry=_make_registry(), engine=engine)


async def _instantiate_agent(redis_client: Any) -> Any:
    """真实实例化 CEO Agent（Redis Agent 实体——run-task 守卫数据源）。

    第四依赖 isolation_service 用 AsyncMock(spec=IsolationManagementServicePort)
    ——集成 Mock 工厂子模式（隔离初始化非本 Story 5-3 场景断言面，归 5-4 集成）。
    """
    from unittest.mock import AsyncMock

    from src.application.ports.isolation_management import IsolationManagementServicePort

    repository = RedisAgentRepository(adapter=RedisAdapter(redis_client=redis_client))
    instantiate_use_case = InstantiateAgentUseCase(
        config_loader=_resolve("agent_config_loader"),
        repository=repository,
        event_publisher=InMemoryEventBus(),
        isolation_service=AsyncMock(spec=IsolationManagementServicePort),
    )
    return await instantiate_use_case.execute(role=AgentRole.CEO)


def _resolve(name: str) -> Any:
    from src.domain.ports.resolver import resolve

    return resolve(name)


def _make_registry() -> Any:
    """手工组装工具注册服务（InMemoryToolRepository + register_all——组合根
    resolve 的 registry 底层仓储未预载工具目录，集成链需自带数据）。"""
    from src.application.services.tool_registry_service import ToolRegistryService
    from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository

    registry = ToolRegistryService(InMemoryToolRepository())
    registry.register_all()
    return registry


def _make_guard_mock() -> Any:
    """隔离守卫 AsyncMock 替身（集成 Mock 工厂子模式——Story 5.5 双接线构造
    签名回归面；放行语义默认: ensure_agent_executable 返回 L4 策略 /
    ensure_tool_access 静默放行）。"""
    from unittest.mock import AsyncMock

    from src.application.ports.isolation_guard import IsolationGuardPort
    from src.domain.events.enums import IsolationLevel
    from src.domain.value_objects.isolation_policy import get_isolation_policy

    guard = AsyncMock(spec=IsolationGuardPort)
    guard.ensure_agent_executable.return_value = get_isolation_policy(IsolationLevel.L4_HARD)
    return guard


def _assemble_run_chain(
    redis_client: Any,
    *,
    fake_llm: Any,
    recorder: _RecordingEventPublisher,
) -> Any:
    """手动组装 run-task 全链用例（真实仓储/档案加载 + 手工引擎与工具链）。

    禁 resolve 用例端口（SINGLETON redis_client 跨循环死连接——5-2 组装纪律）。
    """
    from src.application.services.agent_workflow_service import AgentWorkflowService
    from src.application.use_cases.agent_profile_loading import LoadAgentProfileUseCase
    from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase
    from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
    from src.infrastructure.config.langgraph import LangGraphConfig

    repository = RedisAgentRepository(adapter=RedisAdapter(redis_client=redis_client))
    profile_use_case = LoadAgentProfileUseCase(
        profile_loader=_resolve("agent_profile_loader"),
        repository=repository,
        skill_selector=_resolve("skill_selector"),
        event_publisher=InMemoryEventBus(),
    )
    workflow_service = AgentWorkflowService(
        llm_client=fake_llm,
        tool_execution_service=_build_tool_execution_service(fake_llm),
        skill_loader=_resolve("skill_loader"),
        tool_registry_service=_make_registry(),
        isolation_guard=_make_guard_mock(),
    )
    engine = LangGraphEngine(
        config=LangGraphConfig.from_env(),
        event_publisher=recorder,
        workflow_service=workflow_service,
    )
    return RunAgentWorkflowUseCase(
        agent_repository=repository,
        agent_profile_use_case=profile_use_case,
        agent_engine=engine,
        agent_workflow_service=workflow_service,
        isolation_guard=_make_guard_mock(),
    )


async def _execute_workflow(use_case: Any, agent_id: Any, task: str) -> Any:
    """执行并返回结果（六阶段全链单次）。"""
    return await use_case.execute(agent_id=agent_id, task=task)


async def sample_workflow_latency(redis_client: Any) -> dict[str, Any]:
    """P95 采样 helper（warmup 1 + 20 计时——模块级缓存共享，禁双跑）。

    集成场景②与验收 AC-5.1/5.2 共享本 helper 结果（同 xdist_group 同 worker
    串行保证缓存命中）。

    Args:
        redis_client: 场景级 Redis 客户端（instantiate 真实落键）

    Returns:
        {"p95": float, "samples": list[float], "chains": list[Any]}
    """
    if "result" in _PERF_CACHE:
        cached: dict[str, Any] = _PERF_CACHE["result"]
        return cached

    samples: list[float] = []
    chains: list[Any] = []
    workflow_llm_calls: list[int] = []
    tool_llm_calls: list[int] = []
    sample_keys: list[str] = []

    async def _run_once(record_chain: bool = True) -> float:
        instantiation = await _instantiate_agent(redis_client)
        sample_keys.append(build_key("agent", str(instantiation.agent_id)))
        fake_llm = _make_fake_llm(verify_mode="always_pass", delay_sec=FAKE_LLM_DELAY_SEC)
        recorder = _RecordingEventPublisher()
        use_case = _assemble_run_chain(redis_client, fake_llm=fake_llm, recorder=recorder)
        start = time.perf_counter()
        try:
            result = await _execute_workflow(use_case, instantiation.agent_id, "分析新能源汽车行业进入战略")
            chain = result.chain
        except Exception:
            # 失败 run 计入完整率分母（chain=None——组装链判别力变异的载体：
            # 完整率 100% 非恒真的实证，Task 7 变异第三项）
            chain = None
        elapsed = time.perf_counter() - start
        if record_chain:
            chains.append(chain)
            # 调用数锁（R1 耗时优化的判别力增强）：mock 内建计数与分派键（Schema
            # 身份）独立信号——工作流级 4 次（perceive/plan/verify/终局）+ 工具
            # 链 3 次（Think/Code/Validate），漏 1 次调用即红（计时下界只对漏
            # ≥4 次敏感——降档后判别力由本锁承载）
            workflow_llm_calls.append(fake_llm.structured_generate.call_count)
            tool_llm_calls.append(fake_llm.generate.call_count)
        return elapsed

    await _run_once(record_chain=False)  # warmup（剔除——计时与完整率分母均不含）
    for _ in range(20):
        samples.append(await _run_once())

    # teardown：采样键精确清理（同场景隔离纪律）
    if sample_keys:
        await redis_client.delete(*sample_keys)

    result = {
        "p95": statistics.quantiles(samples, n=20)[18],
        "samples": samples,
        "chains": chains,
        "workflow_llm_calls": workflow_llm_calls,
        "tool_llm_calls": tool_llm_calls,
    }
    _PERF_CACHE["result"] = result
    return result


# ===================================================================
# 场景①：全链（真实 Redis + 真实档案 + 真实图 + Fake LLM + 工具链替身）
# ===================================================================


@pytest.mark.asyncio
async def test_scenario_1_full_chain_six_phases(real_redis: Any) -> None:
    """场景①：instantiate→run-task 同 agent_id 全链贯通（AgentDecided 捕获）。"""
    instantiation = await _instantiate_agent(real_redis)
    agent_id = instantiation.agent_id
    try:
        fake_llm = _make_fake_llm(verify_mode="always_pass")
        recorder = _RecordingEventPublisher()
        use_case = _assemble_run_chain(real_redis, fake_llm=fake_llm, recorder=recorder)

        result = await _execute_workflow(use_case, agent_id, "分析新能源汽车行业进入战略")

        # 六阶段贯通（AC-1）
        assert result.executed_phases == ("perceive", "plan", "execute", "verify", "package")
        assert result.workflow_status == "completed"
        # 思维链（AC-2——覆写制：Fake 回声值被覆写）
        assert result.chain.input_summary == "任务摘要：新能源车进入战略分析"
        assert "fake-echo" not in "".join(result.chain.tools_used)
        assert result.chain.tools_used, "工具步任务应产生真实轨迹"
        # 证据（AC-3——六类字段）
        assert len(result.evidence.input_hash) == 64
        assert result.evidence.confidence == 0.85
        # AgentDecided 捕获（agent_id 贯通 + confidence 真实化 + 五键投影）
        decided = [e for e in recorder.published_events if type(e).__name__ == "AgentDecided"]
        assert decided, "应发布 AgentDecided"
        assert decided[0].agent_id == agent_id
        assert decided[0].confidence == 0.85
        assert "workflow_status" in decided[0].decision_result
    finally:
        await real_redis.delete(build_key("agent", str(agent_id)))


# ===================================================================
# 场景②：P95 性能（共享采样 helper）
# ===================================================================


@pytest.mark.asyncio
async def test_scenario_2_p95_under_10_seconds(real_redis: Any) -> None:
    """场景②：P95 < 10s + 计时下界（同源派生）+ 调用数锁（漏 1 次调用即红）。"""
    result = await sample_workflow_latency(real_redis)

    assert len(result["samples"]) == 20, "采样数 20（warmup 已剔除）"
    assert result["p95"] < 10.0, f"P95 {result['p95']:.2f}s >= 10s（NFR-PERF-04 MVP 档）"
    # 计时下界（同源派生——延迟档位调整不破锚）：工作流级 4 次调用（perceive/
    # plan/verify/终局）× FAKE_LLM_DELAY_SEC（+ 工具链 generate 面 3 次同延迟，
    # 实际下界 7×delay 更高，4×delay 为保守锚）
    lower_bound = 4 * FAKE_LLM_DELAY_SEC
    assert result["p95"] >= lower_bound, f"P95 {result['p95']:.2f}s 低于 Fake 延迟下界（计时未含全链）"
    # 调用数锁：20 轮采样每轮调用计数精确锁定（漏任一调用即红——判别力主承载）
    assert set(result["workflow_llm_calls"]) == {4}, (
        f"每链工作流级 LLM 调用应恰 4 次（perceive/plan/verify/终局），实际 {result['workflow_llm_calls']}"
    )
    assert set(result["tool_llm_calls"]) == {3}, (
        f"每链工具链 LLM 调用应恰 3 次（Think/Code/Validate），实际 {result['tool_llm_calls']}"
    )


# ===================================================================
# 场景③：并发 10 会话
# ===================================================================


@pytest.mark.asyncio
async def test_scenario_3_concurrent_ten_sessions(real_redis: Any) -> None:
    """场景③：asyncio.gather 10 agent_id 并发全链全部成功（单进程并发先例）。"""
    agent_ids: list[Any] = []
    try:
        instantiations = [await _instantiate_agent(real_redis) for _ in range(10)]
        agent_ids = [inst.agent_id for inst in instantiations]

        async def _run_session(agent_id: Any) -> Any:
            fake_llm = _make_fake_llm(verify_mode="always_pass", delay_sec=0.05)
            recorder = _RecordingEventPublisher()
            use_case = _assemble_run_chain(real_redis, fake_llm=fake_llm, recorder=recorder)
            return await _execute_workflow(use_case, agent_id, "并发任务")

        results = list(await asyncio.gather(*(_run_session(aid) for aid in agent_ids)))
        assert len(results) == 10
        for item in results:
            assert item.workflow_status == "completed"
            assert item.executed_phases[-1] == "package"
            assert item.chain is not None and item.evidence is not None
    finally:
        for agent_id in agent_ids:
            await real_redis.delete(build_key("agent", str(agent_id)))


# ===================================================================
# 场景④：真实 LLM 冒烟（配置真源探测动态 skip——恒真/恒假双陷阱防线）
# ===================================================================


@pytest.mark.asyncio
async def test_scenario_4_real_llm_smoke(real_redis: Any) -> None:
    """场景④：真实 LLM 全链冒烟（跑通即证链路兼容不设硬阈值——外部 SaaS
    延迟不可控）。

    门控经 build_default_llm_config 真源探测（endpoint+api_key 齐备才执行）：
    - 禁 LLMConfig.from_env 的 model 恒真门控（model 默认 qwen2.5:7b 永非空）
    - 禁裸读 LLM_ENDPOINT/LLM_API_KEY 双 env（UDMR SSOT 云端配置不经这两个
      变量名——恒假跳过，UDMR 已配 GLM-5.3 环境实测踩中）；真源探测对两种
      配置形态（LLM_* env / UDMR_CLOUD_*）统一生效
    """
    from src.infrastructure.config.llm import build_default_llm_config

    llm_config = build_default_llm_config()
    if not (llm_config.endpoint and llm_config.api_key):
        pytest.skip(
            f"真实 LLM 未配置（build_default_llm_config 无 endpoint/api_key——"
            f"LLM_* env 与 UDMR 云端配置均缺席，model={llm_config.model}）"
        )

    from src.domain.ports.llm_client import LLMClientPort

    instantiation = await _instantiate_agent(real_redis)
    agent_id = instantiation.agent_id
    try:
        real_llm = _resolve("llm_client")
        assert isinstance(real_llm, LLMClientPort)
        recorder = _RecordingEventPublisher()
        # base_config 注入生产配置（组合根同款——温度分档完整派生不丢连接字段）；
        # per_call_timeout 放宽 60s（云端 SaaS RTT+生成时间——8s 生产预算针对
        # Fake 延迟口径，真实冒烟单次链路不设硬阈值但仍禁继承 600s 默认）
        from src.application.services.agent_workflow_service import AgentWorkflowService

        workflow_service = AgentWorkflowService(
            llm_client=real_llm,
            tool_execution_service=_build_tool_execution_service(real_llm),
            skill_loader=_resolve("skill_loader"),
            tool_registry_service=_make_registry(),
            isolation_guard=_make_guard_mock(),
            base_config=llm_config,
            per_call_timeout_sec=60.0,
        )
        from src.application.use_cases.agent_profile_loading import LoadAgentProfileUseCase
        from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase
        from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
        from src.infrastructure.config.langgraph import LangGraphConfig

        repository = RedisAgentRepository(adapter=RedisAdapter(redis_client=real_redis))
        profile_use_case = LoadAgentProfileUseCase(
            profile_loader=_resolve("agent_profile_loader"),
            repository=repository,
            skill_selector=_resolve("skill_selector"),
            event_publisher=InMemoryEventBus(),
        )
        engine = LangGraphEngine(
            config=LangGraphConfig.from_env(),
            event_publisher=recorder,
            workflow_service=workflow_service,
        )
        use_case = RunAgentWorkflowUseCase(
            agent_repository=repository,
            agent_profile_use_case=profile_use_case,
            agent_engine=engine,
            agent_workflow_service=workflow_service,
            isolation_guard=_make_guard_mock(),
        )

        result = await _execute_workflow(use_case, agent_id, "用一句话概括 SWOT 分析的用途")
        # 真实 LLM 产出不可精确断言——链路走通 + 终态产物形态即冒烟通过
        assert result.executed_phases[-1] == "package"
        assert result.chain.final_answer.strip()
    except Exception as exc:
        # 已知服务端缺陷形态豁免（外部 SaaS 不可控——冒烟语义是「证链路兼容」
        # 而非「证服务端无缺陷」）：GLM-5.3 anthropic 兼容端点（open.bigmodel.cn）
        # 对嵌套 JSON Schema（PlanSchema 的 list[PlanStep]——pydantic v2 合法
        # Schema）服务端 500 StackOverflowError（扁平 Schema 实测正常，链路
        # 兼容性已被 PerceptionSchema/ChainOfThoughtSchema 真实调用证明）。
        # 服务端修复或 UDMR 切 openai 兼容端点后本场景自动恢复全链冒烟。
        # 444 包装异常的 str 仅含默认消息——服务端细节在 cause 链上，需遍历。
        cause_texts: list[str] = []
        current: BaseException | None = exc
        seen: set[int] = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            cause_texts.append(str(current))
            current = current.__cause__
        full_text = " ".join(cause_texts).lower()
        # 豁免匹配收窄（R1-F12）：精确服务端缺陷特征串——原裸子串 "500"/"internal"
        # 会误吞 "1500ms" 超时/InternalError 任何来源等非目标异常
        if "stackoverflowerror" in full_text or "overloaded" in full_text:
            pytest.skip(
                f"真实 LLM 端点服务端缺陷（嵌套 Schema 栈溢出——GLM-5.3 anthropic 兼容端点已知限制）: {cause_texts[-1][:160]}"
            )
        raise
    finally:
        await real_redis.delete(build_key("agent", str(agent_id)))


# ===================================================================
# 场景⑤：真实发布链路（R1-DF3 处置——PG outbox 落行）
# ===================================================================


@pytest.mark.asyncio
async def test_scenario_5_real_publish_outbox_row(real_redis: Any) -> None:
    """场景⑤：resolve 真实 event_publisher 执行一次 → PG event_outbox 落行断言。

    按event_type + payload.aggregate_id(=agent_id) 精确查询（真实发布下测试
    无从预知 event_id——禁全表计数）；outbox 追加语义无清理面（生产提交独立
    于测试事务）。PG 门控动态 skip。
    """
    from sqlalchemy import text

    from src.infrastructure.config.postgresql import PostgreSQLConfig
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
    from tests.environments import get_test_env

    env_pg = get_test_env().postgres
    try:
        manager = PostgreSQLManager(
            PostgreSQLConfig(
                host=env_pg.host,
                port=env_pg.port,
                database=env_pg.database,
                username=env_pg.username,
                password=env_pg.password,
            )
        )
    except Exception as exc:  # PG 配置缺失
        pytest.skip(f"PostgreSQL 不可用: {exc}")

    # 连接级 + schema 级双预检（R5-DF1 核销——5-4 R7-F01 同款：manager 构造
    # 零 IO 拦不住「服务缺席/空 schema」，任一形态下发布 INSERT 被 DC-10 容错
    # 吞 warning 后查询裸红；预检直探目标表存在性统一 skip）
    from sqlalchemy import text as _sa_text
    from sqlalchemy.ext.asyncio import AsyncSession as _AsyncSession

    try:
        async with _AsyncSession(manager.get_async_engine()) as probe_session:
            await probe_session.execute(_sa_text("SELECT event_id FROM event_outbox LIMIT 1"))
    except Exception as exc:
        await manager.get_async_engine().dispose()
        pytest.skip(f"PostgreSQL 不可达或 event_outbox 表未初始化: {exc}")

    instantiation = await _instantiate_agent(real_redis)
    agent_id = instantiation.agent_id
    try:
        # 真实发布面：引擎构造注入生产 DualChannelEventBus（resolve 真实端口）
        # SINGLETON publisher 跨测试 loop 死连接防线（R7-F02 同款——组合跑中
        # 先行场景的 resolve 实例持旧 loop 连接，本测试发布必失败；resolve 前
        # 清 SINGLETON 取新建实例绑定当前测试 loop，构造零 IO 重建安全）
        from src.domain.ports.resolver import get_resolver

        get_resolver().clear_singleton()
        real_publisher = _resolve("event_publisher")
        from src.application.services.agent_workflow_service import AgentWorkflowService
        from src.application.use_cases.agent_profile_loading import LoadAgentProfileUseCase
        from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase
        from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
        from src.infrastructure.config.langgraph import LangGraphConfig

        repository = RedisAgentRepository(adapter=RedisAdapter(redis_client=real_redis))
        profile_use_case = LoadAgentProfileUseCase(
            profile_loader=_resolve("agent_profile_loader"),
            repository=repository,
            skill_selector=_resolve("skill_selector"),
            event_publisher=InMemoryEventBus(),
        )
        fake_llm = _make_fake_llm(verify_mode="always_pass", delay_sec=0.0)
        workflow_service = AgentWorkflowService(
            llm_client=fake_llm,
            tool_execution_service=_build_tool_execution_service(fake_llm),
            skill_loader=_resolve("skill_loader"),
            tool_registry_service=_make_registry(),
            isolation_guard=_make_guard_mock(),
        )
        engine = LangGraphEngine(
            config=LangGraphConfig.from_env(),
            event_publisher=real_publisher,
            workflow_service=workflow_service,
        )
        use_case = RunAgentWorkflowUseCase(
            agent_repository=repository,
            agent_profile_use_case=profile_use_case,
            agent_engine=engine,
            agent_workflow_service=workflow_service,
            isolation_guard=_make_guard_mock(),
        )

        result = await _execute_workflow(use_case, agent_id, "真实发布链路验证任务")
        assert result.executed_phases[-1] == "package"

        # PG outbox 落行断言（独立 session 读已提交行——测试事务不覆盖生产提交）
        from sqlalchemy.ext.asyncio import AsyncSession

        async with AsyncSession(manager.get_async_engine(), expire_on_commit=False) as session:
            query = text(
                "SELECT event_id, event_type, status FROM event_outbox "
                "WHERE event_type = 'AgentDecided' AND payload->>'aggregate_id' = :agent_id "
                "ORDER BY created_at DESC LIMIT 1"
            )
            row = (await session.execute(query, {"agent_id": str(agent_id)})).fetchone()
        assert row is not None, f"event_outbox 未落 AgentDecided 行（agent_id={agent_id}——真实发布链路断裂）"
        assert row[0] is not None  # event_id
        assert row[1] == "AgentDecided"
    finally:
        await real_redis.delete(build_key("agent", str(agent_id)))
