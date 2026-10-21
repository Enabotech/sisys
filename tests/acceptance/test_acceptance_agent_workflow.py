"""Story 5-3 — 单 Agent 标准工作流验收测试（BDD 场景步骤实现）。

结构范本：test_acceptance_agent_profile_loading.py（5-2 最新形态——FEATURE 常量 +
@scenario 显式绑定 + context dict + 场景级独立 Redis 客户端 + _run_async 同循环调度）；
AST 静态扫描写法参照 test_acceptance_postgresql_relational_layer.py（架构约束归
tests/unit/architecture/test_arch_agent_workflow.py）。

18 场景三属性分档表（Task 0 Subtask 0.6 定稿——层级/LLM 依赖/Redis 依赖）：

| #  | 场景     | 层级                     | LLM      | Redis  |
|----|----------|--------------------------|----------|--------|
| 1  | AC-1.1   | 端口级（手工装配图+服务） | Fake     | 无     |
| 2  | AC-1.2   | 端口级                   | Fake 序列 | 无     |
| 3  | AC-1.3   | 端口级                   | Fake 序列 | 无     |
| 4  | AC-1.4   | 端口级                   | Fake     | 无     |
| 5  | AC-2.1   | 端口级                   | Fake     | 无     |
| 6  | AC-2.2   | VO 级                    | 无       | 无     |
| 7  | AC-3.1   | 端口级                   | Fake     | 无     |
| 8  | AC-3.2   | 端口级                   | Fake 序列 | 无     |
| 9  | AC-4.1   | Schema 级                | 无       | 无     |
| 10 | AC-4.2   | Schema 级                | 无       | 无     |
| 11 | AC-4.3   | Schema 级                | 无       | 无     |
| 12 | AC-5.1   | 端口级（benchmark 标记）  | Fake 延迟 | 无     |
| 13 | AC-5.2   | 端口级（复用 5.1 采样）  | Fake     | 无     |
| 14 | AC-5.3   | 端口级                   | Fake     | 无     |
| 15 | AC-6.3   | 用例级（进程内 main）    | Fake 覆写 | 真实   |
| 16 | AC-6.1   | resolve 级               | 不触     | 无     |
| 17 | AC-6.2   | 端口级                   | Fake     | 无     |
| 18 | AC-6.4   | 静态完成清单（Task 9）   | 无       | 无     |

场景序约束（DC-12）：AC-6.3 CLI 覆写场景先于 AC-6.1 接线场景执行（接线场景
resolve 即缓存全真实链，后行 CLI 覆写失效）——绑定函数定义序 AC-6.3 在前，
feature 文本序保持 AC 编号序。

新模块延迟 import 纪律：本 Story 交付的模块（agent_workflow 端口 / 六阶段服务 /
schemas / prompts / context 装配器 / 图工厂 / 引擎扩展 / use_case / 444-445 异常 /
SAP message）一律在步骤函数体内延迟 import——模块顶部 import 会使 pytest 收集期
整文件 collection error，已实现/未实现场景一起炸，无法逐 Task 转绿。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/acceptance/test_acceptance_agent_workflow.py -v

测试隔离:
    - 端口级场景不触 Redis（档案加载走本地静态文件 loader；图执行手工装配
      LangGraphEngine + InMemoryEventBus 子类 recording publisher——R3-F4 注入位）
    - 仅 AC-6.3 需要真实 Redis（instantiate 落 Agent 实体 + run-task 守卫 get_by_id）
    - teardown 逐键精确删除本场景记录的 agent_id 键（禁 delete_pattern/flush）
    - 场景级独立 Redis 客户端 + 同循环关闭（跨循环 "Event loop is closed" 存档教训）
    - BDD 步骤禁 @pytest.mark.asyncio（context 数据丢失），统一 _run_async 调度
    - 验收禁调用 bootstrap()（session 级 _bootstrap_once 已引导，二次调用因
      lambda 工厂 spec 不幂等必抛 ConflictError）
    - Fake LLM 端口替身是外部 SaaS 豁免面（分派键 = response_schema 身份，断言锚
      与分派键独立——4-5 纪律）；工具链 generate 面按 prompt 前缀分派
    - AC-5.1/5.2 共享计时 helper（模块级采样缓存——禁 20 采样双跑拖慢套件）
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from collections.abc import Coroutine, Generator
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenario, then, when

from src.domain.entities.agent import AgentRole
from src.infrastructure.storage.redis.key_builder import build_key

FEATURE = "test_acceptance_agent_workflow.feature"

# 仓库根锚定（完成清单断言用，不依赖 cwd）
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# 文件名不含服务关键词，acceptance conftest 不会自动添加 marker——显式声明；
# xdist_group("agent-workflow-perf") 与集成性能场景同组——同 worker 串行化计时
# 场景并共享模块级采样缓存（禁 20 采样双跑）；AC-5.1/5.2 另挂场景级 benchmark
# 标记（R1-F8 裁定不打文件级）
pytestmark = [
    pytest.mark.acceptance,
    pytest.mark.redis,
    pytest.mark.xdist_group("agent-workflow-perf"),
]

# AC-5.1/5.2 共享计时采样缓存（xdist_group 保证同 worker 串行——AC-5.1 先行产出）
_PERF_SAMPLES: dict[str, Any] = {}


# ===================================================================
# 场景绑定（17 个，场景名从 .feature 复制粘贴——ASCII 连字符 + 两侧空格）
# 注意：AC-6.3 先于 AC-6.1/AC-6.2 定义（DC-12 场景序约束）
# ===================================================================


@scenario(FEATURE, "AC-1.1 - 六阶段标准工作流顺序执行")
def test_ac_1_1_six_phase_sequential_execution(context: dict[str, Any]) -> None:
    """AC-1.1: executed_phases 轨迹六阶段完备 + 每阶段产物入 state。"""


@scenario(FEATURE, "AC-1.2 - 验证失败进入反思且修正后重试与不可修正早退")
def test_ac_1_2_reflect_retry_and_early_exit(context: dict[str, Any]) -> None:
    """AC-1.2: fail→reflect→revised→plan 重试成功 + revised=False 早退两路径。"""


@scenario(FEATURE, "AC-1.3 - 重试上限耗尽带失败标记完成")
def test_ac_1_3_retry_exhausted_failed_completion(context: dict[str, Any]) -> None:
    """AC-1.3: plan 总执行 ≤3 次 + status=failed 完成态。"""


@scenario(FEATURE, "AC-1.4 - agent_id 全链贯通无新铸")
def test_ac_1_4_agent_id_threading(context: dict[str, Any]) -> None:
    """AC-1.4: AgentDecided.agent_id == parameters 传入值（5-2 风险 #2 核销）。"""


@scenario(FEATURE, "AC-2.1 - 思维链五字段完备且工具轨迹一致")
def test_ac_2_1_chain_five_fields_and_tool_trace(context: dict[str, Any]) -> None:
    """AC-2.1: 五字段非空 + tools_used 与真实工具轨迹一致（覆写制）。"""


@scenario(FEATURE, "AC-2.2 - 思维链展示形态含 XML 标签与 JSON 尾段")
def test_ac_2_2_chain_display_form(context: dict[str, Any]) -> None:
    """AC-2.2: to_display 五段形态 + 三个 XML 标签段 + JSON 尾段。"""


@scenario(FEATURE, "AC-3.1 - 证据包六类字段齐备")
def test_ac_3_1_evidence_six_field_classes(context: dict[str, Any]) -> None:
    """AC-3.1: 六类字段齐备 + input_hash sha256 64 位 hex + 置信度溯源。"""


@scenario(FEATURE, "AC-3.2 - 失败终态产出全量轨迹证据包")
def test_ac_3_2_failed_terminal_full_trace(context: dict[str, Any]) -> None:
    """AC-3.2: 跨重试轮全部工具轨迹 + 末次验证失败摘要。"""


