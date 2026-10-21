"""LangGraphEngine 单元测试

验证 submit_graph/get_graph_status、状态映射、AgentEnginePort 一致性
使用 mock LangGraph SDK，不启动真实 server
"""

from __future__ import annotations

import time
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from src.domain.exceptions import ValidationError
from src.domain.value_objects.flow_status import FlowStatus
from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
from src.infrastructure.config.langgraph import LangGraphConfig


@pytest.fixture
def mock_event_publisher() -> AsyncMock:
    publisher = AsyncMock()
    publish_result = AsyncMock()
    publish_result.is_full_failure = False
    publisher.publish = AsyncMock(return_value=publish_result)
    return publisher


@pytest.fixture
def config() -> LangGraphConfig:
    return LangGraphConfig()


@pytest.fixture
def engine(config: LangGraphConfig, mock_event_publisher: AsyncMock) -> LangGraphEngine:
    return LangGraphEngine(config, mock_event_publisher)


class TestLangGraphEngineProtocolCompliance:
    """LangGraphEngine 满足 AgentEnginePort Protocol"""

    def test_is_agent_engine_port(self, engine: LangGraphEngine) -> None:
        from src.domain.ports.agent_engine import AgentEnginePort

        assert isinstance(engine, AgentEnginePort)


class TestLangGraphEngineSubmitGraph:
    """submit_graph 测试"""

    async def test_submit_graph_returns_string_id(self, engine: LangGraphEngine) -> None:
        """submit_graph 应返回 graph_run_id 字符串"""
        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(
            return_value={
                "task_description": "test task",
                "agent_role": "analyst",
                "analysis_result": "分析完成",
                "synthesis_result": "综合完成",
            }
        )

        with patch.object(engine, "_build_graph", return_value=mock_compiled):
            result = await engine.submit_graph(
                "BasicAgent",
                {"task_description": "test task", "agent_role": "analyst"},
            )

        assert isinstance(result, str)
        assert len(result) > 0

    async def test_submit_graph_rejects_empty_graph_name(self, engine: LangGraphEngine) -> None:
        """空 graph_name 应抛出 ValueError"""
        with pytest.raises(ValidationError, match="graph_name"):
            await engine.submit_graph("", {})

    async def test_submit_graph_rejects_empty_parameters(self, engine: LangGraphEngine) -> None:
        """空 parameters 应抛出 ValueError"""
        with pytest.raises(ValidationError, match="parameters"):
            await engine.submit_graph("BasicAgent", {})

    async def test_submit_graph_runtime_error_on_exception(self, engine: LangGraphEngine) -> None:
        """SDK 异常应转换为 RuntimeError"""
        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(side_effect=Exception("SDK error"))

        with patch.object(engine, "_build_graph", return_value=mock_compiled):
            with pytest.raises(RuntimeError, match="提交状态图失败"):
                await engine.submit_graph("BasicAgent", {"task_description": "test"})


