"""SingleAgentWorkflow 六阶段图单元测试（Story 5-3 — 单 Agent 标准工作流）

覆盖六节点图与条件边编排契约（DC-1 节点适配器模式）：
- 图工厂编译产物 nodes/edges 断言（六节点 + 节点名 package_evidence——分支键
  package 经 path_map 映射，命名禁混用）
- WorkflowAgentState 字段（agent_id/task/context/phase 产物/retry_count/
  executed_phases 轨迹——末元素钉死 "package"）
- 四路径执行（Fake 服务替身驱动）：
  ① 正常路径 perceive→plan→execute→verify→[pass]→package_evidence
  ② 验证失败→reflect→plan 重试→成功（retry_count 语义：reflect 执行一次=
     消耗一次重试——适配器递增；plan 总执行 ≤3）
  ③ 重试上限耗尽→package_evidence（status=failed 完成态）
  ④ revised=False 早退（reflect 判定不可修正且未耗尽→直接 package(failed)）
- 节点适配器形态：每节点返回 dict 部分更新——谓词键写入者
  （verification_passed←verify 适配器 / revised+retry_count←reflect 适配器 /
  executed_phases←各适配器 append / confidence←verify 适配器）
- MAX_RETRIES=2 模块常量（AC-1 口径锚）

Fake 服务替身：Mock(spec=AgentWorkflowServicePort)——分派键 = 方法名（与
断言锚「state 产物内容」独立信号）。

Run with:
    poetry run pytest tests/unit/infrastructure/agent_orch/test_single_agent_workflow_graph.py -v
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any
from unittest.mock import Mock

from src.application.ports.agent_workflow import (
    AgentWorkflowServicePort,
    ExecutionResult,
    PackageOutcome,
    PerceptionResult,
    PlanResult,
    ReflectionResult,
    VerificationResult,
    WorkflowContext,
)
from src.domain.value_objects.chain_of_thought import ChainOfThought
from src.domain.value_objects.task_evidence import TaskEvidencePackage


def _make_context() -> WorkflowContext:
    """构造最小 WorkflowContext（图执行的 context 键初值）。"""
    return WorkflowContext(
        system_prompt="## 身份档案（IDENTITY）\n\nCEO",
        tools_l1=(),
        task="分析新能源汽车行业进入战略",
        tenant_id=uuid.uuid4(),
        assembled_context_tokens=100,
    )


def _make_evidence(status: str = "completed") -> TaskEvidencePackage:
    """构造终态证据包（成功/失败终态共用工厂）。"""
    return TaskEvidencePackage(
        input_hash="a" * 64,
        task_breakdown=("执行分析",),
        tool_trace=(),
        artifacts_snapshot=(),
        confidence=0.85,
        confidence_rationale="结构化检查通过",
        citations=(),
        status=status,
        failure_reason="" if status == "completed" else "第 3 次验证未通过：约束缺失",
    )


def _make_chain() -> ChainOfThought:
    """构造终局思维链。"""
    return ChainOfThought(
        input_summary="任务摘要",
        reflection="一次通过",
        tools_used=(),
        constraints_check="约束符合",
        final_answer='{"answer": "ok"}',
    )


def _make_fake_service(
    *,
    verify_passed_sequence: list[bool] | None = None,
    reflect_revised: bool = True,
) -> Any:
    """六阶段服务 Fake（分派键 = 方法名——与 state 产物断言锚独立）。

    Args:
        verify_passed_sequence: verify 返回序列（按调用次消耗；耗尽取末值）
        reflect_revised: reflect 返回的 revised 值
    """
    service = Mock(spec=AgentWorkflowServicePort)
    verify_call = {"count": 0}

    async def _perceive(state: dict[str, Any]) -> PerceptionResult:
        return PerceptionResult(summary="任务摘要：战略分析")

    async def _plan(state: dict[str, Any]) -> PlanResult:
        return PlanResult(steps=(("执行分析", "PESTEL 分析", {}),), selected_tools=("PESTEL 分析",))

    async def _execute(state: dict[str, Any]) -> ExecutionResult:
        previous: ExecutionResult | None = state.get("execution")
        return ExecutionResult(
            tool_trace=(*(previous.tool_trace if previous else ()), "PESTEL 分析:1.2.0"),
            step_summaries=(f"第 {state.get('retry_count', 0) + 1} 轮执行",),
        )

    async def _verify(state: dict[str, Any]) -> VerificationResult:
        verify_call["count"] += 1
        if verify_passed_sequence:
            index = min(verify_call["count"], len(verify_passed_sequence)) - 1
            passed = verify_passed_sequence[index]
        else:
            passed = True
        return VerificationResult(
            passed=passed,
            confidence=0.85 if passed else 0.42,
            rationale="结构化检查通过" if passed else "验证未通过",
        )

    async def _reflect(state: dict[str, Any]) -> ReflectionResult:
        return ReflectionResult(
            revised=reflect_revised,
            error_analysis="根因",
            revised_plan="修正计划" if reflect_revised else "",
        )

    async def _package(state: dict[str, Any]) -> PackageOutcome:
        verification: VerificationResult | None = state.get("verification")
        status = "completed" if (verification and verification.passed) else "failed"
        return PackageOutcome(evidence=_make_evidence(status), chain=_make_chain())

    service.perceive.side_effect = _perceive
    service.plan.side_effect = _plan
    service.execute.side_effect = _execute
    service.verify.side_effect = _verify
    service.reflect.side_effect = _reflect
    service.package_evidence.side_effect = _package
    return service


def _invoke_graph(service: Any, **state_extra: Any) -> dict[str, Any]:
    """编译图并同步执行（ainvoke 终态 state 返回）。"""
    from src.infrastructure.agent_orch.graphs.single_agent_workflow_graph import (
        build_single_agent_workflow_graph,
    )

    compiled = build_single_agent_workflow_graph(service)
    initial: dict[str, Any] = {
        "agent_id": str(uuid.uuid4()),
        "task": "分析新能源汽车行业进入战略",
        "context": _make_context(),
        "retry_count": 0,
    }
    initial.update(state_extra)
    return asyncio.run(compiled.ainvoke(initial))


# ===================================================================
# 图工厂结构（nodes/edges/常量）
# ===================================================================


class TestGraphStructure:
    """图工厂编译产物与模块常量断言。"""

    def test_six_nodes_registered(self) -> None:
        """六节点齐备（节点名 package_evidence——分支键 package 经 path_map 映射）。"""
        from src.infrastructure.agent_orch.graphs.single_agent_workflow_graph import (
            build_single_agent_workflow_graph,
        )

        service = _make_fake_service()
        graph = build_single_agent_workflow_graph(service)
        compiled = graph
        node_names = set(compiled.get_graph().nodes.keys())
        expected = {"perceive", "plan", "execute", "verify", "reflect", "package_evidence"}
        assert expected <= node_names, f"六节点缺失: {expected - node_names}"

    def test_max_retries_constant(self) -> None:
        """MAX_RETRIES=2 模块常量（AC-1 重试上限口径锚——R3-F11）。"""
        from src.infrastructure.agent_orch.graphs.single_agent_workflow_graph import MAX_RETRIES

        assert MAX_RETRIES == 2

    def test_state_schema_fields(self) -> None:
        """WorkflowAgentState 字段齐备（含 executed_phases/evidence/chain/retry_count）。"""
        import typing

        from src.infrastructure.agent_orch.schemas import WorkflowAgentState

        hints = typing.get_type_hints(WorkflowAgentState)
        for field_name in (
            "agent_id",
            "task",
            "context",
            "perception",
            "plan",
            "execution",
            "verification",
            "reflection",
            "retry_count",
            "revised",
            "verification_passed",
            "confidence",
            "executed_phases",
            "evidence",
            "chain",
        ):
            assert field_name in hints, f"State 缺字段: {field_name}"


# ===================================================================
# 路径①：正常路径（一次通过）
# ===================================================================


class TestHappyPath:
    """正常路径：perceive→plan→execute→verify→[pass]→package_evidence。"""

    def test_happy_path_phases(self) -> None:
        service = _make_fake_service(verify_passed_sequence=[True])
        state = _invoke_graph(service)
        assert state["executed_phases"] == ["perceive", "plan", "execute", "verify", "package"]
        assert state["retry_count"] == 0

    def test_happy_path_terminal_products(self) -> None:
        """终态产物：evidence/chain 拆写入 state（PackageOutcome 拆写）。"""
        service = _make_fake_service(verify_passed_sequence=[True])
        state = _invoke_graph(service)
        assert isinstance(state["evidence"], TaskEvidencePackage)
        assert isinstance(state["chain"], ChainOfThought)
        assert state["evidence"].status == "completed"
        assert state["confidence"] == 0.85
        assert state["verification_passed"] is True

    def test_predicate_keys_written_by_adapters(self) -> None:
        """谓词键写入者：verify 适配器写 verification_passed + confidence。"""
        service = _make_fake_service(verify_passed_sequence=[True])
        state = _invoke_graph(service)
        assert state["verification_passed"] is True
        assert state["confidence"] == 0.85

    def test_service_not_called_for_reflect_on_pass(self) -> None:
        """验证通过时 reflect 不执行。"""
        service = _make_fake_service(verify_passed_sequence=[True])
        _invoke_graph(service)
        service.reflect.assert_not_called()


# ===================================================================
# 路径②：验证失败→反思→重试→成功
# ===================================================================


class TestReflectRetryLoop:
    """反思重试路径：fail→reflect→plan→execute→verify→[pass]→package。"""

    def test_retry_then_success_phases(self) -> None:
        service = _make_fake_service(verify_passed_sequence=[False, True])
        state = _invoke_graph(service)
        assert state["executed_phases"] == [
            "perceive",
            "plan",
            "execute",
            "verify",
            "reflect",
            "plan",
            "execute",
            "verify",
            "package",
        ]
        assert state["retry_count"] == 1, "reflect 执行一次即消耗一次重试"
        assert state["evidence"].status == "completed"

    def test_plan_total_executions_bounded(self) -> None:
        """plan 总执行次数 ≤3（初始 1 + 重试 2——reflect 递增 + <= 谓词）。"""
        service = _make_fake_service(verify_passed_sequence=[False, False, True])
        state = _invoke_graph(service)
        plan_count = state["executed_phases"].count("plan")
        assert plan_count == 3
        assert state["retry_count"] == 2

    def test_execution_trace_accumulates_across_rounds(self) -> None:
        """execution 轨迹跨轮累积（Fake 服务聚合 + 适配器直写全量）。"""
        service = _make_fake_service(verify_passed_sequence=[False, True])
        state = _invoke_graph(service)
        assert state["execution"].tool_trace == ("PESTEL 分析:1.2.0", "PESTEL 分析:1.2.0"), "两轮执行应累积"


# ===================================================================
# 路径③：重试上限耗尽→失败完成态
# ===================================================================


class TestRetryExhausted:
    """重试耗尽路径：恒失败+恒可修正→满 3 次 plan→package(failed)。"""

    def test_exhausted_phases_and_retry_count(self) -> None:
        service = _make_fake_service(verify_passed_sequence=None)

        # 恒失败：覆写 verify 序列为全 False
        async def _always_fail(state: dict[str, Any]) -> VerificationResult:
            return VerificationResult(passed=False, confidence=0.42, rationale="恒失败")

        service.verify.side_effect = _always_fail

        state = _invoke_graph(service)
        assert state["executed_phases"].count("plan") == 3, "恒可修正应触发满 3 次 plan"
        # retry_count 终值 3 = reflect 总执行数（第三次 reflect 判定耗尽不再入 plan；
        # 重试次数 2 = plan(2)+plan(3)——R2 推演留痕「最坏路径 retry_count 终值 3」）
        assert state["retry_count"] == 3
        assert len(state["executed_phases"]) == 14, "最坏路径 executed_phases=14 元素"
        assert state["executed_phases"][-1] == "package"
        assert state["evidence"].status == "failed"


# ===================================================================
# 路径④：revised=False 不可修正早退
# ===================================================================


class TestNotRevisableEarlyExit:
    """第四路径：reflect 判定不可修正（未耗尽）→直接 package(failed) 早退。"""

    def test_early_exit_phases(self) -> None:
        service = _make_fake_service(verify_passed_sequence=None, reflect_revised=False)

        async def _always_fail(state: dict[str, Any]) -> VerificationResult:
            return VerificationResult(passed=False, confidence=0.42, rationale="不可修正失败")

        service.verify.side_effect = _always_fail

        state = _invoke_graph(service)
        assert state["executed_phases"] == [
            "perceive",
            "plan",
            "execute",
            "verify",
            "reflect",
            "package",
        ], "不可修正应直接早退（不再入 plan）"
        assert state["retry_count"] == 1, "reflect 执行一次即消耗一次重试（未耗尽）"
        assert state["evidence"].status == "failed"


# ===================================================================
# agent_id 贯通（state 透传）
# ===================================================================


class TestAgentIdThreading:
    """agent_id 经 state 贯通（引擎收敛位在 test_langgraph_engine.py 覆盖）。"""

    def test_agent_id_preserved_in_state(self) -> None:
        service = _make_fake_service(verify_passed_sequence=[True])
        agent_id = str(uuid.uuid4())
        state = _invoke_graph(service, agent_id=agent_id)
        assert state["agent_id"] == agent_id