@scenario(FEATURE, "AC-4.1 - SAP 消息十五字段定义完整")
def test_ac_4_1_sap_fifteen_fields(context: dict[str, Any]) -> None:
    """AC-4.1: 15 字段存在性与类型 + 10 必需字段逐一点名（验收 tripwire）。"""


@scenario(FEATURE, "AC-4.2 - SAP 枚举值与默认值契约")
def test_ac_4_2_sap_enums_and_defaults(context: dict[str, Any]) -> None:
    """AC-4.2: 5 类型/4 优先级 + 四默认值（NORMAL/L4_HARD/False/300）。"""


@scenario(FEATURE, "AC-4.3 - SAP 必填约束与非法值拒绝")
def test_ac_4_3_sap_required_and_rejection(context: dict[str, Any]) -> None:
    """AC-4.3: conversation_id 必填 + correlation_id 可空 + 非法枚举拒绝 + UTC。"""


@pytest.mark.benchmark  # 性能场景级标记（R1-F8——不打文件级以防非计时场景误挂语义）
@scenario(FEATURE, "AC-5.1 - 工作流执行延迟 P95 小于 10 秒")
def test_ac_5_1_p95_under_10s(context: dict[str, Any]) -> None:
    """AC-5.1: warmup 1 + 20 采样 quantiles(n=20)[18] < 10s（Fake 延迟注入）。"""


@scenario(FEATURE, "AC-5.2 - 思维链输出完整率不低于 98%")
def test_ac_5_2_chain_completeness_rate(context: dict[str, Any]) -> None:
    """AC-5.2: 复用 AC-5.1 采样统计五字段完备占比 ≥98%。"""


@scenario(FEATURE, "AC-5.3 - 并发 10 个 Agent 会话全部成功")
def test_ac_5_3_concurrent_ten_sessions(context: dict[str, Any]) -> None:
    """AC-5.3: asyncio.gather 10 agent_id 并发全成功（单进程并发先例）。"""


# --- DC-12 场景序约束：AC-6.3 CLI 覆写场景先于 AC-6.1 接线场景执行 ---


@scenario(FEATURE, "AC-6.3 - CLI run-task 全链贯通")
def test_ac_6_3_cli_run_task_full_chain(context: dict[str, Any]) -> None:
    """AC-6.3: DC-12 四件套——成功 exit 0/失败完成态 exit 0/守卫 443 exit 1。"""


@scenario(FEATURE, "AC-6.1 - 端口接线与图注册可达")
def test_ac_6_1_port_wiring_and_graph_registration(context: dict[str, Any]) -> None:
    """AC-6.1: 两新端口 resolve+isinstance + SingleAgentWorkflow 图名注册。"""


@scenario(FEATURE, "AC-6.2 - AgentDecided 事件真实化发布")
def test_ac_6_2_agent_decided_realized(context: dict[str, Any]) -> None:
    """AC-6.2: decision_result 五键投影 + confidence 来自验证阶段（非 0.9）。"""


@scenario(FEATURE, "AC-6.4 - 完成清单逐项确认")
def test_ac_6_4_completion_checklist(context: dict[str, Any]) -> None:
    """AC-6.4: src/tests 完成清单 + 链路接线断言清单终态（Task 9 收尾）。"""


# ===================================================================
# 共享基建：context fixture + _run_async + Fake LLM/装配 helper
# ===================================================================


@pytest.fixture
def context(
    event_loop: asyncio.AbstractEventLoop,
    acceptance_env_config: Any,
) -> Generator[dict[str, Any], None, None]:
    """BDD 步骤间共享状态容器（场景级独立 Redis 客户端 + 同循环 teardown 关闭）。

    Redis 客户端必须场景级独立创建：session 客户端的连接池持有前一场景已关闭
    事件循环的连接，跨场景复用会抛 RuntimeError "Event loop is closed"（存档
    教训）。teardown 仅精确删除本场景记录的 agent_id 对应键；无需 Redis 的
    端口级场景不触发任何 Redis 命令（客户端仅在 teardown 关闭，空连零副作用）。
    """
    import redis.asyncio as aioredis

    redis_client = aioredis.Redis(
        host=acceptance_env_config.redis.host,
        port=acceptance_env_config.redis.port,
        password=acceptance_env_config.redis.password,
        decode_responses=True,
    )
    ctx: dict[str, Any] = {
        "_tenant": uuid.uuid4(),
        "_loop": event_loop,
        "_redis_client": redis_client,
        "_agent_ids": [],
        "_restorers": [],
    }
    yield ctx

    # teardown: 先恢复端口覆写（AC-6.3 场景注册的 Fake spec 还原真实链），
    # 再逐键精确删除本场景创建的 Agent 状态键 + 同循环关闭客户端
    for restore in ctx["_restorers"]:
        restore()
    for agent_id in ctx["_agent_ids"]:
        _run_async(event_loop, redis_client.delete(build_key("agent", str(agent_id))))
    _run_async(event_loop, redis_client.close())


def _run_async(event_loop: asyncio.AbstractEventLoop, coro: Coroutine[Any, Any, Any]) -> Any:
    """在场景级共享事件循环上同步调度协程。

    BDD 步骤函数禁止 @pytest.mark.asyncio（context 数据丢失）；
    aioredis/asyncio.Lock 等对象在首次使用时绑定事件循环，
    必须复用同一循环，否则抛 "Event loop is closed" 跨循环错误。
    """
    return event_loop.run_until_complete(coro)