class TestLangGraphEngineEventPublishing:
    """AgentDecided 事件发布测试"""

    async def test_submit_graph_publishes_agent_decided(self, engine: LangGraphEngine, mock_event_publisher: AsyncMock) -> None:
        """submit_graph 完成后应发布 AgentDecided 事件"""
        from src.domain.events.agent_events import AgentDecided

        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(
            return_value={
                "task_description": "test",
                "agent_role": "analyst",
                "analysis_result": "分析完成",
                "synthesis_result": "综合完成",
            }
        )

        with patch.object(engine, "_build_graph", return_value=mock_compiled):
            await engine.submit_graph("BasicAgent", {"task_description": "test"})

        mock_event_publisher.publish.assert_called_once()
        event = mock_event_publisher.publish.call_args[0][0]
        assert isinstance(event, AgentDecided)
        assert event.confidence == 0.9

    async def test_submit_graph_no_event_on_failure(self, engine: LangGraphEngine, mock_event_publisher: AsyncMock) -> None:
        """submit_graph 失败时不应发布事件"""
        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(side_effect=Exception("SDK error"))

        with patch.object(engine, "_build_graph", return_value=mock_compiled):
            with pytest.raises(RuntimeError):
                await engine.submit_graph("BasicAgent", {"task_description": "test"})

        mock_event_publisher.publish.assert_not_called()

    async def test_submit_graph_remains_completed_on_publish_exception(
        self, engine: LangGraphEngine, mock_event_publisher: AsyncMock
    ) -> None:
        """事件发布异常不应覆写 COMPLETED 状态"""
        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(
            return_value={
                "task_description": "test",
                "agent_role": "analyst",
                "analysis_result": "分析完成",
                "synthesis_result": "综合完成",
            }
        )
        mock_event_publisher.publish = AsyncMock(side_effect=ConnectionError("network"))

        with patch.object(engine, "_build_graph", return_value=mock_compiled):
            run_id = await engine.submit_graph("BasicAgent", {"task_description": "test"})

        status = await engine.get_graph_status(run_id)
        assert status == FlowStatus.COMPLETED

    async def test_submit_graph_handles_publish_returning_none(
        self, engine: LangGraphEngine, mock_event_publisher: AsyncMock
    ) -> None:
        """publish 返回 None 时应记录警告但不影响状态"""
        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(
            return_value={
                "task_description": "test",
                "agent_role": "analyst",
                "analysis_result": "分析完成",
                "synthesis_result": "综合完成",
            }
        )
        mock_event_publisher.publish = AsyncMock(return_value=None)

        with patch.object(engine, "_build_graph", return_value=mock_compiled):
            run_id = await engine.submit_graph("BasicAgent", {"task_description": "test"})

        status = await engine.get_graph_status(run_id)
        assert status == FlowStatus.COMPLETED

    async def test_submit_graph_logs_warning_on_full_failure(
        self, engine: LangGraphEngine, mock_event_publisher: AsyncMock
    ) -> None:
        """publish 返回 is_full_failure=True 时应记录警告"""
        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(
            return_value={
                "task_description": "test",
                "agent_role": "analyst",
                "analysis_result": "分析完成",
                "synthesis_result": "综合完成",
            }
        )
        publish_result = AsyncMock()
        publish_result.is_full_failure = True
        mock_event_publisher.publish = AsyncMock(return_value=publish_result)

        with patch.object(engine, "_build_graph", return_value=mock_compiled):
            run_id = await engine.submit_graph("BasicAgent", {"task_description": "test"})

        status = await engine.get_graph_status(run_id)
        assert status == FlowStatus.COMPLETED


class TestLangGraphEngineGetGraphStatus:
    """get_graph_status 测试"""

    async def test_get_graph_status_completed(self, engine: LangGraphEngine) -> None:
        """已完成的 run_id 返回 COMPLETED"""
        run_id = str(uuid.uuid4())
        # 模拟 submit_graph 将结果存入 _runs
        engine._runs[run_id] = (FlowStatus.COMPLETED, 0.0, None)

        status = await engine.get_graph_status(run_id)
        assert status == FlowStatus.COMPLETED

    async def test_get_graph_status_failed(self, engine: LangGraphEngine) -> None:
        """失败的 run_id 返回 FAILED"""
        run_id = str(uuid.uuid4())
        engine._runs[run_id] = (FlowStatus.FAILED, 0.0, None)

        status = await engine.get_graph_status(run_id)
        assert status == FlowStatus.FAILED

    async def test_get_graph_status_rejects_empty_id(self, engine: LangGraphEngine) -> None:
        """空 graph_run_id 应抛出 ValueError"""
        with pytest.raises(ValidationError, match="graph_run_id"):
            await engine.get_graph_status("")

    async def test_get_graph_status_unknown_id_returns_failed(self, engine: LangGraphEngine) -> None:
        """未知 run_id 返回 FAILED"""
        status = await engine.get_graph_status(str(uuid.uuid4()))
        assert status == FlowStatus.FAILED


