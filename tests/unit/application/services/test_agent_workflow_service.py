"""AgentWorkflowService 六阶段逻辑单元测试（Story 5-3 — 单 Agent 标准工作流）

覆盖六阶段服务的编排契约（Fake LLM 身份分派——response_schema is X 分派键
与断言锚独立，4-5 纪律）：
- build_context 装配委托（WorkflowContext 五字段——context 模块单测的组装面）
- perceive/plan/verify/reflect 的 prompt 构造与 Schema 解析（温度分档断言）
- plan 重试轮回灌（state 含 reflection 时 prompt 注入 revised_plan/error_analysis
  ——R2-F4：防重试退化为同输入复读）
- execute 阶段级聚合：零工具步/单步/多步；get_tool(tool_name=) 名字→实体 +
  TES.execute(tool_id, ToolCall, ExecutionContext) 经端口调用断言（DC-10）；
  历史聚合（读 state 旧 execution 追加合并——R2-F5 防重试轮覆盖丢轨迹）
- package_evidence：九字段组装（input_hash sha256 口径/轨迹聚合/失败终态
  分支）+ 终局思维链合成（一次 structured_generate(ChainOfThoughtSchema) +
  组装覆写——tools_used==真实轨迹、Fake 回声值被覆写，DC-2）
- 异常契约：LLM 族异常包装 444 携带 phase / LLMConfigError 与 CancelledError
  透传 / structured_generate 非 Schema 实例守卫 444 / VO 242→445 改写
  （missing_fields——异常契约三层次序②）

Run with:
    poetry run pytest tests/unit/application/services/test_agent_workflow_service.py -v
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from src.domain.ports.llm_client import LLMClientPort
from src.domain.value_objects.tool_execution import (
    ExecutionContext,
    ToolCall,
    ToolResult,
    ToolResultStatus,
)

# ===================================================================
# Fake LLM（response_schema 身份分派 + 调用记录——分派键与断言锚独立）
# ===================================================================


def _make_fake_llm(
    *,
    verify_passed: bool = True,
    chain_echo_tools: tuple[str, ...] = ("fake-echo:not-real",),
    llm_error_by_schema: dict[type, BaseException] | None = None,
    non_schema_return: bool = False,
    chain_echo_instance: Any = None,
    plan_tool_names: tuple[str, ...] | None = None,
) -> Any:
    """六阶段 Fake LLM 端口替身。

    分派键 = response_schema 身份（六阶段 Schema 两两不同是前提）；调用
    记录四元组 (prompt, system_prompt, response_schema, temperature) 供
    prompt/温度断言。终局分支返回与真实轨迹【相异】的 tools_used（防 Fake
    回声——覆写制断言判别力实证，R3-F8）。

    Args:
        verify_passed: 验证阶段返回值
        chain_echo_tools: 终局合成分支的回声 tools_used（相异值）
        llm_error_by_schema: 按 Schema 注入异常（异常路径测试）
        non_schema_return: structured_generate 返回非 Schema 实例（守卫测试）
        chain_echo_instance: 终局分支直接返回的实例（model_construct 穿透
            Schema 校验——三层次序② VO 242 路径测试用）
        plan_tool_names: plan 阶段步骤工具名定制（None 用默认两步；空串元素
            表示直接推理步——Story 5.5 白名单预检测试面）

    Returns:
        AsyncMock(spec=LLMClientPort) 替身（_workflow_calls 记录列表）
    """
    from src.application.services.agent_workflow_schemas import (
        ChainOfThoughtSchema,
        PerceptionSchema,
        PlanSchema,
        ReflectionSchema,
        VerificationSchema,
    )

    calls: list[tuple[str, str | None, type, float | None]] = []
    errors = llm_error_by_schema or {}
    plan_steps = (
        [
            {"description": f"步骤 {index + 1}", "tool_name": tool_name, "arguments": {}}
            for index, tool_name in enumerate(plan_tool_names)
        ]
        if plan_tool_names is not None
        else [
            {"description": "执行宏观环境分析", "tool_name": "PESTEL 分析", "arguments": {"scope": "CN"}},
            {"description": "综合建议（零工具步）", "tool_name": "", "arguments": {}},
        ]
    )

    async def _structured_generate(
        prompt: str,
        response_schema: type,
        config: Any = None,
        system_prompt: str | None = None,
    ) -> Any:
        temperature = config.temperature if config is not None else None
        calls.append((prompt, system_prompt, response_schema, temperature))
        if response_schema in errors:
            raise errors[response_schema]
        if non_schema_return and response_schema is PerceptionSchema:
            return {"summary": "非 Schema 实例返回"}
        if response_schema is PerceptionSchema:
            return PerceptionSchema(summary="任务摘要：战略分析")
        if response_schema is PlanSchema:
            return PlanSchema(
                steps=plan_steps,
                selected_tools=[step["tool_name"] for step in plan_steps if step["tool_name"]],
            )
        if response_schema is VerificationSchema:
            return VerificationSchema(
                passed=verify_passed,
                confidence=0.85 if verify_passed else 0.42,
                rationale="结构化检查通过" if verify_passed else "第 1 次验证未通过：约束缺失",
            )
        if response_schema is ReflectionSchema:
            return ReflectionSchema(
                error_analysis="工具输出缺少关键约束字段",
                revised_plan="补充约束参数后重新执行工具并复核",
                revised=True,
            )
        if response_schema is ChainOfThoughtSchema:
            if chain_echo_instance is not None:
                return chain_echo_instance
            return ChainOfThoughtSchema(
                input_summary="Fake 回声摘要（应被覆写）",
                reflection="Fake 回声反思（终局合成产物）",
                tools_used=list(chain_echo_tools),
                constraints_check="Fake 回声约束（终局合成产物）",
                final_answer='{"answer": "终局综合答案"}',
            )
        raise AssertionError(f"未预期的 response_schema: {response_schema}")

    fake = AsyncMock(spec=LLMClientPort)
    fake.structured_generate.side_effect = _structured_generate
    fake._workflow_calls = calls
    return fake


# ===================================================================
# 工具面 mock（单元测试 Mock 端口——get_tool sync / execute async）
# ===================================================================


def _make_tool_mocks(tool_name: str = "PESTEL 分析", tool_version: str = "1.2.0") -> tuple[Any, Any]:
    """构造工具注册与执行服务 mock（get_tool 返回真实 Tool 实体）。"""
    from src.application.ports.tool_execution_service import ToolExecutionServicePort
    from src.application.ports.tool_registry_service import ToolRegistryServicePort
    from src.domain.entities.tool import Tool, ToolCategory

    registry = Mock(spec=ToolRegistryServicePort)
    registry.get_tool.return_value = Tool(
        tool_id=uuid.uuid4(),
        name=tool_name,
        category=ToolCategory.ENVIRONMENT_ANALYSIS,
        version=tool_version,
    )
    execution_service = AsyncMock(spec=ToolExecutionServicePort)
    execution_service.execute.return_value = ToolResult(
        tool_id=registry.get_tool.return_value.tool_id,
        status=ToolResultStatus.SUCCESS,
        output={"result": "分析完成"},
    )
    return registry, execution_service


def _make_service(
    fake_llm: Any,
    registry: Any,
    execution_service: Any,
    isolation_guard: Any = None,
) -> Any:
    """构造 AgentWorkflowService（R2 组合端口五依赖——skill_loader/guard 注入）。

    Args:
        fake_llm: 六阶段 Fake LLM 替身。
        registry: 工具注册服务 mock。
        execution_service: 工具执行服务 mock。
        isolation_guard: 隔离守卫替身（None 时构造默认放行 AsyncMock——
            ensure_tool_access 静默返回 None）。
    """
    from src.application.ports.isolation_guard import IsolationGuardPort
    from src.application.services.agent_workflow_service import AgentWorkflowService

    skill_loader = AsyncMock()
    guard = isolation_guard if isolation_guard is not None else AsyncMock(spec=IsolationGuardPort)
    return AgentWorkflowService(
        llm_client=fake_llm,
        tool_execution_service=execution_service,
        skill_loader=skill_loader,
        tool_registry_service=registry,
        isolation_guard=guard,
    )


def _make_state(
    *,
    task: str = "分析新能源汽车行业进入战略",
    context: Any = None,
    **extra: Any,
) -> dict[str, Any]:
    """构造六阶段 state（context 键 + 可选前阶段产物）。"""
    from src.application.ports.agent_workflow import WorkflowContext
    from src.application.ports.skill_loader import ToolMetadata

    tools_l1 = (
        ToolMetadata(
            tool_name="PESTEL 分析",
            slug="pestel-analysis",
            category="environment_analysis",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            description="宏观环境六维度分析",
            when_to_use=("宏观环境分析",),
        ),
    )
    if context is None:
        context = WorkflowContext(
            system_prompt="## 身份档案（IDENTITY）\n\nCEO",
            tools_l1=tools_l1,
            task=task,
            tenant_id=uuid.uuid4(),
            assembled_context_tokens=100,
        )
    state: dict[str, Any] = {"agent_id": str(uuid.uuid4()), "task": task, "context": context}
    state.update(extra)
    return state


# ===================================================================
# build_context 装配委托
# ===================================================================


class TestBuildContext:
    """build_context 装配（委托 context 模块——服务端口装配入口）。"""

    def test_build_context_returns_workflow_context(self) -> None:
        fake_llm = _make_fake_llm()
        registry, execution_service = _make_tool_mocks()
        service = _make_service(fake_llm, registry, execution_service)

        from src.application.ports.agent_workflow import WorkflowContext
        from src.application.use_cases.agent_profile_loading import AgentProfileLoadResult
        from src.domain.entities.agent import AgentRole
        from src.domain.value_objects.agent_profile import AgentProfile

        profile = AgentProfile(
            agent_id=uuid.uuid4(),
            role=AgentRole.CEO,
            identity="# IDENTITY\nCEO",
            code_of_conduct="# CODE\n规则",
            soul="# SOUL\n视角",
            user_preferences="# USER\n偏好",
            memory="# MEMORY\n记忆",
            heartbeat="# HEARTBEAT\n心跳",
        )
        result = AgentProfileLoadResult(
            agent_id=profile.agent_id,
            role=AgentRole.CEO,
            profile=profile,
            tools_l1=(),
            startup_context_tokens=0,
        )
        context = service.build_context(result, "任务描述")
        assert isinstance(context, WorkflowContext)
        assert context.task == "任务描述"
        assert context.tenant_id is not None
        assert context.assembled_context_tokens > 0
        assert "CEO" in context.system_prompt
        assert "HEARTBEAT" not in context.system_prompt


# ===================================================================
# perceive / verify / reflect（单阶段面）
# ===================================================================


class TestPerceive:
    """感知阶段：任务摘要 prompt + PerceptionSchema 解析 + 温度 0.3。"""

    def test_perceive_returns_summary(self) -> None:
        fake_llm = _make_fake_llm()
        registry, execution_service = _make_tool_mocks()
        service = _make_service(fake_llm, registry, execution_service)

        state = _make_state()
        result = asyncio.run(service.perceive(state))
        assert result.summary == "任务摘要：战略分析"

    def test_perceive_prompt_contains_task_and_temperature(self) -> None:
        fake_llm = _make_fake_llm()
        registry, execution_service = _make_tool_mocks()
        service = _make_service(fake_llm, registry, execution_service)

        state = _make_state(task="分析新能源汽车行业进入战略")
        asyncio.run(service.perceive(state))

        prompt, system_prompt, schema, temperature = fake_llm._workflow_calls[-1]
        assert "分析新能源汽车行业进入战略" in prompt
        assert system_prompt == state["context"].system_prompt
        assert temperature == 0.3


class TestVerify:
    """验证阶段：VerificationSchema 解析 + 温度 0.1。"""

    def test_verify_returns_result(self) -> None:
        fake_llm = _make_fake_llm(verify_passed=True)
        registry, execution_service = _make_tool_mocks()
        service = _make_service(fake_llm, registry, execution_service)

        from src.application.ports.agent_workflow import ExecutionResult

        state = _make_state(execution=ExecutionResult(step_summaries=("步一完成",)))
        result = asyncio.run(service.verify(state))
        assert result.passed is True
        assert result.confidence == 0.85
        assert "结构化检查" in result.rationale

    def test_verify_temperature_and_execution_summary(self) -> None:
        fake_llm = _make_fake_llm()
        registry, execution_service = _make_tool_mocks()
        service = _make_service(fake_llm, registry, execution_service)

        from src.application.ports.agent_workflow import ExecutionResult

        state = _make_state(execution=ExecutionResult(step_summaries=("已执行 PESTEL 工具",)))
        asyncio.run(service.verify(state))

        prompt, _, schema, temperature = fake_llm._workflow_calls[-1]
        assert "已执行 PESTEL 工具" in prompt
        assert temperature == 0.1


class TestReflect:
    """反思阶段：ReflectionSchema 解析 + 温度 0.4 + 验证依据入 prompt。"""

    def test_reflect_returns_result(self) -> None:
        fake_llm = _make_fake_llm()
        registry, execution_service = _make_tool_mocks()
        service = _make_service(fake_llm, registry, execution_service)

        from src.application.ports.agent_workflow import VerificationResult

        state = _make_state(verification=VerificationResult(passed=False, confidence=0.42, rationale="第 1 次验证未通过"))
        result = asyncio.run(service.reflect(state))
        assert result.revised is True
        assert "补充约束" in result.revised_plan

        prompt, _, _, temperature = fake_llm._workflow_calls[-1]
        assert "第 1 次验证未通过" in prompt
        assert temperature == 0.4


# ===================================================================
# plan（基础 + 重试轮回灌——R2-F4）
# ===================================================================


class TestPlan:
    """规划阶段：任务分解 + 工具匹配 + 重试轮回灌。"""

    def test_plan_returns_steps(self) -> None:
        fake_llm = _make_fake_llm()
        registry, execution_service = _make_tool_mocks()
        service = _make_service(fake_llm, registry, execution_service)

        state = _make_state()
        result = asyncio.run(service.plan(state))
        assert len(result.steps) == 2
        assert result.steps[0][1] == "PESTEL 分析"
        assert result.steps[1][1] == ""
        assert result.selected_tools == ("PESTEL 分析",)

    def test_plan_temperature(self) -> None:
        fake_llm = _make_fake_llm()
        registry, execution_service = _make_tool_mocks()
        service = _make_service(fake_llm, registry, execution_service)

        asyncio.run(service.plan(_make_state()))
        _, _, _, temperature = fake_llm._workflow_calls[-1]
        assert temperature == 0.2

    def test_plan_retry_round_injects_reflection(self) -> None:
        """重试轮回灌：state 含 reflection 时 prompt 注入修正计划与错误分析（R2-F4）。"""
        from src.application.ports.agent_workflow import ReflectionResult

        fake_llm = _make_fake_llm()
        registry, execution_service = _make_tool_mocks()
        service = _make_service(fake_llm, registry, execution_service)

        state = _make_state(
            reflection=ReflectionResult(
                revised=True,
                error_analysis="工具输出缺少关键约束字段",
                revised_plan="补充约束参数后重新执行工具并复核",
            )
        )
        asyncio.run(service.plan(state))

        prompt, _, _, _ = fake_llm._workflow_calls[-1]
        assert "补充约束参数后重新执行工具并复核" in prompt, "修正计划未注入重试轮 prompt"
        assert "工具输出缺少关键约束字段" in prompt, "错误分析未注入重试轮 prompt"

    def test_plan_first_round_no_reflection_residue(self) -> None:
        """首轮规划 prompt 无反思注入残留。"""
        fake_llm = _make_fake_llm()
        registry, execution_service = _make_tool_mocks()
        service = _make_service(fake_llm, registry, execution_service)

        asyncio.run(service.plan(_make_state()))
        prompt, _, _, _ = fake_llm._workflow_calls[-1]
        assert "上一轮验证失败" not in prompt


# ===================================================================
# execute（阶段级聚合——名字→实体 + 端口调用 + 历史聚合）
# ===================================================================


class TestExecute:
    """执行阶段：按 plan 步骤逐步经工具执行服务（DC-10）。"""

    def test_execute_calls_registry_and_service_via_ports(self) -> None:
        """单工具步：get_tool(tool_name=) 名字→实体 + TES.execute 经端口（DC-10）。"""
        fake_llm = _make_fake_llm()
        registry, execution_service = _make_tool_mocks(tool_name="PESTEL 分析", tool_version="1.2.0")
        service = _make_service(fake_llm, registry, execution_service)

        from src.application.ports.agent_workflow import PlanResult

        state = _make_state(
            plan=PlanResult(
                steps=(
                    ("执行宏观环境分析", "PESTEL 分析", {"scope": "CN"}),
                    ("综合建议", "", {}),
                )
            )
        )
        result = asyncio.run(service.execute(state))

        registry.get_tool.assert_called_once_with(tool_name="PESTEL 分析")
        assert execution_service.execute.await_count == 1
        assert result.tool_trace == ("PESTEL 分析:1.2.0",)
        call_args = execution_service.execute.await_args
        tool_id_arg = call_args.args[0] if call_args.args else call_args.kwargs["tool_id"]
        tool_call_arg = call_args.kwargs.get("tool_call") or call_args.args[1]
        context_arg = call_args.kwargs.get("context") or call_args.args[2]
        assert tool_id_arg == registry.get_tool.return_value.tool_id
        assert isinstance(tool_call_arg, ToolCall)
        assert tool_call_arg.arguments == {"scope": "CN"}
        assert isinstance(context_arg, ExecutionContext)
        assert context_arg.tenant_id == state["context"].tenant_id

    def test_execute_tool_trace_with_version_suffix(self) -> None:
        """工具轨迹含版本后缀（"{tool_name}:{version}"——AC-2 口径）。"""
        fake_llm = _make_fake_llm()
        registry, execution_service = _make_tool_mocks(tool_name="PESTEL 分析", tool_version="1.2.0")
        service = _make_service(fake_llm, registry, execution_service)

        from src.application.ports.agent_workflow import PlanResult

        state = _make_state(plan=PlanResult(steps=(("执行分析", "PESTEL 分析", {}),)))
        result = asyncio.run(service.execute(state))
        assert result.tool_trace == ("PESTEL 分析:1.2.0",)

    def test_execute_zero_tool_steps(self) -> None:
        """零工具步：不调工具执行服务（轨迹空元组合法）。"""
        fake_llm = _make_fake_llm()
        registry, execution_service = _make_tool_mocks()
        service = _make_service(fake_llm, registry, execution_service)

        from src.application.ports.agent_workflow import PlanResult

        state = _make_state(plan=PlanResult(steps=(("直接推理", "", {}),)))
        result = asyncio.run(service.execute(state))
        assert result.tool_trace == ()
        execution_service.execute.assert_not_awaited()

    def test_execute_history_aggregation(self) -> None:
        """历史聚合：读 state 旧 execution 追加合并（R2-F5——重试轮不丢前轮轨迹）。"""
        fake_llm = _make_fake_llm()
        registry, execution_service = _make_tool_mocks(tool_name="PESTEL 分析", tool_version="1.2.0")
        service = _make_service(fake_llm, registry, execution_service)

        from src.application.ports.agent_workflow import ExecutionResult, PlanResult

        previous = ExecutionResult(
            tool_trace=("SWOT 分析:1.0.0",),
            artifacts_snapshot=(("swot", "{}"),),
            step_summaries=("前轮步",),
        )
        state = _make_state(
            plan=PlanResult(steps=(("本轮步", "PESTEL 分析", {}),)),
            execution=previous,
        )
        result = asyncio.run(service.execute(state))
        assert result.tool_trace == ("SWOT 分析:1.0.0", "PESTEL 分析:1.2.0"), "跨轮轨迹应追加合并"
        assert ("swot", "{}") in result.artifacts_snapshot
        assert "前轮步" in result.step_summaries

    def test_execute_unknown_tool_name_raises(self) -> None:
        """未知工具名：get_tool 抛 ToolNotFoundError 原样传播（统一异常体系）。"""
        from src.domain.exceptions import ToolNotFoundError

        fake_llm = _make_fake_llm()
        registry, execution_service = _make_tool_mocks()
        registry.get_tool.side_effect = ToolNotFoundError(tool_name="不存在的工具")
        service = _make_service(fake_llm, registry, execution_service)

        from src.application.ports.agent_workflow import PlanResult

        state = _make_state(plan=PlanResult(steps=(("步", "不存在的工具", {}),)))
        with pytest.raises(ToolNotFoundError):
            asyncio.run(service.execute(state))


# ===================================================================
# package_evidence（终局合成 + 组装覆写 + 失败终态）
# ===================================================================


def _make_terminal_state(verify_passed: bool = True, with_tools: bool = True) -> dict[str, Any]:
    """构造终态前 state（全阶段产物齐备——package_evidence 输入）。"""
    from src.application.ports.agent_workflow import (
        ExecutionResult,
        PerceptionResult,
        PlanResult,
        VerificationResult,
    )

    tool_trace = ("PESTEL 分析:1.2.0",) if with_tools else ()
    return _make_state(
        perception=PerceptionResult(summary="任务摘要：战略分析"),
        plan=PlanResult(steps=(("执行分析", "PESTEL 分析", {}),)),
        execution=ExecutionResult(
            tool_trace=tool_trace,
            artifacts_snapshot=(("pestel_output", '{"P": 0.8}'),),
            step_summaries=("步一完成",),
            citations=("chunk-001",),
        ),
        verification=VerificationResult(
            passed=verify_passed,
            confidence=0.85 if verify_passed else 0.42,
            rationale="结构化检查通过" if verify_passed else "第 3 次验证未通过：约束缺失",
        ),
        retry_count=1,
    )


class TestPackageEvidence:
    """证据打包：九字段组装 + 终局思维链合成（DC-2）。"""

    def test_package_success_terminal(self) -> None:
        """成功终态：PackageOutcome 双产物 + evidence.status=completed。"""
        fake_llm = _make_fake_llm(verify_passed=True)
        registry, execution_service = _make_tool_mocks()
        service = _make_service(fake_llm, registry, execution_service)

        state = _make_terminal_state(verify_passed=True)
        outcome = asyncio.run(service.package_evidence(state))

        from src.application.ports.agent_workflow import PackageOutcome
        from src.domain.value_objects.chain_of_thought import ChainOfThought
        from src.domain.value_objects.task_evidence import TaskEvidencePackage

        assert isinstance(outcome, PackageOutcome)
        assert isinstance(outcome.evidence, TaskEvidencePackage)
        assert isinstance(outcome.chain, ChainOfThought)
        assert outcome.evidence.status == "completed"
        assert outcome.evidence.failure_reason == ""

    def test_input_hash_sha256_of_task(self) -> None:
        """input_hash = sha256(task_description).hexdigest()（口径钉死）。"""
        fake_llm = _make_fake_llm()
        registry, execution_service = _make_tool_mocks()
        service = _make_service(fake_llm, registry, execution_service)

        state = _make_terminal_state()
        outcome = asyncio.run(service.package_evidence(state))
        assert outcome.evidence.input_hash == hashlib.sha256(state["task"].encode()).hexdigest()

    def test_evidence_fields_from_state(self) -> None:
        """九字段组装：task_breakdown←plan / tool_trace+artifacts←execution /
        confidence+rationale←verification / citations 聚合。"""
        fake_llm = _make_fake_llm()
        registry, execution_service = _make_tool_mocks()
        service = _make_service(fake_llm, registry, execution_service)

        state = _make_terminal_state()
        outcome = asyncio.run(service.package_evidence(state))
        evidence = outcome.evidence
        assert evidence.task_breakdown == ("执行分析",)
        assert evidence.tool_trace == ("PESTEL 分析:1.2.0",)
        assert ("pestel_output", '{"P": 0.8}') in evidence.artifacts_snapshot
        assert evidence.confidence == 0.85
        assert "结构化检查" in evidence.confidence_rationale
        assert evidence.citations == ("chunk-001",)

    def test_failed_terminal_evidence(self) -> None:
        """失败终态：status=failed + failure_reason==末次验证 rationale（R1-F17）。"""
        fake_llm = _make_fake_llm(verify_passed=False)
        registry, execution_service = _make_tool_mocks()
        service = _make_service(fake_llm, registry, execution_service)

        state = _make_terminal_state(verify_passed=False)
        outcome = asyncio.run(service.package_evidence(state))
        assert outcome.evidence.status == "failed"
        assert outcome.evidence.failure_reason == "第 3 次验证未通过：约束缺失"
        assert outcome.evidence.confidence == 0.42

    def test_final_synthesis_called_once(self) -> None:
        """终局合成：一次 structured_generate(ChainOfThoughtSchema) + 温度 0.1。"""
        from src.application.services.agent_workflow_schemas import ChainOfThoughtSchema

        fake_llm = _make_fake_llm()
        registry, execution_service = _make_tool_mocks()
        service = _make_service(fake_llm, registry, execution_service)

        state = _make_terminal_state()
        asyncio.run(service.package_evidence(state))

        synthesis_calls = [c for c in fake_llm._workflow_calls if c[2] is ChainOfThoughtSchema]
        assert len(synthesis_calls) == 1, "终局合成应恰好一次"
        prompt, system_prompt, _, temperature = synthesis_calls[0]
        assert temperature == 0.1
        assert "任务摘要：战略分析" in prompt, "终局 prompt 应携带感知摘要"
        assert "结构化检查通过" in prompt, "终局 prompt 应携带验证结论"

    def test_final_synthesis_prompt_includes_reflection_material(self) -> None:
        """重试路径终局合成 prompt 携带反思修正素材（F1——「总结修正过程」须有素材，
        缺失即逼 LLM 虚构违反核心约束；按 ChainOfThoughtSchema 身份选调用，
        与 plan 重试轮回灌的同一素材文本区分面互不污染）。"""
        from src.application.ports.agent_workflow import ReflectionResult
        from src.application.services.agent_workflow_schemas import ChainOfThoughtSchema

        fake_llm = _make_fake_llm()
        registry, execution_service = _make_tool_mocks()
        service = _make_service(fake_llm, registry, execution_service)

        state = _make_terminal_state(verify_passed=False)
        state["reflection"] = ReflectionResult(
            revised=False,
            error_analysis="三次工具执行均缺关键约束字段",
            revised_plan="无可用修正路径（根本性障碍）",
        )
        state["retry_count"] = 2
        asyncio.run(service.package_evidence(state))

        synthesis_calls = [c for c in fake_llm._workflow_calls if c[2] is ChainOfThoughtSchema]
        assert len(synthesis_calls) == 1
        prompt = synthesis_calls[0][0]
        assert "三次工具执行均缺关键约束字段" in prompt, "终局 prompt 应携带错误分析素材"
        assert "无可用修正路径（根本性障碍）" in prompt, "终局 prompt 应携带修正计划素材"
        assert "历经 2 次重试" in prompt, "终局 prompt 应携带重试次数"

    def test_final_synthesis_no_reflection_section_on_first_pass(self) -> None:
        """成功路径（无反思轮）终局 prompt 无「反思修正」分节（防无素材虚构）。"""
        from src.application.services.agent_workflow_schemas import ChainOfThoughtSchema

        fake_llm = _make_fake_llm()
        registry, execution_service = _make_tool_mocks()
        service = _make_service(fake_llm, registry, execution_service)

        state = _make_terminal_state(verify_passed=True)
        state.pop("retry_count", None)
        asyncio.run(service.package_evidence(state))

        synthesis_calls = [c for c in fake_llm._workflow_calls if c[2] is ChainOfThoughtSchema]
        prompt = synthesis_calls[0][0]
        assert "- 反思修正（历经" not in prompt, "无反思轮时不应有反思修正分节（锚=分节行前缀，要求段静态文本不算）"

    def test_chain_assembly_overwrite(self) -> None:
        """组装覆写（DC-2 判别力核心）：input_summary←perceive、tools_used←真实
        轨迹（Fake 回声相异值被覆写）、reflection/constraints_check/final_answer←
        终局合成。"""
        fake_llm = _make_fake_llm(chain_echo_tools=("fake-echo:not-real",))
        registry, execution_service = _make_tool_mocks()
        service = _make_service(fake_llm, registry, execution_service)

        state = _make_terminal_state()
        outcome = asyncio.run(service.package_evidence(state))
        chain = outcome.chain
        assert chain.input_summary == "任务摘要：战略分析", "input_summary 应覆写为感知产物"
        assert chain.tools_used == ("PESTEL 分析:1.2.0",), "tools_used 应覆写为真实轨迹"
        assert "fake-echo" not in "".join(chain.tools_used), "Fake 回声值泄漏"
        assert chain.reflection == "Fake 回声反思（终局合成产物）"
        assert chain.constraints_check == "Fake 回声约束（终局合成产物）"
        assert chain.final_answer == '{"answer": "终局综合答案"}'


# ===================================================================
# 异常契约（444 包装 / 透传 / 守卫 / 242→445 改写）
# ===================================================================


class TestErrorContract:
    """LLM 异常包装 444 携带 phase + 透传纪律 + isinstance 守卫 + 445 改写。"""

    def test_llm_error_wrapped_as_444_with_phase(self) -> None:
        """LLM 族异常按阶段包装 444（phase 为同码多因区分锚点）。"""
        from src.domain.exceptions import LLMAPIError
        from src.domain.exceptions.agent_exceptions import AgentWorkflowError

        fake_llm = _make_fake_llm(
            llm_error_by_schema={
                __import__(
                    "src.application.services.agent_workflow_schemas", fromlist=["PerceptionSchema"]
                ).PerceptionSchema: LLMAPIError(message="upstream 500"),
            }
        )
        registry, execution_service = _make_tool_mocks()
        service = _make_service(fake_llm, registry, execution_service)

        with pytest.raises(AgentWorkflowError) as exc_info:
            asyncio.run(service.perceive(_make_state()))
        assert exc_info.value.code == "EXCEPTION_444"
        assert exc_info.value.context["phase"] == "perceive"

    @pytest.mark.parametrize(
        "phase,schema_name",
        [
            ("perceive", "PerceptionSchema"),
            ("plan", "PlanSchema"),
            ("verify", "VerificationSchema"),
            ("reflect", "ReflectionSchema"),
            ("package", "ChainOfThoughtSchema"),
        ],
    )
    def test_444_context_carries_agent_id_all_phases(self, phase: str, schema_name: str) -> None:
        """五阶段（全 _structured_call 调用面）444 context 携真实 agent_id——
        异常契约 {agent_id, phase, reason} 三键完备（参数化防漏位——某阶段
        调用点漏传 agent_id 时该参数项即红）。"""
        import src.application.services.agent_workflow_schemas as schemas_mod
        from src.application.ports.agent_workflow import ReflectionResult
        from src.domain.exceptions import LLMAPIError
        from src.domain.exceptions.agent_exceptions import AgentWorkflowError

        schema_cls = getattr(schemas_mod, schema_name)
        fake_llm = _make_fake_llm(llm_error_by_schema={schema_cls: LLMAPIError(message="upstream 500")})
        registry, execution_service = _make_tool_mocks()
        service = _make_service(fake_llm, registry, execution_service)

        state = _make_state()
        if phase == "reflect":
            state["verification"] = None
        if phase == "package":
            state["reflection"] = ReflectionResult(revised=True, error_analysis="e", revised_plan="p")

        method = {
            "perceive": service.perceive,
            "plan": service.plan,
            "verify": service.verify,
            "reflect": service.reflect,
            "package": service.package_evidence,
        }[phase]
        with pytest.raises(AgentWorkflowError) as exc_info:
            asyncio.run(method(state))
        assert exc_info.value.context["phase"] == phase
        assert exc_info.value.context["agent_id"] == state["agent_id"], (
            f"{phase} 阶段 444 context 应携带真实 agent_id（非空串）"
        )

    def test_llm_config_error_passthrough(self) -> None:
        """LLMConfigError 透传不包装（4-5 辩论纪律先例）。"""
        from src.application.services.agent_workflow_schemas import PerceptionSchema
        from src.domain.exceptions import LLMConfigError

        fake_llm = _make_fake_llm(llm_error_by_schema={PerceptionSchema: LLMConfigError(message="cfg")})
        registry, execution_service = _make_tool_mocks()
        service = _make_service(fake_llm, registry, execution_service)

        with pytest.raises(LLMConfigError):
            asyncio.run(service.perceive(_make_state()))

    def test_cancelled_error_passthrough(self) -> None:
        """CancelledError 透传（父任务取消语义保护）。"""
        from src.application.services.agent_workflow_schemas import PerceptionSchema

        fake_llm = _make_fake_llm(llm_error_by_schema={PerceptionSchema: asyncio.CancelledError()})
        registry, execution_service = _make_tool_mocks()
        service = _make_service(fake_llm, registry, execution_service)

        with pytest.raises(asyncio.CancelledError):
            asyncio.run(service.perceive(_make_state()))

    def test_non_schema_return_guarded_as_444(self) -> None:
        """structured_generate 返回非 Schema 实例 → 444（red_blue L350-356 先例）。"""
        from src.domain.exceptions.agent_exceptions import AgentWorkflowError

        fake_llm = _make_fake_llm(non_schema_return=True)
        registry, execution_service = _make_tool_mocks()
        service = _make_service(fake_llm, registry, execution_service)

        with pytest.raises(AgentWorkflowError) as exc_info:
            asyncio.run(service.perceive(_make_state()))
        assert exc_info.value.code == "EXCEPTION_444"

    def test_vo_validation_error_rewritten_as_445(self) -> None:
        """VO 构造 EntityValidationError(242) 捕获改写 445 携 missing_fields（三层次序②）。

        经 model_construct 穿透 Schema 校验构造空白字段（模拟 Schema 层失守
        的深层缺陷——242 在 VO 层拦截后由服务改写 445）。
        """
        from src.application.services.agent_workflow_schemas import ChainOfThoughtSchema
        from src.domain.exceptions.agent_exceptions import ChainOfThoughtValidationError

        broken_echo = ChainOfThoughtSchema.model_construct(
            input_summary="a",
            reflection="  ",
            tools_used=[],
            constraints_check="c",
            final_answer="{}",
        )
        fake_llm = _make_fake_llm(chain_echo_instance=broken_echo)
        registry, execution_service = _make_tool_mocks()
        service = _make_service(fake_llm, registry, execution_service)

        with pytest.raises(ChainOfThoughtValidationError) as exc_info:
            asyncio.run(service.package_evidence(_make_terminal_state()))
        assert exc_info.value.code == "EXCEPTION_445"
        assert "reflection" in exc_info.value.context["missing_fields"]


# ===================================================================
# Story 5-5 追加：execute 工具位白名单全量预检（第五依赖接线）
# ===================================================================


class TestToolAllowlistPreflight:
    """execute 工具位预检契约（Story 5.5——进执行循环前 plan 全量工具名预检）。

    all-or-nothing fail-closed: 任一白名单外工具 449 先于首个工具执行（杜绝
    「前 N 步已执行、第 N+1 步才拒」的部分执行副作用）；449 先于工具存在性
    （白名单外名不炸 ToolNotFound 而炸 449——判别锚，guard 不查注册表）。
    """

    def _make_guard(self, denied_tools: tuple[str, ...]) -> Any:
        """构造守卫替身（denied_tools 内工具名抛 449——白名单外模拟）。"""
        from unittest.mock import AsyncMock

        from src.application.ports.isolation_guard import IsolationGuardPort
        from src.domain.exceptions import IsolationOperationForbiddenError

        guard = AsyncMock(spec=IsolationGuardPort)

        async def _ensure_tool(agent_id: Any, tool_name: str) -> None:
            if tool_name in denied_tools:
                raise IsolationOperationForbiddenError(
                    agent_id=str(agent_id), operation="execute", reason=f"tool_not_in_allowlist:{tool_name}"
                )

        guard.ensure_tool_access = AsyncMock(side_effect=_ensure_tool)
        return guard

    def _plan_state(self, tool_names: tuple[str, ...], agent_id: str) -> dict[str, Any]:
        """构造携带 plan 产物的 state（steps 三元组直供——既有 TestExecute 形态）。"""
        from src.application.ports.agent_workflow import PlanResult

        return _make_state(
            agent_id=agent_id,
            plan=PlanResult(steps=tuple((f"步骤 {index + 1}", tool_name, {}) for index, tool_name in enumerate(tool_names))),
        )

    def test_preflight_denies_before_first_tool_execution(self) -> None:
        """多工具 plan 且其一白名单外 → 449 向上抛且 get_tool 零调用
        （预检先于首个工具执行——部分执行副作用杜绝；白名单外名不炸
        ToolNotFound 而炸 449——判别锚）。"""
        from src.domain.exceptions import IsolationOperationForbiddenError

        fake_llm = _make_fake_llm()
        registry, execution_service = _make_tool_mocks()
        guard = self._make_guard(denied_tools=("绝对不在白名单的工具",))
        service = _make_service(fake_llm, registry, execution_service, isolation_guard=guard)
        state = self._plan_state(("PESTEL 分析", "绝对不在白名单的工具", "SWOT-TOWS"), str(uuid.uuid4()))

        with pytest.raises(IsolationOperationForbiddenError) as exc_info:
            asyncio.run(service.execute(state))
        assert exc_info.value.code == "EXCEPTION_449"
        assert registry.get_tool.call_count == 0, "预检须先于 get_tool（449 先于工具存在性——判别锚）"
        assert execution_service.execute.await_count == 0

    def test_preflight_calls_guard_for_every_tool_name_exactly_once(self) -> None:
        """全白名单多工具 plan: ensure_tool_access 对全部工具名逐名调用且恰一遍
        （空工具名步骤跳过——直接推理步不进预检）。"""
        fake_llm = _make_fake_llm()
        registry, execution_service = _make_tool_mocks()
        guard = self._make_guard(denied_tools=())
        service = _make_service(fake_llm, registry, execution_service, isolation_guard=guard)
        state = self._plan_state(("PESTEL 分析", "", "SWOT-TOWS"), "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0")

        asyncio.run(service.execute(state))
        called_names = [call.args[1] for call in guard.ensure_tool_access.await_args_list]
        assert called_names == ["PESTEL 分析", "SWOT-TOWS"], "预检逐名恰一遍（空工具名步骤跳过）"

    def test_preflight_agent_id_uuid_conversion(self) -> None:
        """state['agent_id'] 是 str 形态——进循环前 UUID 显式转换一次断言。"""
        fake_llm = _make_fake_llm()
        registry, execution_service = _make_tool_mocks()
        guard = self._make_guard(denied_tools=())
        service = _make_service(fake_llm, registry, execution_service, isolation_guard=guard)
        state = self._plan_state(("PESTEL 分析",), "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0")

        asyncio.run(service.execute(state))
        call = guard.ensure_tool_access.await_args_list[0]
        assert isinstance(call.args[0], uuid.UUID), "guard 入参必须 UUID 实例（state str 形态转换）"
        assert call.args[0] == uuid.UUID("0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0")

    def test_all_allowlisted_plan_executes_normally(self) -> None:
        """全部白名单内 → 预检放行且后续执行正常（既有主链零回归锚）。"""
        fake_llm = _make_fake_llm()
        registry, execution_service = _make_tool_mocks()
        guard = self._make_guard(denied_tools=())
        service = _make_service(fake_llm, registry, execution_service, isolation_guard=guard)
        state = self._plan_state(("PESTEL 分析", ""), str(uuid.uuid4()))

        result = asyncio.run(service.execute(state))
        registry.get_tool.assert_called_once_with(tool_name="PESTEL 分析")
        assert result.tool_trace == ("PESTEL 分析:1.2.0",)

    def test_no_tool_steps_zero_guard_calls(self) -> None:
        """无工具名步骤（直接推理 plan）→ guard 零调用。"""
        fake_llm = _make_fake_llm()
        registry, execution_service = _make_tool_mocks()
        guard = self._make_guard(denied_tools=())
        service = _make_service(fake_llm, registry, execution_service, isolation_guard=guard)
        state = self._plan_state(("", ""), str(uuid.uuid4()))

        asyncio.run(service.execute(state))
        guard.ensure_tool_access.assert_not_awaited()
        registry.get_tool.assert_not_called()