class _RecordingEventBus:
    """记录发布事件的发布器（事件捕获锚点——R3-F4 引擎构造注入位）。

    手写发布器实现 EventPublisher 协议（publish 返回 PublishResult），
    记录全部发布事件供场景断言——tool_version 验收 _RecordingEventPublisher
    同款形态（4-6/4-7 先例）；发布面口径差（内存替身 vs 生产 outbox）随
    模块 docstring 声明（R1-DF3——真实发布链路归集成场景⑤）。
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
    reflect_revised: bool = True,
    delay_sec: float = 0.0,
    plan_tool_names: tuple[str, ...] = (),
) -> Any:
    """六阶段 Fake LLM 端口替身（外部 SaaS 豁免面——分派键与断言锚独立）。

    分派键 = response_schema 身份（六阶段 Schema 两两不同是前提）；verify 序列
    模式经 verify_mode 控制（always_pass / fail_once / always_fail）——序列 Fake
    形态（R2-F8）。终局 ChainOfThoughtSchema 分支返回与真实轨迹【相异】的
    tools_used 值（防 Fake 回声——覆写制断言判别力实证，R3-F8）。

    Args:
        verify_mode: 验证阶段行为——always_pass / fail_once（先失败一次后通过）/
            always_fail（恒失败——重试耗尽与失败终态场景）
        reflect_revised: 反思阶段是否产出修正计划（False = 不可修正早退路径）
        delay_sec: 每调用模拟延迟（秒）——AC-5.1 计时下界注入
        plan_tool_names: 规划阶段产出的工具步名（空 = 零工具步任务）

    Returns:
        AsyncMock(spec=LLMClientPort) 替身
    """
    from unittest.mock import AsyncMock

    from src.application.services.agent_workflow_schemas import (
        ChainOfThoughtSchema,
        PerceptionSchema,
        PlanSchema,
        PlanStep,
        ReflectionSchema,
        VerificationSchema,
    )
    from src.domain.ports.llm_client import LLMClientPort, LLMResponse

    verify_calls = {"count": 0}

    async def _structured_generate(
        prompt: str, response_schema: type, config: Any = None, system_prompt: str | None = None
    ) -> Any:
        if delay_sec:
            await asyncio.sleep(delay_sec)
        if response_schema is PerceptionSchema:
            return PerceptionSchema(summary=f"任务摘要：{prompt[:60]}")
        if response_schema is PlanSchema:
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
                error_analysis="验证失败根因：工具输出缺少关键约束字段",
                revised_plan="补充约束参数后重新执行工具并复核",
                revised=reflect_revised,
            )
        if response_schema is ChainOfThoughtSchema:
            # 相异值防 Fake 回声：tools_used 故意返回与真实轨迹不同的值——
            # 覆写制下终局产物仍等于真实轨迹（DC-2 判别力实证）
            return ChainOfThoughtSchema(
                input_summary="Fake 回声摘要（应被 perceive 产物覆写）",
                reflection="Fake 回声反思（应被终局合成覆写）",
                tools_used=["fake-echo:not-a-real-tool"],
                constraints_check="Fake 回声约束（应被覆写）",
                final_answer="Fake 综合答案（终局合成产物）",
            )
        raise AssertionError(f"未知 response_schema: {response_schema!r}")

    async def _generate(prompt: str, config: Any = None, system_prompt: str | None = None) -> LLMResponse:
        # 工具链 Think/Code/Validate 面（generate 非 structured）——按调用序返回合法内容
        if delay_sec:
            await asyncio.sleep(delay_sec)
        return LLMResponse(content='{"valid": true, "confidence": 0.9}', model="fake-llm")

    fake = AsyncMock(spec=LLMClientPort)
    fake.structured_generate.side_effect = _structured_generate
    fake.generate.side_effect = _generate
    return fake


def _assemble_workflow(context: dict[str, Any], **fake_kwargs: Any) -> None:
    """端口级手工装配六阶段全链（真实档案加载 + 真实图执行 + Fake LLM 替身）。

    装配面（全部真实组件，LLM 是唯一豁免替身）：
    - 档案加载：resolve("agent_profile_loader")（本地静态文件只读、无连接构造
      跨循环安全）→ 真实 AgentProfile；tools_l1 经真实 skill_selector
    - 六阶段服务：AgentWorkflowService 手动实例化（Fake LLM + 真实工具执行链 +
      skill_loader + tool_registry_service 构造注入——R2 组合端口）
    - 图执行：LangGraphEngine 手动构造（workflow_service 注入 + recording
      publisher——R3-F4 引擎构造注入位实证）
    """
    from src.application.services.agent_workflow_service import AgentWorkflowService
    from src.domain.ports.resolver import resolve
    from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
    from src.infrastructure.config.langgraph import LangGraphConfig

    loop = context["_loop"]

    # 真实档案加载（本地静态文件——无 Redis 依赖，uuid4 随机锚点）
    context["agent_id"] = uuid.uuid4()
    profile_loader = resolve("agent_profile_loader")
    profile = _run_async(loop, profile_loader.load(role=AgentRole.CEO, agent_id=context["agent_id"]))
    skill_selector = resolve("skill_selector")
    tools_l1 = _run_async(loop, skill_selector.list_active_skills())

    from src.application.use_cases.agent_profile_loading import AgentProfileLoadResult

    profile_result = AgentProfileLoadResult(
        agent_id=context["agent_id"],
        role=AgentRole.CEO,
        profile=profile,
        tools_l1=tools_l1,
        startup_context_tokens=0,
    )

    fake_llm = _make_fake_llm(**fake_kwargs)
    context["fake_llm"] = fake_llm
    tool_execution_service = _build_tool_execution_service(fake_llm)

    service = AgentWorkflowService(
        llm_client=fake_llm,
        tool_execution_service=tool_execution_service,
        skill_loader=resolve("skill_loader"),
        tool_registry_service=_make_registry(),
    )
    context["service"] = service

    context["task"] = "分析新能源汽车行业进入战略并给出三层次建议"
    workflow_context = service.build_context(profile_result, context["task"])
    context["workflow_context"] = workflow_context

    recorder = _RecordingEventBus()
    context["recorder"] = recorder
    context["engine"] = LangGraphEngine(
        config=LangGraphConfig.from_env(),
        event_publisher=recorder,
        workflow_service=service,
    )


def _make_registry() -> Any:
    """手工组装工具注册服务（InMemoryToolRepository + register_all——组合根
    resolve 的 registry 底层仓储未预载工具目录，集成/验收链需自带数据）。"""
    from src.application.services.tool_registry_service import ToolRegistryService
    from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository

    registry = ToolRegistryService(InMemoryToolRepository())
    registry.register_all()
    return registry


def _build_tool_execution_service(fake_llm: Any) -> Any:
    """工具执行面替身边界（隔离约束①）：真实服务链 + Fake llm 注入链内 + 沙箱替身。

    e2e 先例（test_integration_strategic_tool_e2e.py L319-328）：ToolExecutionService(
    registry, ToolExecutionEngine(llm_client=Fake, sandbox=替身, retry_policy))——
    引擎 Think/Code/Validate 每工具步 ≥2 次 generate 真实调用走 Fake（组合根
    resolve 装配则链内 llm_client 是真实 LitellmLLMClient 必打外网——R3-F1）。
    """
    from unittest.mock import AsyncMock

    from src.application.services.retry_helpers import RetryPolicy
    from src.application.services.tool_execution_engine import ToolExecutionEngine
    from src.application.services.tool_execution_service import ToolExecutionService
    from src.application.services.tool_registry_service import ToolRegistryService
    from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository

    registry = ToolRegistryService(InMemoryToolRepository())
    registry.register_all()

    sandbox = AsyncMock()
    sandbox.start_container = AsyncMock(return_value="session-fake")
    sandbox.execute_code = AsyncMock(return_value={"status": "ok", "output": '{"result": "分析完成"}'})
    sandbox.stop_container = AsyncMock(return_value=None)

    engine = ToolExecutionEngine(
        llm_client=fake_llm,
        sandbox=sandbox,
        retry_policy=RetryPolicy(max_attempts=1, initial_delay_sec=0.01),
    )
    return ToolExecutionService(registry=registry, engine=engine)


def _submit_workflow(context: dict[str, Any]) -> None:
    """以指定 agent_id 提交 SingleAgentWorkflow 图执行（阻塞语义——返回即终态）。"""
    parameters = {
        "agent_id": str(context["agent_id"]),
        "task": context["task"],
        "context": context["workflow_context"],
    }
    run_id = _run_async(
        context["_loop"],
        context["engine"].submit_graph("SingleAgentWorkflow", parameters=parameters),
    )
    context["run_id"] = run_id
    context["final_state"] = _run_async(context["_loop"], context["engine"].get_graph_result(run_id))


# ===================================================================
# Given 步骤
# ===================================================================


@given("Redis 缓存服务可用")
def given_redis_service_available(context: dict[str, Any]) -> None:
    """验证 Redis 服务可用（不可用时场景整体动态跳过，禁止写死 skip）。"""
    try:
        _run_async(context["_loop"], context["_redis_client"].ping())
    except Exception as exc:
        pytest.skip(f"Redis not available: {exc}")


@given("六阶段工作流组件已装配且 Fake LLM 验证恒通过")
def given_workflow_assembled_always_pass(context: dict[str, Any]) -> None:
    """装配六阶段全链（Fake LLM verify 恒 pass——成功路径基准形态）。"""
    _assemble_workflow(context, verify_mode="always_pass")


@given("六阶段工作流组件已装配且 Fake LLM 验证先失败后通过")
def given_workflow_assembled_fail_once(context: dict[str, Any]) -> None:
    """装配六阶段全链（序列 Fake：verify 第 1 次 fail、第 2 次 pass——反思重试闭环）。"""
    _assemble_workflow(context, verify_mode="fail_once", plan_tool_names=("PESTEL 分析",))


@given("六阶段工作流组件已装配且 Fake LLM 验证恒失败且反思恒可修正")
def given_workflow_assembled_always_fail(context: dict[str, Any]) -> None:
    """装配六阶段全链（verify 恒 fail + reflect 恒 revised=True——重试耗尽路径）。"""
    _assemble_workflow(context, verify_mode="always_fail", reflect_revised=True, plan_tool_names=("PESTEL 分析",))


@given("六阶段工作流组件已装配且 Fake LLM 反思判定不可修正")
def given_workflow_assembled_not_revisable(context: dict[str, Any]) -> None:
    """装配六阶段全链（reflect revised=False——第四路径不可修正早退）。"""
    _assemble_workflow(context, verify_mode="always_fail", reflect_revised=False, plan_tool_names=("PESTEL 分析",))


@given("已构造含工具轨迹的思维链值对象")
def given_chain_of_thought_vo(context: dict[str, Any]) -> None:
    """构造 ChainOfThought VO 实例（VO 级场景——to_display 展示形态断言）。"""
    from src.domain.value_objects.chain_of_thought import ChainOfThought

    context["chain_vo"] = ChainOfThought(
        input_summary="输入摘要：分析新能源汽车行业进入战略",
        reflection="反思：分析覆盖了政策、经济与技术三维度",
        tools_used=("pestel:v1.2.0",),
        constraints_check="约束检查：符合 MVP 范围与安全红线",
        final_answer=json.dumps({"answer": "建议采用三层次进入策略"}, ensure_ascii=False),
    )


@given("已实例化 CEO Agent 且 CLI 已覆写 Fake LLM 端口")
def given_cli_env_with_fake_llm_overridden(context: dict[str, Any]) -> None:
    """DC-12 测试序四件套前置：真实 instantiate + Fake LLM 端口覆写。

    ⓪ clear_singleton() 实例缓存驱逐（resolver unregister 不驱逐 _instances——
    不先清缓存则覆写后 resolve 仍返回缓存真实实例静默失效）
    ① bootstrap 已由 conftest _bootstrap_once session 级承载（场景内禁自调）
    ② unregister("llm_client") + register_port(Fake LLM spec) 两步覆写
    （同名异 spec 直接 register 抛 ConflictError）
    ③ 场景内 main(["run-task", ...])（handler 内 bootstrap 幂等守卫）

    teardown 恢复：重新 register 真实 llm_client spec + clear_singleton 驱逐
    Fake 缓存实例（后续场景 AC-6.1 接线 resolve 全真实链）。
    """
    from src.application.use_cases.agent_instantiation import InstantiateAgentUseCase
    from src.domain.ports.llm_client import LLMClientPort
    from src.domain.ports.registry import (
        Lifetime,
        PortSpec,
        _global_registry,
    )
    from src.domain.ports.resolver import get_resolver, resolve
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository

    loop = context["_loop"]

    # ⓪ 实例缓存全清（唯一公开驱逐 API——旧池不关的泄漏权衡，惰性重建）
    get_resolver().clear_singleton()

    # 真实 instantiate（Redis Agent 实体——run-task 守卫 get_by_id 数据源）
    repository = RedisAgentRepository(adapter=RedisAdapter(redis_client=context["_redis_client"]))
    instantiate_use_case = InstantiateAgentUseCase(
        config_loader=resolve("agent_config_loader"),
        repository=repository,
        event_publisher=InMemoryEventBus(),
    )
    instantiation = _run_async(loop, instantiate_use_case.execute(role=AgentRole.CEO))
    context["_agent_ids"].append(instantiation.agent_id)
    context["agent_id"] = instantiation.agent_id

    # ② 两步覆写：unregister 真实 llm_client → register Fake spec
    real_spec = _global_registry.get("llm_client")
    assert real_spec is not None, "真实 llm_client spec 应已由 bootstrap 注册（conftest _bootstrap_once）"
    context["_real_llm_spec"] = real_spec
    _global_registry.unregister("llm_client")

    fake_llm = _make_fake_llm(verify_mode="always_pass")
    context["cli_fake_llm"] = fake_llm

    _global_registry.register(
        PortSpec(
            name="llm_client",
            version=real_spec.version,
            interface=LLMClientPort,
            impl=lambda resolver: fake_llm,
            module="tests.acceptance.test_acceptance_agent_workflow",
            lifetime=Lifetime.SINGLETON,
            owner="platform",
            tags=("llm", "fake"),
        )
    )

    def _restore_llm_port() -> None:
        """teardown：恢复真实 llm_client spec + 驱逐 Fake 缓存实例。"""
        _global_registry.unregister("llm_client")
        if real_spec is not None:
            _global_registry.register(real_spec)
        get_resolver().clear_singleton()

    context["_restorers"].append(_restore_llm_port)


# ===================================================================
# When 步骤
# ===================================================================


@when("以指定 agent_id 执行单 Agent 工作流任务")
def when_execute_workflow_task(context: dict[str, Any]) -> None:
    """提交 SingleAgentWorkflow（阻塞语义）+ 取终态 state（get_graph_result）。"""
    _submit_workflow(context)


@when("采样执行工作流全链 1 次 warmup 与 20 次计时")
def when_sample_workflow_latency(context: dict[str, Any]) -> None:
    """P95 采样：warmup 1 次 + 计时 20 次（statistics.quantiles(n=20)[18]——5-2 先例）。

    共享计时 helper（Task 7 交付）：委托集成测试模块的 sample_workflow_latency
    ——模块级采样缓存使集成场景②与验收 AC-5.1/5.2 共享同批结果（禁 20 采样
    双跑拖慢套件）；同 xdist_group("agent-workflow-perf") 同 worker 串行保证
    缓存命中。
    """
    # 采样链 instantiate 需真实 Redis（键落库）——门控复用 given 步骤的 ping 形态
    try:
        _run_async(context["_loop"], context["_redis_client"].ping())
    except Exception as exc:
        pytest.skip(f"Redis not available（采样链 instantiate 前置）: {exc}")

    # 计时链完全由集成 helper 自建（逐轮 Fake 装配 + 延迟注入）——验收侧
    # 不再做本地装配（原装配产物零消费且不进计时窗——R1 耗时优化 F11）
    from tests.integration.test_integration_agent_workflow import sample_workflow_latency

    result = _run_async(context["_loop"], sample_workflow_latency(context["_redis_client"]))
    context["perf_samples"] = result["samples"]
    context["perf_chains"] = result["chains"]
    _PERF_SAMPLES["latencies"] = result["samples"]
    _PERF_SAMPLES["chains"] = result["chains"]
    context["p95"] = result["p95"]


@when("复用性能采样结果统计思维链完整率")
def when_compute_chain_completeness(context: dict[str, Any]) -> None:
    """从共享采样缓存统计五字段完备占比（AC-5.2——与 AC-5.1 同批结果）。"""
    if "chains" not in _PERF_SAMPLES:
        pytest.skip("AC-5.1 采样未执行（Redis 缺席级联跳过——完整率无分母）")
    chains = _PERF_SAMPLES["chains"]
    total = len(chains)

    def _complete(chain: Any) -> bool:
        if chain is None:
            return False
        non_str_fields = ("input_summary", "reflection", "constraints_check", "final_answer")
        for name in non_str_fields:
            value = getattr(chain, name, "")
            if not isinstance(value, str) or not value.strip():
                return False
        tools = getattr(chain, "tools_used", None)
        return isinstance(tools, tuple)

    context["completeness_total"] = total
    context["completeness_complete"] = sum(1 for chain in chains if _complete(chain))


@when("以 10 个不同 agent_id 并发执行工作流任务")
def when_concurrent_ten_sessions(context: dict[str, Any]) -> None:
    """asyncio.gather 10 个 agent_id 并发全链（单进程并发先例）。"""

    async def _run_session(agent_id: uuid.UUID) -> dict[str, Any]:
        from src.domain.ports.resolver import resolve

        profile_loader = resolve("agent_profile_loader")
        profile = await profile_loader.load(role=AgentRole.CEO, agent_id=agent_id)
        skill_selector = resolve("skill_selector")
        tools_l1 = await skill_selector.list_active_skills()

        from src.application.use_cases.agent_profile_loading import AgentProfileLoadResult

        profile_result = AgentProfileLoadResult(
            agent_id=agent_id,
            role=AgentRole.CEO,
            profile=profile,
            tools_l1=tools_l1,
            startup_context_tokens=0,
        )

        fake_llm = _make_fake_llm(verify_mode="always_pass")
        tool_execution_service = _build_tool_execution_service(fake_llm)

        from src.application.services.agent_workflow_service import AgentWorkflowService

        service = AgentWorkflowService(
            llm_client=fake_llm,
            tool_execution_service=tool_execution_service,
            skill_loader=resolve("skill_loader"),
            tool_registry_service=_make_registry(),
        )
        recorder = _RecordingEventBus()
        from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
        from src.infrastructure.config.langgraph import LangGraphConfig

        engine = LangGraphEngine(config=LangGraphConfig.from_env(), event_publisher=recorder, workflow_service=service)
        workflow_context = service.build_context(profile_result, context["task"])
        parameters = {"agent_id": str(agent_id), "task": context["task"], "context": workflow_context}
        run_id = await engine.submit_graph("SingleAgentWorkflow", parameters=parameters)
        state = await engine.get_graph_result(run_id)
        return {"agent_id": agent_id, "state": state}

    async def _gather_all() -> list[dict[str, Any]]:
        import asyncio as aio

        agent_ids = [uuid.uuid4() for _ in range(10)]
        return list(await aio.gather(*(_run_session(aid) for aid in agent_ids)))

    context["concurrent_results"] = _run_async(context["_loop"], _gather_all())


@when("执行 CLI run-task 成功路径")
def when_cli_run_task_success(context: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    """进程内 main(["run-task"]) 成功路径（DC-12 四件套第③步）。

    输出在 when 步骤内捕获存 context（多 when/then 交替场景——readouterr
    消费性读取需与产出同步）。
    """
    from src.entrypoints.agent_cli import main

    context["cli_exit_code"] = main(
        [
            "run-task",
            "--agent-id",
            str(context["agent_id"]),
            "--task",
            "分析新能源汽车行业进入战略并给出三层次建议",
        ]
    )
    context["cli_captured"] = capsys.readouterr()


@when("执行 CLI run-task 验证恒失败路径")
def when_cli_run_task_failed_completion(context: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    """失败完成态路径：覆写 Fake 为 verify 恒 fail——工作流正常走完 status=failed。"""
    from src.domain.ports.llm_client import LLMClientPort
    from src.domain.ports.registry import Lifetime, PortSpec, _global_registry
    from src.domain.ports.resolver import get_resolver

    get_resolver().clear_singleton()
    _global_registry.unregister("llm_client")

    real_spec = context["_real_llm_spec"]
    fake_llm = _make_fake_llm(verify_mode="always_fail", reflect_revised=True)
    _global_registry.register(
        PortSpec(
            name="llm_client",
            version=real_spec.version,
            interface=LLMClientPort,
            impl=lambda resolver: fake_llm,
            module="tests.acceptance.test_acceptance_agent_workflow",
            lifetime=Lifetime.SINGLETON,
            owner="platform",
            tags=("llm", "fake"),
        )
    )

    from src.entrypoints.agent_cli import main

    context["cli_exit_code"] = main(
        [
            "run-task",
            "--agent-id",
            str(context["agent_id"]),
            "--task",
            "分析新能源汽车行业进入战略并给出三层次建议",
        ]
    )
    context["cli_captured"] = capsys.readouterr()


@when("以不存在的 agent_id 执行 CLI run-task")
def when_cli_run_task_agent_not_found(context: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    """守卫路径：随机 agent_id → 443 退出码 1 + stderr 编码断言。

    第三次进程内 main() 前 clear_singleton 驱逐缓存实例——前两次 main() 的
    asyncio.run 各自新建循环，SINGLETON repository 的 Redis 客户端绑定已关
    循环（跨循环 "Event loop is closed"——clear 后惰性重建新循环连接）。
    """
    from src.domain.ports.resolver import get_resolver
    from src.entrypoints.agent_cli import main

    # 双清：SINGLETON（redis_adapter/manager 链）+ SCOPED（agent_repository——
    # clear_singleton 不覆盖 SCOPED 缓存，跨循环死连接正是 SCOPED 实例持有）
    get_resolver().clear_singleton()
    get_resolver().clear_scoped()
    context["cli_missing_agent_id"] = uuid.uuid4()
    context["cli_exit_code"] = main(
        [
            "run-task",
            "--agent-id",
            str(context["cli_missing_agent_id"]),
            "--task",
            "任意任务",
        ]
    )
    context["cli_captured"] = capsys.readouterr()


# ===================================================================
# Then 步骤
# ===================================================================


@then("executed_phases 轨迹按六阶段顺序完备且末段为 package")
def then_executed_phases_complete(context: dict[str, Any]) -> None:
    """六阶段轨迹断言（成功路径：perceive→plan→execute→verify→package）。"""
    state = context["final_state"]
    phases = state["executed_phases"]
    assert phases == ["perceive", "plan", "execute", "verify", "package"], f"轨迹异常: {phases}"
    assert phases[-1] == "package", "末元素钉死 package（对齐 444 phase 枚举）"


@then("每阶段产物已写入工作流状态")
def then_phase_artifacts_in_state(context: dict[str, Any]) -> None:
    """各阶段产物键非空断言（perception/plan 产物/execution/verification/evidence/chain）。"""
    state = context["final_state"]
    assert state.get("perception") is not None
    assert state.get("plan") is not None
    assert state.get("execution") is not None
    assert state.get("verification") is not None
    assert state.get("evidence") is not None
    assert state.get("chain") is not None


@then("轨迹含验证反思规划重试环且终态成功")
def then_reflect_retry_loop_success(context: dict[str, Any]) -> None:
    """fail_once 路径轨迹：...verify→reflect→plan→execute→verify→package。"""
    state = context["final_state"]
    phases = state["executed_phases"]
    expected_prefix = ["perceive", "plan", "execute", "verify", "reflect", "plan", "execute", "verify", "package"]
    assert phases == expected_prefix, f"反思重试轨迹异常: {phases}"
    assert state["evidence"].status == "completed"


@then("重试轮规划提示词包含修正计划与错误分析")
def then_retry_plan_prompt_contains_revision(context: dict[str, Any]) -> None:
    """R2-F4：重试轮 plan prompt 注入 revised_plan + error_analysis 断言。

    R1 修复：选调锚改 PlanSchema 身份（原「规划 in system_prompt」对全部调用
    恒真——system_prompt 六阶段共用；终局合成模板自带「修正」二字使 OR 兜底
    恒绿，R2-F4 断裂时本断言不红——空心化）。断言锚 = Fake 产物精确串，与
    分派键（Schema 身份）独立。
    """
    from src.application.services.agent_workflow_schemas import PlanSchema

    fake_llm = context["fake_llm"]
    plan_calls = [
        call.kwargs.get("prompt", "") or call.args[0]
        for call in fake_llm.structured_generate.call_args_list
        if call.kwargs.get("response_schema") is PlanSchema
    ]
    assert len(plan_calls) >= 2, f"fail_once 路径应存在两次 plan 调用，实际 {len(plan_calls)} 次"
    # 第二次 plan 调用（重试轮）须含反思产物注入（Fake 反思产物的精确串——
    # 不用「修正」类模板兜底词，防终局合成 prompt 的静态文本污染）
    retry_prompt = plan_calls[1]
    assert "补充约束参数" in retry_prompt, f"重试轮 plan prompt 未注入修正计划: {retry_prompt[:200]}"
    assert "工具输出缺少关键约束字段" in retry_prompt, f"重试轮 plan prompt 未注入错误分析: {retry_prompt[:200]}"


@then("未耗尽重试即直接打包失败证据")
def then_not_revisable_early_exit(context: dict[str, Any]) -> None:
    """第四路径：reflect 判定不可修正（revised=False 且未耗尽）→ 直接 package(failed)。"""
    state = context["final_state"]
    phases = state["executed_phases"]
    expected = ["perceive", "plan", "execute", "verify", "reflect", "package"]
    assert phases == expected, f"不可修正早退轨迹异常: {phases}"
    assert state["evidence"].status == "failed"
    assert state["retry_count"] == 1, "reflect 执行一次即消耗一次重试（未耗尽）"


@then("规划阶段总执行次数不超过 3 次")
def then_plan_execution_bounded(context: dict[str, Any]) -> None:
    """重试语义：初始 1 + 重试 2 = plan 总执行 ≤3（reflect 递增 + <= 谓词）。"""
    state = context["final_state"]
    phases = state["executed_phases"]
    plan_count = phases.count("plan")
    assert plan_count == 3, f"恒失败+恒可修正应触发满 3 次 plan: {phases}"
    assert state["retry_count"] == 3, "retry_count 终值=reflect 总执行数（第三次 reflect 判定耗尽）"


@then("终态证据携带失败标记与失败原因")
def then_failed_evidence_marker(context: dict[str, Any]) -> None:
    """失败终态：status=failed + failure_reason 非空（末次验证失败摘要）。"""
    evidence = context["final_state"]["evidence"]
    assert evidence.status == "failed"
    assert evidence.failure_reason.strip(), "失败终态 failure_reason 必须非空"


@then("发布的 AgentDecided 事件 agent_id 与入参完全一致")
def then_agent_decided_agent_id_matches(context: dict[str, Any]) -> None:
    """agent_id 贯通：事件 agent_id == parameters 传入实体 id（5-2 风险 #2 核销）。"""
    decided_events = [e for e in context["recorder"].published_events if type(e).__name__ == "AgentDecided"]
    assert decided_events, "应发布 AgentDecided 事件"
    assert decided_events[0].agent_id == context["agent_id"], (
        f"事件 agent_id {decided_events[0].agent_id} != 入参 {context['agent_id']}"
    )