class TestLangGraphEngineRunsEviction:
    """_runs 字典淘汰机制测试"""

    async def test_cleanup_evicts_expired_entries(self, engine: LangGraphEngine) -> None:
        """TTL 过期的记录应被淘汰"""
        run_id = str(uuid.uuid4())
        # 插入一条基于 monotonic 时钟的过期记录（确保 now - ts > TTL）
        expired_ts = time.monotonic() - engine._RUNS_TTL_SECONDS - 1
        engine._runs[run_id] = (FlowStatus.COMPLETED, expired_ts, None)

        # 触发一次 submit_graph 以执行 _cleanup_runs
        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(
            return_value={
                "task_description": "t",
                "agent_role": "a",
                "analysis_result": "r",
                "synthesis_result": "s",
            }
        )
        with patch.object(engine, "_build_graph", return_value=mock_compiled):
            await engine.submit_graph("BasicAgent", {"task_description": "test"})

        # 过期记录应被淘汰
        assert run_id not in engine._runs

    async def test_cleanup_keeps_fresh_entries(self, engine: LangGraphEngine) -> None:
        """未过期的记录应保留"""
        run_id = str(uuid.uuid4())
        engine._runs[run_id] = (FlowStatus.COMPLETED, time.monotonic(), None)

        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(
            return_value={
                "task_description": "t",
                "agent_role": "a",
                "analysis_result": "r",
                "synthesis_result": "s",
            }
        )
        with patch.object(engine, "_build_graph", return_value=mock_compiled):
            await engine.submit_graph("BasicAgent", {"task_description": "test"})

        # 新鲜记录应保留
        assert run_id in engine._runs

    async def test_max_size_fifo_eviction(self) -> None:
        """超过 max_size 时 FIFO 淘汰最早记录"""
        config = LangGraphConfig()
        publisher = AsyncMock()
        publish_result = AsyncMock()
        publish_result.is_full_failure = False
        publisher.publish = AsyncMock(return_value=publish_result)
        engine = LangGraphEngine(config, publisher)
        engine._MAX_RUNS = 3

        now = time.monotonic()
        # 手动填满 _runs 到 max_size
        engine._runs["old-1"] = (FlowStatus.COMPLETED, now, None)
        engine._runs["old-2"] = (FlowStatus.COMPLETED, now, None)
        engine._runs["old-3"] = (FlowStatus.COMPLETED, now, None)

        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(
            return_value={
                "task_description": "t",
                "agent_role": "a",
                "analysis_result": "r",
                "synthesis_result": "s",
            }
        )
        with patch.object(engine, "_build_graph", return_value=mock_compiled):
            await engine.submit_graph("BasicAgent", {"task_description": "test"})

        # 最早记录应被淘汰
        assert "old-1" not in engine._runs
        # 较新记录保留
        assert "old-2" in engine._runs
        assert len(engine._runs) <= engine._MAX_RUNS


# ===================================================================
# Story 5-3 — SingleAgentWorkflow 图注册 / agent_id 收敛 / get_graph_result /
# DomainError 透传 / confidence 真实化 / decision_result 投影
# ===================================================================


def _make_workflow_service_stub(
    *,
    verify_passed: bool = True,
    chain_final_answer: str = '{"answer": "终局答案"}',
) -> AsyncMock:
    """六阶段服务桩（端口形态最小实现——节点驱动用）。

    分派键 = 方法名；断言锚 = state 产物内容（独立信号）。
    """
    import hashlib

    # spec 约束（R1-F12）：方法名拼错/签名漂移即时红（Protocol 测试原则）
    from src.application.ports.agent_workflow import (
        AgentWorkflowServicePort,
        ExecutionResult,
        PackageOutcome,
        PerceptionResult,
        PlanResult,
        ReflectionResult,
        VerificationResult,
    )
    from src.domain.value_objects.chain_of_thought import ChainOfThought
    from src.domain.value_objects.task_evidence import TaskEvidencePackage

    service = AsyncMock(spec=AgentWorkflowServicePort)

    async def _perceive(state):
        return PerceptionResult(summary="任务摘要：战略分析")

    async def _plan(state):
        return PlanResult(steps=(("执行分析", "", {}),))

    async def _execute(state):
        return ExecutionResult(step_summaries=("步一完成",))

    async def _verify(state):
        return VerificationResult(passed=verify_passed, confidence=0.72 if verify_passed else 0.42, rationale="检查依据")

    async def _reflect(state):
        return ReflectionResult(revised=False, error_analysis="根因", revised_plan="")

    async def _package(state):
        verification = state.get("verification")
        passed = verification.passed if verification else False
        task = state.get("task", "")
        evidence = TaskEvidencePackage(
            input_hash=hashlib.sha256(task.encode()).hexdigest(),
            task_breakdown=("执行分析",),
            tool_trace=(),
            artifacts_snapshot=(),
            confidence=0.72 if passed else 0.42,
            confidence_rationale="检查依据",
            citations=(),
            status="completed" if passed else "failed",
            failure_reason="" if passed else "检查依据",
        )
        chain = ChainOfThought(
            input_summary="任务摘要：战略分析",
            reflection="一次通过",
            tools_used=(),
            constraints_check="约束符合",
            final_answer=chain_final_answer,
        )
        return PackageOutcome(evidence=evidence, chain=chain)

    service.perceive.side_effect = _perceive
    service.plan.side_effect = _plan
    service.execute.side_effect = _execute
    service.verify.side_effect = _verify
    service.reflect.side_effect = _reflect
    service.package_evidence.side_effect = _package
    return service


class TestSingleAgentWorkflowGraphSupport:
    """图注册与构造注入（Task 5 循环 B）。"""

    def test_supported_graphs_contains_single_agent_workflow(self) -> None:
        """_SUPPORTED_GRAPHS 含 SingleAgentWorkflow（注册遗漏会被身份锚断言抓红）。"""
        assert "SingleAgentWorkflow" in LangGraphEngine._SUPPORTED_GRAPHS

    def test_constructor_accepts_workflow_service(self, config, mock_event_publisher) -> None:
        """构造签名扩展 workflow_service（默认 None 保持 BasicAgent 向后兼容）。"""
        service = _make_workflow_service_stub()
        engine_with = LangGraphEngine(config, mock_event_publisher, workflow_service=service)
        assert engine_with is not None
        engine_without = LangGraphEngine(config, mock_event_publisher)
        assert engine_without is not None


class TestAgentIdConvergence:
    """agent_id 收敛（5-2 风险 #2 核销——DC-5）。"""

    async def test_agent_decided_agent_id_matches_parameters(self, config, mock_event_publisher) -> None:
        """AgentDecided.agent_id == parameters 传入实体 id（uuid4 新铸必红）。"""
        service = _make_workflow_service_stub()
        engine = LangGraphEngine(config, mock_event_publisher, workflow_service=service)
        agent_id = uuid.uuid4()
        parameters = {"agent_id": str(agent_id), "task": "任务", "context": None}

        await engine.submit_graph("SingleAgentWorkflow", parameters)

        published = mock_event_publisher.publish.call_args.args[0]
        assert published.agent_id == agent_id, "事件 agent_id 应等于 parameters 传入值（非自铸）"

    async def test_agent_id_fallback_when_absent(self, config, mock_event_publisher) -> None:
        """parameters 缺 agent_id 时回退自铸（BasicAgent 兼容路径）。"""
        engine = LangGraphEngine(config, mock_event_publisher)
        await engine.submit_graph("BasicAgent", {"task_description": "t"})
        published = mock_event_publisher.publish.call_args.args[0]
        assert isinstance(published.agent_id, uuid.UUID)

    @pytest.mark.parametrize(
        "bad_agent_id",
        ["not-a-uuid", "", "   ", 123, uuid.uuid4()],
        ids=["畸形串", "空串", "空白串", "非str整数", "UUID实例直塞"],
    )
    async def test_agent_id_invalid_value_raises_validation_error(
        self, config, mock_event_publisher, bad_agent_id: object
    ) -> None:
        """R1-F4 收敛位守卫：agent_id 键存在但非法 → ValidationError(201) 统一
        异常体系（裸 uuid.UUID 会抛内置 ValueError/AttributeError 逃逸——
        orchestration_service API 直通面可触发；不写 _runs 死记录）。"""
        from src.domain.exceptions import ValidationError

        engine = LangGraphEngine(config, mock_event_publisher)
        with pytest.raises(ValidationError) as exc_info:
            await engine.submit_graph("BasicAgent", {"task_description": "t", "agent_id": bad_agent_id})
        assert exc_info.value.code == "EXCEPTION_201"
        # 参数校验位先于 run 记录——非法输入不留死记录
        assert engine._runs == {} or all(status != FlowStatus.FAILED for status, _, _ in engine._runs.values())


class TestAgentDecidedRealization:
    """AgentDecided 真实化（DC-6/R3-F5——图身份锚）。"""

    async def test_decision_result_projection_five_keys(self, config, mock_event_publisher) -> None:
        """decision_result 五键纯标量投影（图身份锚——防未知图名静默回退仍绿）。"""
        service = _make_workflow_service_stub()
        engine = LangGraphEngine(config, mock_event_publisher, workflow_service=service)
        await engine.submit_graph("SingleAgentWorkflow", {"agent_id": str(uuid.uuid4()), "task": "任务", "context": None})

        published = mock_event_publisher.publish.call_args.args[0]
        decision = published.decision_result
        for key in ("workflow_status", "task_summary", "chain_summary", "evidence_ref", "retry_count"):
            assert key in decision, f"投影缺键: {key}"
            assert isinstance(decision[key], (str, int, float)), f"投影键 {key} 应为纯标量"
        assert decision["workflow_status"] == "completed"
        assert decision["retry_count"] == 0
        assert decision["chain_summary"].startswith('{"answer"')

    async def test_confidence_from_state_not_hardcoded(self, config, mock_event_publisher) -> None:
        """事件 confidence == state 验证置信度（Fake 桩 0.72——硬编码 0.9 必红）。"""
        service = _make_workflow_service_stub()
        engine = LangGraphEngine(config, mock_event_publisher, workflow_service=service)
        await engine.submit_graph("SingleAgentWorkflow", {"agent_id": str(uuid.uuid4()), "task": "任务", "context": None})

        published = mock_event_publisher.publish.call_args.args[0]
        assert published.confidence == 0.72, "事件置信度应取 state（Fake 桩 0.72 档）"

    async def test_basic_agent_confidence_default_preserved(self, config, mock_event_publisher) -> None:
        """BasicAgent 存量断言 0.9 保持绿（state.get("confidence", 0.9) 双默认——DC-6 范围仅新图）。"""
        engine = LangGraphEngine(config, mock_event_publisher)
        await engine.submit_graph("BasicAgent", {"task_description": "t"})
        published = mock_event_publisher.publish.call_args.args[0]
        assert published.confidence == 0.9

    async def test_basic_agent_decision_result_full_state_passthrough(self, config, mock_event_publisher) -> None:
        """R1-F12 互斥锚：BasicAgent decision_result 保持 state 全量透传——
        投影误施于 BasicAgent（判别条件改坏）时本断言红（含 BasicAgent 特有键
        且不含五键投影的 workflow_status）。"""
        engine = LangGraphEngine(config, mock_event_publisher)
        await engine.submit_graph("BasicAgent", {"task_description": "t"})
        decision = mock_event_publisher.publish.call_args.args[0].decision_result
        assert "analysis_result" in decision, "BasicAgent 应全量透传（含 analysis_result 键）"
        assert "synthesis_result" in decision
        assert "workflow_status" not in decision, "五键投影不应施于 BasicAgent（图名判别被破坏即红）"