@then("思维链五字段完备且非空")
def then_chain_five_fields_complete(context: dict[str, Any]) -> None:
    """五字段完备：四 str 字段非空 + tools_used 元组形态（空元组合法）。"""
    chain = context["final_state"]["chain"]
    for name in ("input_summary", "reflection", "constraints_check", "final_answer"):
        value = getattr(chain, name)
        assert isinstance(value, str) and value.strip(), f"字段 {name} 应为非空 str"
    assert isinstance(chain.tools_used, tuple), "tools_used 应为 tuple 形态"


@then("tools_used 与真实工具调用轨迹一致")
def then_tools_used_matches_real_trace(context: dict[str, Any]) -> None:
    """覆写制断言：chain.tools_used == 真实执行轨迹（Fake 终局回声值相异——判别力）。"""
    chain = context["final_state"]["chain"]
    execution = context["final_state"]["execution"]
    real_trace = execution.tool_trace if hasattr(execution, "tool_trace") else ()
    assert chain.tools_used == real_trace, f"tools_used {chain.tools_used} != 真实轨迹 {real_trace}（覆写制失效）"
    assert "fake-echo" not in "".join(chain.tools_used), "Fake 回声值泄漏（未覆写）"


@then("to_display 生成五段展示形态")
def then_to_display_five_segments(context: dict[str, Any]) -> None:
    """展示形态：Input → Reflection → Tools_Used → Constraints_Check → JSON。"""
    display = context["chain_vo"].to_display()
    assert "Input" in display
    assert display.index("Input") < display.index("<Reflection>"), "分段顺序: Input 在 Reflection 前"


@then("输出含三个 XML 标签段与 JSON 尾段")
def then_display_xml_tags_and_json_tail(context: dict[str, Any]) -> None:
    """三 XML 标签段 + JSON 尾段（or.md §五.5 展示契约）。"""
    display = context["chain_vo"].to_display()
    assert "<Reflection>" in display and "</Reflection>" in display
    assert "<Tools_Used>" in display and "</Tools_Used>" in display
    assert "<Constraints_Check>" in display and "</Constraints_Check>" in display
    json_tail = display.rsplit("→", 1)[-1].strip()
    json.loads(json_tail)  # 尾段必须是合法 JSON


@then("证据包六类字段齐备且输入哈希为 SHA256 六十四位十六进制")
def then_evidence_six_classes_and_hash(context: dict[str, Any]) -> None:
    """六类字段（输入哈希/分解图/轨迹/快照/置信度依据/引用源）+ sha256 口径。"""
    evidence = context["final_state"]["evidence"]
    for name in (
        "input_hash",
        "task_breakdown",
        "tool_trace",
        "artifacts_snapshot",
        "confidence",
        "confidence_rationale",
        "citations",
    ):
        assert hasattr(evidence, name), f"证据字段缺失: {name}"
    task = context["task"]
    assert evidence.input_hash == hashlib.sha256(task.encode()).hexdigest(), "input_hash 口径: sha256(task_description)"
    assert len(evidence.input_hash) == 64 and all(c in "0123456789abcdef" for c in evidence.input_hash)