class TestGetGraphResult:
    """get_graph_result 结果取回（DC-11——既有端口追加方法）。"""

    async def test_get_graph_result_returns_final_state(self, config, mock_event_publisher) -> None:
        """新图路径写入终态 state（evidence/chain/executed_phases 可取回）。"""
        service = _make_workflow_service_stub()
        engine = LangGraphEngine(config, mock_event_publisher, workflow_service=service)
        run_id = await engine.submit_graph(
            "SingleAgentWorkflow", {"agent_id": str(uuid.uuid4()), "task": "任务", "context": None}
        )

        state = await engine.get_graph_result(run_id)
        assert state is not None
        assert state["executed_phases"][-1] == "package"
        assert state["evidence"].status == "completed"
        assert state["chain"] is not None

    async def test_get_graph_result_unknown_id_returns_none(self, config, mock_event_publisher) -> None:
        """未知/过期 id 返回 None（区分于 get_graph_status 的 FAILED 默认）。"""
        engine = LangGraphEngine(config, mock_event_publisher)
        result = await engine.get_graph_result("nonexistent-run-id")
        assert result is None

    async def test_basic_agent_result_still_none_compatible(self, config, mock_event_publisher) -> None:
        """BasicAgent 路径（无服务注入）不破坏 get_graph_status 存量语义。"""
        engine = LangGraphEngine(config, mock_event_publisher)
        run_id = await engine.submit_graph("BasicAgent", {"task_description": "t"})
        status = await engine.get_graph_status(run_id)
        assert status == FlowStatus.COMPLETED


class TestDomainErrorPassthrough:
    """DomainError 透传（R1-F4——444/445 原样上抛，非 RuntimeError 改写）。"""

    async def test_node_444_propagates_as_domain_error(self, config, mock_event_publisher) -> None:
        """节点内 444 → submit_graph 上抛 AgentWorkflowError（非 RuntimeError 改写）。"""
        from src.domain.exceptions.agent_exceptions import AgentWorkflowError

        service = _make_workflow_service_stub()

        async def _broken_perceive(state):
            raise AgentWorkflowError(agent_id=str(state.get("agent_id", "")), phase="perceive", reason="LLM 失败")

        service.perceive.side_effect = _broken_perceive
        engine = LangGraphEngine(config, mock_event_publisher, workflow_service=service)

        with pytest.raises(AgentWorkflowError) as exc_info:
            await engine.submit_graph("SingleAgentWorkflow", {"agent_id": str(uuid.uuid4()), "task": "任务", "context": None})
        assert exc_info.value.code == "EXCEPTION_444"
        assert exc_info.value.context["phase"] == "perceive"

    async def test_non_domain_error_still_wrapped_runtime_error(self, engine) -> None:
        """非 DomainError（SDK 异常）保持 RuntimeError 包装（存量语义零回归）。"""
        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(side_effect=Exception("SDK error"))
        with patch.object(engine, "_build_graph", return_value=mock_compiled):
            with pytest.raises(RuntimeError, match="提交状态图失败"):
                await engine.submit_graph("BasicAgent", {"task_description": "t"})