@then("置信度与依据来源于验证阶段产物")
def then_confidence_from_verification(context: dict[str, Any]) -> None:
    """置信度同源验证阶段（Fake verify pass 时 confidence=0.85——非硬编码 0.9）。"""
    evidence = context["final_state"]["evidence"]
    verification = context["final_state"]["verification"]
    assert evidence.confidence == verification.confidence, "置信度应同源验证阶段"
    assert evidence.confidence == 0.85, "Fake 验证通过档位 0.85（区别于硬编码 0.9）"
    assert evidence.confidence_rationale.strip()


@then("失败终态证据包含跨重试轮全部工具轨迹")
def then_failed_evidence_full_trace(context: dict[str, Any]) -> None:
    """历史聚合断言：恒失败 3 轮 plan → 工具轨迹跨轮累积（键覆盖丢前轮即红）。"""
    state = context["final_state"]
    evidence = state["evidence"]
    plan_count = state["executed_phases"].count("plan")
    trace = evidence.tool_trace
    assert plan_count >= 2, "前置：应至少两个执行轮"
    # 形态 + 精确下界（同源派生：given 每轮 plan 含 1 工具步 → 轨迹数 >= plan 轮数；
    # execute 聚合改键覆盖丢前轮时 len < plan_count 必红——恒真形态已修）
    assert isinstance(trace, tuple), "轨迹应为元组形态（frozen VO 不可变纪律）"
    assert len(trace) >= plan_count, "跨轮轨迹应累积至计划轮数下界（键覆盖丢前轮即红）"
    execution = state["execution"]
    assert execution is not None and len(execution.tool_trace) == len(trace), (
        "execution 与 evidence 轨迹应同长（聚合语义——覆盖丢前轮轨迹即红）"
    )


@then("失败原因携带末次验证失败摘要")
def then_failure_reason_last_verification(context: dict[str, Any]) -> None:
    """failure_reason = 末次验证失败摘要（Fake rationale 含轮次锚）。"""
    evidence = context["final_state"]["evidence"]
    verification = context["final_state"]["verification"]
    assert evidence.failure_reason == verification.rationale, "失败原因应为末次验证摘要"


@then("SAPMessage 模型包含十五个字段且类型正确")
def then_sap_message_fifteen_fields(context: dict[str, Any]) -> None:
    """15 字段存在性与类型（验收 tripwire——AC-4×3 与 Task 2 单测断言面重复，
    保留为静态绊线先例）。"""
    import datetime
    import uuid as uuid_module

    from src.interfaces.sap.message import SAPMessage

    field_names = set(SAPMessage.model_fields)
    assert len(field_names) == 15, f"字段总数应为 15: {field_names}"

    message = SAPMessage(
        message_id=uuid_module.uuid4(),
        conversation_id=uuid_module.uuid4(),
        sender_id="agent-ceo",
        receiver_id="agent-cfo",
        message_type="request",
        content="请提供财务视角评估",
    )
    assert isinstance(message.message_id, uuid_module.UUID)
    assert isinstance(message.timestamp, datetime.datetime)
    assert isinstance(message.context, dict)


@then("十个必需字段逐一点名存在")
def then_sap_ten_required_fields_named(context: dict[str, Any]) -> None:
    """epics 验收点名的 10 必需字段逐一点名（tripwire 第二断言面）。"""
    from src.interfaces.sap.message import SAPMessage

    required_ten = (
        "message_id",
        "conversation_id",
        "sender_id",
        "receiver_id",
        "message_type",
        "priority",
        "content",
        "correlation_id",
        "isolation_level",
        "blackboard_visible",
    )
    field_names = set(SAPMessage.model_fields)
    for name in required_ten:
        assert name in field_names, f"必需字段缺失: {name}"


@then("MessageType 含五种类型且 MessagePriority 含四级优先级")
def then_sap_enum_values(context: dict[str, Any]) -> None:
    """枚举值集合：request/response/notification/broadcast/debate + low/normal/high/urgent。"""
    from src.interfaces.sap.types import MessagePriority, MessageType

    assert {item.value for item in MessageType} == {"request", "response", "notification", "broadcast", "debate"}
    assert {item.value for item in MessagePriority} == {"low", "normal", "high", "urgent"}


@then("默认值为普通优先级硬隔离不公开黑板且超时 300 秒")
def then_sap_defaults(context: dict[str, Any]) -> None:
    """四默认值：priority=NORMAL / isolation_level=L4_HARD / blackboard_visible=False / timeout=300。"""
    import uuid as uuid_module

    from src.domain.events.enums import IsolationLevel
    from src.interfaces.sap.message import SAPMessage
    from src.interfaces.sap.types import MessagePriority

    message = SAPMessage(
        message_id=uuid_module.uuid4(),
        conversation_id=uuid_module.uuid4(),
        sender_id="agent-ceo",
        receiver_id="broadcast",
        message_type="broadcast",
        content="广播消息",
    )
    assert message.priority is MessagePriority.NORMAL
    assert message.isolation_level is IsolationLevel.L4_HARD
    assert message.blackboard_visible is False
    assert message.timeout_seconds == 300


@then("conversation_id 必填且 correlation_id 默认可空")
def then_sap_required_and_nullable(context: dict[str, Any]) -> None:
    """conversation_id 无默认（缺失构造 ValidationError）+ correlation_id: UUID | None = None。"""
    import uuid as uuid_module

    import pydantic

    from src.interfaces.sap.message import SAPMessage

    # model_validate(dict) 承载「必填缺失」负向构造（裸 SAPMessage(...) 缺参
    # 形态对 mypy 是 call-arg 静态错误——model_validate 等价运行时语义）
    with pytest.raises(pydantic.ValidationError):
        SAPMessage.model_validate(
            {
                "message_id": uuid_module.uuid4(),
                "sender_id": "agent-ceo",
                "receiver_id": "agent-cfo",
                "message_type": "request",
                "content": "缺少 conversation_id",
            }
        )

    message = SAPMessage(
        message_id=uuid_module.uuid4(),
        conversation_id=uuid_module.uuid4(),
        sender_id="agent-ceo",
        receiver_id="agent-cfo",
        message_type="request",
        content="correlation_id 可空",
    )
    assert message.correlation_id is None


@then("非法枚举值构造被拒绝且时间戳为 UTC 感知")
def then_sap_invalid_rejected_and_utc(context: dict[str, Any]) -> None:
    """非法 message_type 构造 ValidationError + timestamp tz-aware（禁裸 utcnow）。"""
    import uuid as uuid_module

    import pydantic

    from src.interfaces.sap.message import SAPMessage

    with pytest.raises(pydantic.ValidationError):
        SAPMessage(
            message_id=uuid_module.uuid4(),
            conversation_id=uuid_module.uuid4(),
            sender_id="agent-ceo",
            receiver_id="agent-cfo",
            message_type="invalid-type",
            content="非法枚举",
        )

    message = SAPMessage(
        message_id=uuid_module.uuid4(),
        conversation_id=uuid_module.uuid4(),
        sender_id="agent-ceo",
        receiver_id="agent-cfo",
        message_type="request",
        content="UTC 感知",
    )
    assert message.timestamp.tzinfo is not None, "timestamp 必须为 tz-aware（architecture v8.4.0 红线）"


@then("工作流执行延迟 P95 小于 10 秒且计时含六阶段全链")
def then_p95_under_10s(context: dict[str, Any]) -> None:
    """P95 断言（NFR-PERF-04 MVP 档）+ 计时下界锚（同源派生——R1 耗时优化）。"""
    from tests.integration.test_integration_agent_workflow import FAKE_LLM_DELAY_SEC

    assert len(context["perf_samples"]) == 20, "采样数 20（warmup 已剔除）"
    assert context["p95"] < 10.0, f"P95 {context['p95']:.2f}s >= 10s"
    # 计时下界（同源派生——与集成 helper 的 FAKE_LLM_DELAY_SEC 单源防漂移）：
    # 工作流级 4 次调用（perceive/plan/verify/终局）× 延迟档（调用数判别力
    # 由 scenario_2 的逐轮调用数锁承载）
    assert context["p95"] >= 4 * FAKE_LLM_DELAY_SEC, f"P95 {context['p95']:.2f}s 低于 Fake 延迟下界（计时未含全链）"


@then("五字段完备的思维链占比不低于 98%")
def then_completeness_rate(context: dict[str, Any]) -> None:
    """完整率 ≥98%（Fake 确定性产出下 100%——20/20）。"""
    total = context["completeness_total"]
    complete = context["completeness_complete"]
    assert total == 20, f"分母应为 20: {total}"
    assert complete / total >= 0.98, f"完整率 {complete}/{total} < 98%"


@then("全部会话成功完成且产出完整思维链与证据包")
def then_concurrent_all_success(context: dict[str, Any]) -> None:
    """并发 10 会话全成功 + 每会话 chain/evidence 完备。"""
    results = context["concurrent_results"]
    assert len(results) == 10
    for item in results:
        state = item["state"]
        assert state is not None, f"会话 {item['agent_id']} 终态缺失"
        assert state["evidence"].status == "completed"
        assert state["chain"] is not None
        assert state["executed_phases"][-1] == "package"


@then("agent_workflow_service 与 agent_workflow_use_case 经组合根注册可解析")
def then_ports_resolvable(context: dict[str, Any]) -> None:
    """AC-6.1 接线断言：两新端口 resolve + isinstance（5-2 AC-6.1 同款）。"""
    from src.application.ports.agent_workflow import AgentWorkflowServicePort
    from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase
    from src.domain.ports.resolver import resolve
    from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine

    service = resolve("agent_workflow_service")
    use_case = resolve("agent_workflow_use_case")

    assert isinstance(service, AgentWorkflowServicePort), "service 应满足端口 Protocol"
    assert isinstance(use_case, RunAgentWorkflowUseCase), "use_case 应为具体用例类"

    from src.domain.ports.registry import _global_registry

    for port_name in ("agent_workflow_service", "agent_workflow_use_case"):
        spec = _global_registry.get(port_name)
        assert spec is not None, f"端口 {port_name} 未注册"
        assert spec.lifetime.value.lower() == "singleton"

    engine = resolve("agent_engine")
    assert isinstance(engine, LangGraphEngine), "agent_engine 应为 LangGraphEngine 实例"


@then("SingleAgentWorkflow 图名在引擎支持清单注册")
def then_graph_registered(context: dict[str, Any]) -> None:
    """图注册 + 图身份锚（防未知图名静默回退 BasicAgent 仍绿）。"""
    from src.domain.ports.resolver import resolve

    engine = resolve("agent_engine")
    assert "SingleAgentWorkflow" in engine._SUPPORTED_GRAPHS, "图名未注册"


@then("AgentDecided 事件决策结果含工作流状态与重试计数")
def then_decision_result_projection(context: dict[str, Any]) -> None:
    """decision_result 五键纯标量投影（workflow_status/task_summary/chain_summary/evidence_ref/retry_count）。"""
    decided_events = [e for e in context["recorder"].published_events if type(e).__name__ == "AgentDecided"]
    assert decided_events, "应发布 AgentDecided"
    decision = decided_events[0].decision_result
    for key in ("workflow_status", "task_summary", "chain_summary", "evidence_ref", "retry_count"):
        assert key in decision, f"decision_result 缺投影键: {key}"
        assert isinstance(decision[key], (str, int, float)), f"投影键 {key} 应为纯标量（VO 禁入 dict——JSON 序列化炸）"


@then("置信度来自验证阶段而非硬编码")
def then_confidence_not_hardcoded(context: dict[str, Any]) -> None:
    """事件 confidence == state 验证置信度（Fake 0.85 档——硬编码 0.9 必红）。"""
    decided_events = [e for e in context["recorder"].published_events if type(e).__name__ == "AgentDecided"]
    event = decided_events[0]
    state = context["final_state"]
    assert event.confidence == state["verification"].confidence, "事件置信度应取 state"
    assert event.confidence == 0.85, f"confidence {event.confidence} 非 Fake 验证档位（硬编码泄漏？）"


@then("退出码为 0 且输出六阶段状态行与思维链预览与置信度")
def then_cli_success_exit_zero(context: dict[str, Any]) -> None:
    """CLI 成功路径：exit 0 + 六阶段状态行 + 思维链预览 + 证据引用 + 置信度。"""
    assert context["cli_exit_code"] == 0
    output = context["cli_captured"].out
    assert "perceive" in output and "package" in output, "六阶段状态行缺失"
    assert "<Reflection>" in output, "思维链五段预览缺失"
    assert "0.85" in output, "置信度输出缺失"


@then("退出码为 0 且输出失败状态摘要")
def then_cli_failed_completion_exit_zero(context: dict[str, Any]) -> None:
    """失败完成态：exit 0（工作流正常走完）+ status=failed 摘要（与系统错误 exit 1 区分）。"""
    assert context["cli_exit_code"] == 0, "失败完成态是正常走完语义——exit 0"
    output = context["cli_captured"].out
    assert "failed" in output, "失败状态摘要缺失"


@then("退出码为 1 且 stderr 携带 EXCEPTION_443 编码")
def then_cli_guard_exit_one(context: dict[str, Any]) -> None:
    """守卫路径：443 退出码 1 + stderr [EXCEPTION_443] 编码。"""
    assert context["cli_exit_code"] == 1
    captured = context["cli_captured"]
    assert "EXCEPTION_443" in captured.err, f"stderr 缺 443 编码: {captured.err!r}"


# ===================================================================
# Task 9 收尾：完成清单场景（AC-6.4——AC-6.3 形态同款静态断言）
# ===================================================================


@then("src 与 tests 完成清单逐项存在")
def then_completion_checklist_src_tests(context: dict[str, Any]) -> None:
    """src 新建 12 + 扩展 6 + tests 四目录清单逐项存在性断言（Story 项目结构节）。"""
    src_new_files = (
        "src/domain/value_objects/chain_of_thought.py",
        "src/domain/value_objects/task_evidence.py",
        "src/application/ports/agent_workflow.py",
        "src/application/services/agent_workflow_prompts.py",
        "src/application/services/agent_workflow_schemas.py",
        "src/application/services/agent_workflow_context.py",
        "src/application/services/agent_workflow_service.py",
        "src/application/use_cases/run_agent_workflow.py",
        "src/infrastructure/agent_orch/graphs/single_agent_workflow_graph.py",
        "src/interfaces/sap/__init__.py",
        "src/interfaces/sap/types.py",
        "src/interfaces/sap/message.py",
    )
    src_extended_files = (
        "src/domain/ports/agent_engine.py",
        "src/infrastructure/agent_orch/langgraph_engine.py",
        "src/infrastructure/agent_orch/schemas.py",
        "src/domain/exceptions/agent_exceptions.py",
        "src/entrypoints/agent_cli.py",
        "src/composition_root.py",
    )
    test_files = (
        "tests/unit/domain/value_objects/test_chain_of_thought.py",
        "tests/unit/domain/value_objects/test_task_evidence.py",
        "tests/unit/domain/exceptions/test_agent_exceptions.py",
        "tests/unit/interfaces/sap/test_message.py",
        "tests/unit/application/services/test_agent_workflow_prompts.py",
        "tests/unit/application/services/test_agent_workflow_schemas.py",
        "tests/unit/application/services/test_agent_workflow_context.py",
        "tests/unit/application/services/test_agent_workflow_service.py",
        "tests/unit/application/use_cases/test_run_agent_workflow.py",
        "tests/unit/infrastructure/agent_orch/test_single_agent_workflow_graph.py",
        "tests/unit/interfaces/cli/test_agent_cli.py",
        "tests/contracts/test_port_contract_agent_workflow_service.py",
        "tests/contracts/test_port_contract_agent_workflow_use_case.py",
        "tests/contracts/test_port_contract_agent_engine.py",
        "tests/integration/test_integration_agent_workflow.py",
        "tests/unit/architecture/test_arch_agent_workflow.py",
        "tests/acceptance/test_acceptance_agent_workflow.feature",
        "tests/acceptance/test_acceptance_agent_workflow.py",
    )
    for rel in (*src_new_files, *src_extended_files, *test_files):
        assert (REPO_ROOT / rel).exists(), f"完成清单缺文件: {rel}"


@then("链路接线断言清单全部已验证")
def then_wiring_assertions_verified(context: dict[str, Any]) -> None:
    """链路接线断言清单（Task 0 落盘——Epic 4 行动项 7.1-1）逐项静态终态。"""
    from src.domain.ports.registry import _global_registry

    # L1: 两新端口组合根注册可达
    for port_name in ("agent_workflow_service", "agent_workflow_use_case"):
        assert _global_registry.get(port_name) is not None, f"L1 断言: {port_name} 未注册"

    # L2: SingleAgentWorkflow 图名注册（图身份锚载体）
    composition = (REPO_ROOT / "src" / "composition_root.py").read_text(encoding="utf-8")
    assert '"agent_workflow_service"' in composition, "L2 前置: 组合根注册名缺失"
    engine_source = (REPO_ROOT / "src" / "infrastructure" / "agent_orch" / "langgraph_engine.py").read_text(encoding="utf-8")
    assert '"SingleAgentWorkflow"' in engine_source, "L2 断言: 图名未注册"

    # L3: AgentDecided 发布点（引擎内——图身份锚断言载体存在于引擎测试）
    engine_test = (REPO_ROOT / "tests" / "unit" / "infrastructure" / "agent_orch" / "test_langgraph_engine.py").read_text(
        encoding="utf-8"
    )
    assert "decision_result" in engine_test and "confidence == 0.72" in engine_test, "L3 断言: 图身份锚/置信度真实化测试缺失"

    # L4: get_graph_result 终态 state 取回
    assert "async def get_graph_result" in (REPO_ROOT / "src" / "domain" / "ports" / "agent_engine.py").read_text(
        encoding="utf-8"
    ), "L4 断言: 端口缺 get_graph_result"

    # L5: 444 端到端可达（引擎 DomainError 透传 + CLI stderr 编码测试）
    assert "test_node_444_propagates_as_domain_error" in engine_test, "L5 断言: 引擎 444 透传测试缺失"
    cli_test = (REPO_ROOT / "tests" / "unit" / "interfaces" / "cli" / "test_agent_cli.py").read_text(encoding="utf-8")
    assert "EXCEPTION_444" in cli_test, "L5 断言: CLI 444 编码测试缺失"

    # L6: CLI run-task 全链（子命令注册）
    cli_source = (REPO_ROOT / "src" / "entrypoints" / "agent_cli.py").read_text(encoding="utf-8")
    assert '"run-task"' in cli_source, "L6 断言: run-task 子命令缺失"
