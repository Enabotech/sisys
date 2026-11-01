"""Story 6-1 — BlmPlanningService + SpBlmGraph 单元测试。

TDD Task 3 载体（循环 A 服务阶段方法 + 循环 B 图拓扑）：
- 六子步骤语义配置表驱动断言（视角前缀+工具候选白名单+温度档——期望
  独立构造自配置表唯一源）
- 每步时序钦定（DC-3：工具候选→工具先行→检索注入→单次结构化调用）
- 8s 超时/温度配置传递（Fake LLM 捕获 config 实参）
- 步级降级三态（449/380/LLM 失败——AC-6⑤+直接推理续行语义）+ 服务内
  两级重试（瞬时失败先重试再降级）
- 降级下游三规则（⑥——标注注入/degraded_inputs 列举/阶段 1 全降级阶段 2 照常）
- 各方法末尾快照写+事件发布调用断言（DC-6 写入方唯一）
- 图拓扑（8 节点 7 直连边+END/compile 无 checkpointer）+ 引擎挂载双点 +
  图身份锚（终态 state 含 BLM 专属键）

Run with:
    poetry run pytest tests/unit/application/test_blm_planning_service.py -v
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.ports.blm_planning import (
    BLM_PLANNING_SESSION_PREFIX,
    BlmPlanningContext,
)
from src.application.ports.isolation_guard import IsolationGuardPort
from src.application.services.blm_planning_prompts import (
    BLM_TEMPERATURE_PROFILE,
    MARKET_INSIGHT_STEP_CONFIG,
    PERFORMANCE_GAP_CONFIG,
    GapAnalysisSchema,
    InsightStepSchema,
    InsightSynthesisSchema,
)
from src.application.services.blm_planning_service import BlmPlanningService
from src.domain.exceptions.agent_exceptions import IsolationOperationForbiddenError
from src.domain.exceptions.tool_exceptions import ToolNotFoundError
from src.domain.ports.hybrid_search import HybridSearchPort
from src.domain.ports.llm_client import LLMClientPort, LLMResponse
from src.domain.ports.snapshot_repository_protocol import SnapshotRepositoryProtocol
from src.domain.value_objects.blm_phases import MarketInsightStep

PLAN_ID = "plan-test-1"
AGENT_ID = uuid.uuid4()
TASK = "制定新能源汽车行业五年战略规划"
COLLECTION = "test_blm_col"


# ===================================================================
# Fake LLM（BLM 面三 Schema 分派 + 失败注入 + 配置捕获）
# ===================================================================


def _make_fake_llm(
    *,
    fail_schemas: frozenset[type] = frozenset(),
    fail_first_calls: int = 0,
    empty_synthesis: bool = False,
    config_error: bool = False,
) -> Any:
    """BLM 面 Fake LLM（AsyncMock spec=LLMClientPort——外部 SaaS 豁免替身）。

    Args:
        fail_schemas: 对指定 Schema 恒抛 LLMAPIError（降级终态注入）。
        fail_first_calls: 前 N 次调用抛 LLMAPIError（瞬时故障——重试后成功）。
        empty_synthesis: synthesis 分派返回空 conclusions（R1-10② 空结论形态）。
        config_error: 每次调用抛 LLMConfigError（R1-10④ 确定性配置错误形态）。
    """
    state: dict[str, Any] = {"calls": [], "count": 0}

    async def _structured_generate(
        prompt: str, response_schema: type, config: Any = None, system_prompt: str | None = None
    ) -> Any:
        state["count"] += 1
        state["calls"].append(
            {
                "prompt": prompt,
                "schema": response_schema,
                "config": config,
                "temperature": getattr(config, "temperature", None),
                "timeout": getattr(config, "timeout", None),
                "system_prompt": system_prompt,
            }
        )
        if config_error:
            from src.domain.exceptions import LLMConfigError

            raise LLMConfigError("api_key 缺失（Fake 注入）")
        if fail_first_calls and state["count"] <= fail_first_calls:
            from src.domain.exceptions.llm_exceptions import LLMAPIError

            raise LLMAPIError("瞬时故障（Fake 注入）")
        if response_schema in fail_schemas:
            from src.domain.exceptions.llm_exceptions import LLMAPIError

            raise LLMAPIError("持续故障（Fake 注入）")
        if response_schema is GapAnalysisSchema:
            return GapAnalysisSchema(
                financial_gap="财务差距量化结论",
                operational_gap="运营差距分析结论",
                root_causes=["根因一", "根因二"],
                portfolio_health="业务组合健康度评估",
            )
        if response_schema is InsightStepSchema:
            return InsightStepSchema(summary="市场洞察步骤摘要", findings=["发现一", "发现二"])
        if response_schema is InsightSynthesisSchema:
            if empty_synthesis:
                return InsightSynthesisSchema(conclusions=[])
            return InsightSynthesisSchema(conclusions=["综合结论一", "综合结论二"])
        raise AssertionError(f"未知 response_schema: {response_schema!r}")

    async def _generate(prompt: str, config: Any = None, system_prompt: str | None = None) -> LLMResponse:
        return LLMResponse(content='{"valid": true}', model="fake-llm")

    fake = AsyncMock(spec=LLMClientPort)
    fake.structured_generate.side_effect = _structured_generate
    fake.generate.side_effect = _generate
    fake._state = state
    return fake


# ===================================================================
# 服务工厂（Mock 端口注入——单元测试 Mock 合规域）
# ===================================================================


def _make_context() -> BlmPlanningContext:
    profile = MagicMock()
    profile.agent_id = AGENT_ID
    return BlmPlanningContext(plan_id=PLAN_ID, agent_id=AGENT_ID, profile_result=profile, task=TASK)


def _make_service(
    fake_llm: Any | None = None,
    *,
    guard_error: Exception | None = None,
    registry_error: Exception | None = None,
    search_error: Exception | None = None,
) -> tuple[BlmPlanningService, dict[str, Any]]:
    """构造被测服务 + mock 依赖字典。

    Args:
        fake_llm: Fake LLM（缺省新造）。
        guard_error: 隔离预检注入异常（449 触发面）。
        registry_error: 工具注册注入异常（380 触发面）。
        search_error: 检索注入异常（检索失败降级面）。
    """
    llm = fake_llm or _make_fake_llm()

    tool_execution = AsyncMock()
    tool_result = MagicMock()
    tool_result.status.value = "success"
    tool_result.output = {"分析结论": "工具产出要点"}
    tool_result.evidence_package.citations = ()
    tool_execution.execute = AsyncMock(return_value=tool_result)

    registry = MagicMock()
    tool_meta = MagicMock()
    tool_meta.tool_id = uuid.uuid4()
    tool_meta.slug = "swot-tows"
    tool_meta.name = "SWOT-TOWS"
    tool_meta.version = "v1"
    if registry_error is not None:
        registry.get_tool = MagicMock(side_effect=registry_error)
    else:
        registry.get_tool = MagicMock(return_value=tool_meta)

    guard = AsyncMock(spec=IsolationGuardPort)
    if guard_error is not None:
        guard.ensure_tool_access = AsyncMock(side_effect=guard_error)
    else:
        guard.ensure_tool_access = AsyncMock(return_value=None)

    hybrid = AsyncMock(spec=HybridSearchPort)
    if search_error is not None:
        hybrid.search = AsyncMock(side_effect=search_error)
    else:
        # SearchResult 是 TypedDict（运行时 dict）——替身必须 dict 形态（R1-1：
        # MagicMock 属性形态与真实契约断裂是证据提取恒空的掩盖源）
        search_result = {
            "id": "chunk-001",
            "score": 0.92,
            "payload": {"text": "检索证据片段：新能源行业趋势要点"},
        }
        hybrid.search = AsyncMock(return_value=[search_result])

    snapshot_repo = AsyncMock(spec=SnapshotRepositoryProtocol)
    publisher = AsyncMock()

    service = BlmPlanningService(
        llm_client=llm,
        tool_execution_service=tool_execution,
        tool_registry_service=registry,
        isolation_guard=guard,
        hybrid_search=hybrid,
        search_collection=COLLECTION,
        event_publisher=publisher,
        snapshot_repository=snapshot_repo,
    )
    return service, {
        "llm": llm,
        "tool_execution": tool_execution,
        "registry": registry,
        "guard": guard,
        "hybrid": hybrid,
        "snapshot_repo": snapshot_repo,
        "publisher": publisher,
    }


async def _run_six_steps(
    service: BlmPlanningService, context: BlmPlanningContext, prior: dict[str, Any] | None = None
) -> list[Any]:
    """按枚举序执行六子步骤（服务直调——图拓扑另测）。"""
    prior_outputs: dict[str, Any] = prior or {"performance_gap": None, "insight_steps": ()}
    results = []
    for step in MarketInsightStep:
        result = await service.run_insight_step(step, context, prior_outputs)
        results.append(result)
        prior_outputs = {**prior_outputs, "insight_steps": tuple(results)}
    return results


# ===================================================================
# 循环 A：阶段方法（产物/prompt 断言/配置传递/检索注入）
# ===================================================================


class TestPerformanceGapAnalysis:
    """阶段 1 业绩差距分析。"""

    async def test_four_field_artifacts(self) -> None:
        """四字段产物（financial_gap/operational_gap/root_causes/portfolio_health）。"""
        service, _mocks = _make_service()
        artifacts = await service.run_performance_gap_analysis(_make_context())
        assert artifacts.financial_gap == "财务差距量化结论"
        assert artifacts.operational_gap == "运营差距分析结论"
        assert artifacts.root_causes == ("根因一", "根因二")
        assert artifacts.portfolio_health == "业务组合健康度评估"
        assert artifacts.degraded is False

    async def test_prompt_contains_role_prefix_and_tools(self) -> None:
        """prompt 含 CFO/COO 视角前缀 + 四工具候选白名单（配置表驱动）。"""
        service, mocks = _make_service()
        await service.run_performance_gap_analysis(_make_context())
        prompt = mocks["llm"]._state["calls"][0]["prompt"]
        assert PERFORMANCE_GAP_CONFIG.role_prefix in prompt, "阶段 1 prompt 缺视角前缀"
        for slug in PERFORMANCE_GAP_CONFIG.tool_candidates:
            assert slug in prompt, f"阶段 1 prompt 缺工具候选 {slug}"

    async def test_config_passing_timeout_and_temperature(self) -> None:
        """8s timeout + 阶段 1 温度档（配置传递——AC-5 断言锚）。"""
        service, mocks = _make_service()
        await service.run_performance_gap_analysis(_make_context())
        call = mocks["llm"]._state["calls"][0]
        assert call["timeout"] == 8.0
        assert call["temperature"] == BLM_TEMPERATURE_PROFILE["performance_gap"]

    async def test_retrieval_evidence_injected_into_prompt(self) -> None:
        """检索证据注入 prompt（Fake 独有锚——提取断裂/证据丢弃即红）。"""
        service, mocks = _make_service()
        await service.run_performance_gap_analysis(_make_context())
        mocks["hybrid"].search.assert_awaited()
        prompt = mocks["llm"]._state["calls"][0]["prompt"]
        assert "新能源行业趋势要点" in prompt, "证据文本未注入 prompt（TypedDict 提取断裂或证据丢弃）"

    async def test_retrieval_evidence_production_content_key(self) -> None:
        """生产链 payload["content"] 键形态命中（chunk_indexing_handler 写入键——双键兼容）。"""
        service, mocks = _make_service()
        mocks["hybrid"].search = AsyncMock(
            return_value=[{"id": "chunk-002", "score": 0.88, "payload": {"content": "生产链语料：组织能力评估要点"}}]
        )
        await service.run_performance_gap_analysis(_make_context())
        prompt = mocks["llm"]._state["calls"][0]["prompt"]
        assert "组织能力评估要点" in prompt, "content 键形态未命中（生产链提取断裂）"

    async def test_same_plan_id_rerun_rejected_482(self) -> None:
        """同 plan_id 重跑 → PlanningStateError(482)（run 入口守卫——R1-5）。

        首次 run 事件已发布/快照已写，重跑将污染 timeline 与降级计数；
        重试语义=新 plan_id。
        """
        from src.domain.exceptions.planning_exceptions import PlanningStateError

        service, _mocks = _make_service()
        context = _make_context()
        await service.run_performance_gap_analysis(context)
        with pytest.raises(PlanningStateError) as exc_info:
            await service.run_performance_gap_analysis(context)
        assert exc_info.value.code == "EXCEPTION_482"
        assert exc_info.value.context.get("plan_id") == PLAN_ID

    async def test_tool_used_filled_on_success(self) -> None:
        """工具成功步 tool_used 回填 slug（VO 契约——真执行与直接推理可判别，R1-10⑤）。"""
        service, _mocks = _make_service()
        result = await service.run_insight_step(MarketInsightStep.TREND, _make_context(), {})
        assert result.tool_used == "swot-tows", "工具成功步应回填 slug（tool.slug 口径钦定）"

    async def test_snapshot_written_and_event_published(self) -> None:
        """方法末尾：快照写（snapshot_repository.save）+ BlmStageCompleted 发布。"""
        service, mocks = _make_service()
        await service.run_performance_gap_analysis(_make_context())
        mocks["snapshot_repo"].save.assert_awaited()
        events = [c.args[0] for c in mocks["publisher"].publish.await_args_list]
        stage_events = [e for e in events if type(e).__name__ == "BlmStageCompleted"]
        assert any(e.stage == "performance_gap" for e in stage_events)


class TestInsightSteps:
    """六子步骤执行（顺序/前缀/白名单/检索/配置）。"""

    async def test_six_steps_in_enum_order(self) -> None:
        """六步按枚举序执行（step 标识与 MarketInsightStep 同源）。"""
        service, _mocks = _make_service()
        results = await _run_six_steps(service, _make_context())
        assert [r.step for r in results] == [s.value for s in MarketInsightStep]
        assert all(r.summary for r in results)

    async def test_each_step_prompt_prefix_and_whitelist(self) -> None:
        """每步 prompt 含视角前缀 + 该步工具候选全量（语义配置表钦定面——独立构造期望）。"""
        service, mocks = _make_service()
        await _run_six_steps(service, _make_context())
        step_calls = [c for c in mocks["llm"]._state["calls"] if c["schema"] is InsightStepSchema]
        assert len(step_calls) == 6
        for call, (step, config) in zip(step_calls, MARKET_INSIGHT_STEP_CONFIG.items()):
            assert config.role_prefix in call["prompt"], f"{step.value} prompt 缺视角前缀"
            for slug in config.tool_candidates:
                assert slug in call["prompt"], f"{step.value} prompt 缺工具候选 {slug}（全量白名单注入——R1-9⑤）"

    async def test_each_step_temperature_profile(self) -> None:
        """每步温度档=配置表钦定（8 步温度映射唯一源）。"""
        service, mocks = _make_service()
        await _run_six_steps(service, _make_context())
        step_calls = [c for c in mocks["llm"]._state["calls"] if c["schema"] is InsightStepSchema]
        for call, (step, _config) in zip(step_calls, MARKET_INSIGHT_STEP_CONFIG.items()):
            expected_temp = BLM_TEMPERATURE_PROFILE[step.value]
            assert call["temperature"] == expected_temp, f"{step.value} 温度档不符"
            assert call["timeout"] == 8.0

    async def test_retrieval_per_step(self) -> None:
        """每步独立检索（恰六次 search 调用 + collection 传参注入——租户隔离装配面）。"""
        service, mocks = _make_service()
        await _run_six_steps(service, _make_context())
        assert mocks["hybrid"].search.await_count == 6, "六子步骤应恰六次检索（多/漏均红）"
        for call in mocks["hybrid"].search.await_args_list:
            assert call.kwargs.get("collection") == COLLECTION, "search 未收到构造注入的 collection"


class TestSynthesis:
    """综合洞察。"""

    async def test_synthesis_conclusions(self) -> None:
        """综合结论产出（单次聚合调用）。"""
        service, _mocks = _make_service()
        context = _make_context()
        steps = await _run_six_steps(service, context)
        synthesis = await service.synthesize_insights({"insight_steps": tuple(steps)}, context)
        assert synthesis.conclusions
        assert synthesis.degraded_inputs == ()

    async def test_synthesis_prompt_contains_step_summaries(self) -> None:
        """注入侧锚：synthesis prompt 含六步产物摘要（漏传任一步可判别）。"""
        service, mocks = _make_service()
        context = _make_context()
        steps = await _run_six_steps(service, context)
        await service.synthesize_insights({"insight_steps": tuple(steps)}, context)
        synthesis_calls = [c for c in mocks["llm"]._state["calls"] if c["schema"] is InsightSynthesisSchema]
        assert synthesis_calls
        prompt = synthesis_calls[-1]["prompt"]
        # 六步 Fake 产出均含「市场洞察步骤摘要」标记——prompt 注入面可见
        assert prompt.count("市场洞察步骤摘要") == 6, "synthesis prompt 未含全部六步摘要"

    async def test_synthesis_event_published(self) -> None:
        """synthesis 完成：BlmStageCompleted(market_insight_synthesis) 发布+快照写。"""
        service, mocks = _make_service()
        context = _make_context()
        steps = await _run_six_steps(service, context)
        await service.synthesize_insights({"insight_steps": tuple(steps)}, context)
        events = [c.args[0] for c in mocks["publisher"].publish.await_args_list]
        assert any(type(e).__name__ == "BlmStageCompleted" and e.stage == "market_insight_synthesis" for e in events)
        assert mocks["snapshot_repo"].save.await_count >= 1


# ===================================================================
# 循环 A：步级降级（449/380/LLM/检索）+ 两级重试 + 下游三规则
# ===================================================================


class TestStepDegradation:
    """步级降级语义（AC-6①⑤——449/380 捕获 + 直接推理续行）。"""

    async def test_llm_failure_degrades_step(self) -> None:
        """LLM 持续失败 → 该步降级（完整信封：degraded+原因+空 summary）。"""
        llm = _make_fake_llm(fail_schemas=frozenset({InsightStepSchema}))
        service, _mocks = _make_service(llm)
        results = await _run_six_steps(service, _make_context())
        degraded = [r for r in results if r.degraded]
        assert len(degraded) == 6
        assert all(not r.summary for r in degraded)
        assert all(r.degrade_reason for r in degraded)

    async def test_transient_failure_retried_then_succeeds(self) -> None:
        """瞬时故障两级设计：首次失败重试一次成功 → 不降级（服务内重试）。"""
        llm = _make_fake_llm(fail_first_calls=1)
        service, mocks = _make_service(llm)
        result = await service.run_insight_step(MarketInsightStep.TREND, _make_context(), {})
        assert result.degraded is False, "瞬时故障（单次）应经服务内重试恢复"
        assert result.summary

    async def test_isolation_449_degrades_with_direct_reasoning(self) -> None:
        """449 隔离预检拒绝 → 步骤降级 + 直接推理续行（LLM 仍执行——产物非空）。"""
        service, mocks = _make_service(
            guard_error=IsolationOperationForbiddenError(
                agent_id=str(AGENT_ID), operation="tool_access", reason="tool_not_in_allowlist:swot-tows"
            )
        )
        result = await service.run_insight_step(MarketInsightStep.TREND, _make_context(), {})
        assert result.degraded is True
        assert "449" in result.degrade_reason or "隔离" in result.degrade_reason
        assert result.summary, "449 降级以直接推理续行——LLM 产出仍非空"
        assert result.tool_used == "", "降级步 tool_used 空"

    async def test_tool_380_degrades_with_direct_reasoning(self) -> None:
        """380 工具未注册 → 步骤降级 + 直接推理续行（单测层注入面）。"""
        service, mocks = _make_service(registry_error=ToolNotFoundError(tool_name="幻觉工具名"))
        result = await service.run_insight_step(MarketInsightStep.TREND, _make_context(), {})
        assert result.degraded is True
        assert "380" in result.degrade_reason or "工具" in result.degrade_reason
        assert result.summary

    async def test_retrieval_failure_degrades_step(self) -> None:
        """检索取数失败 → 该步降级（连接失败=降级语义——R3-6 钦定）。"""
        service, mocks = _make_service(search_error=RuntimeError("Qdrant 不可达"))
        result = await service.run_insight_step(MarketInsightStep.TREND, _make_context(), {})
        assert result.degraded is True
        assert "检索" in result.degrade_reason

    async def test_retrieval_empty_result_not_degraded(self) -> None:
        """检索空结果 → 正常空证据（不降级——空结果≠失败判别语义）。"""
        service, mocks = _make_service()
        mocks["hybrid"].search = AsyncMock(return_value=[])
        result = await service.run_insight_step(MarketInsightStep.TREND, _make_context(), {})
        assert result.degraded is False
        assert result.summary


class TestDegradationDownstreamRules:
    """降级下游三规则（AC-6⑥）。"""

    async def test_downstream_prompt_contains_degradation_marker(self) -> None:
        """规则 1：上游降级产物以「[降级]+原因」注入下游 prompt。"""
        llm = _make_fake_llm(fail_schemas=frozenset({InsightStepSchema}))
        service, mocks = _make_service(llm)
        context = _make_context()
        first = await service.run_insight_step(MarketInsightStep.TREND, context, {})
        assert first.degraded
        # 第二步：prior_outputs 含降级产物
        await service.run_insight_step(MarketInsightStep.MARKET_CUSTOMER, context, {"insight_steps": (first,)})
        step_calls = [c for c in mocks["llm"]._state["calls"] if c["schema"] is InsightStepSchema]
        # 按步骤名定位「看市场与客户」首次调用（TREND 失败含重试会占多个 calls 槽位）
        market_customer_calls = [c for c in step_calls if "看市场与客户" in c["prompt"]]
        assert market_customer_calls, "未捕获看市场与客户步骤调用"
        second_prompt = market_customer_calls[0]["prompt"]
        assert "降级" in second_prompt, "下游 prompt 未含降级标注（⑥规则 1）"

    async def test_synthesis_lists_degraded_inputs(self) -> None:
        """规则 2：synthesis 结论必须列举 degraded 输入（不可无标注吞并）。"""
        llm = _make_fake_llm(fail_schemas=frozenset({InsightStepSchema}))
        service, _mocks = _make_service(llm)
        context = _make_context()
        steps = await _run_six_steps(service, context)
        synthesis = await service.synthesize_insights({"insight_steps": tuple(steps)}, context)
        degraded_steps = {r.step for r in steps if r.degraded}
        assert degraded_steps
        assert degraded_steps.issubset(set(synthesis.degraded_inputs)), "degraded_inputs 未完整列举"

    async def test_gap_degraded_phase2_continues(self) -> None:
        """规则 3：阶段 1 全降级 → 阶段 2 照常执行 + 综合报告携带标记 + gap 降级态注入阶段 2 prompt。"""
        llm = _make_fake_llm(fail_schemas=frozenset({GapAnalysisSchema}))
        service, mocks = _make_service(llm)
        context = _make_context()
        gap = await service.run_performance_gap_analysis(context)
        assert gap.degraded, "阶段 1 LLM 失败应降级"
        # 跨阶段传导：首子步骤 prompt 含 gap 降级标注（规则 1——阶段 1→阶段 2 闭合）
        steps = await _run_six_steps(service, context, prior={"performance_gap": gap, "insight_steps": ()})
        assert all(not r.degraded for r in steps), "阶段 1 降级不阻断阶段 2"
        trend_calls = [c for c in mocks["llm"]._state["calls"] if c["schema"] is InsightStepSchema and "看趋势" in c["prompt"]]
        assert trend_calls, "未捕获看趋势步骤调用"
        assert "[降级] 步骤 performance_gap 降级" in trend_calls[0]["prompt"], "gap 降级标注未注入阶段 2 prompt"
        # 综合报告携带标记：degraded_inputs 含 performance_gap（规则 3 半句）
        synthesis = await service.synthesize_insights({"insight_steps": tuple(steps), "performance_gap": gap}, context)
        assert "performance_gap" in synthesis.degraded_inputs, "综合报告未携带阶段 1 降级标记（规则 3）"

    async def test_synthesis_empty_conclusions_self_marks(self) -> None:
        """synthesis LLM 成功但空结论 → 视同降级自含（R3-4 两分支对称——R1-10②）。"""
        llm = _make_fake_llm(empty_synthesis=True)
        service, _mocks = _make_service(llm)
        context = _make_context()
        steps = await _run_six_steps(service, context)
        synthesis = await service.synthesize_insights({"insight_steps": tuple(steps)}, context)
        assert synthesis.conclusions == ()
        assert "market_insight_synthesis" in synthesis.degraded_inputs, "空结论形态未自含标记（R1-10②）"

    async def test_tool_candidates_all_execute_fail_degrades(self) -> None:
        """工具候选全执行失败（非 449/380）→ 聚合降级原因（环耗尽不静默——R1-10①）。"""
        service, mocks = _make_service()
        mocks["tool_execution"].execute = AsyncMock(side_effect=RuntimeError("工具引擎内部故障"))
        result = await service.run_insight_step(MarketInsightStep.TREND, _make_context(), {})
        assert result.degraded is True, "工具候选全部执行失败应记降级"
        assert "全部执行失败" in result.degrade_reason
        assert result.summary, "降级以直接推理续行"

    async def test_llm_config_error_no_retry_degrades(self) -> None:
        """LLMConfigError（确定性配置错误）→ 不重试直接步级降级且原因如实（R1-10④）。"""
        llm = _make_fake_llm(config_error=True)
        service, mocks = _make_service(llm)
        result = await service.run_insight_step(MarketInsightStep.TREND, _make_context(), {})
        assert len(mocks["llm"]._state["calls"]) == 1, "LLMConfigError 不应重试（确定性错误）"
        assert result.degraded is True
        assert "配置错误" in result.degrade_reason


class TestSnapshotWrite:
    """步骤边界快照写入（DC-6——写入方唯一归服务各方法末尾）。"""

    async def test_snapshot_session_and_state_shape(self) -> None:
        """快照 state_data 契约（session_id=前缀+plan_id；timeline 六键）。"""
        service, mocks = _make_service()
        context = _make_context()
        await service.run_performance_gap_analysis(context)
        await service.run_insight_step(MarketInsightStep.TREND, context, {"insight_steps": ()})
        save_calls = mocks["snapshot_repo"].save.await_args_list
        assert save_calls, "快照未写入"
        for call in save_calls:
            snapshot = call.args[0]
            assert snapshot.session_id == f"{BLM_PLANNING_SESSION_PREFIX}{PLAN_ID}"
            data = snapshot.state_data
            assert data["plan_id"] == PLAN_ID
            assert data["total_steps"] == 8
            for entry in data["timeline"]:
                assert set(entry) == {"step", "started_at", "completed_at", "status", "summary_excerpt", "degraded"}


# ===================================================================
# 循环 B：SpBlmGraph 图拓扑 + 引擎挂载双点
# ===================================================================


def _make_engine(service: Any) -> Any:
    """构造 LangGraphEngine（blm_planning_service 注入——挂载双点验证面）。"""
    from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
    from src.infrastructure.config.langgraph import LangGraphConfig

    recorder = AsyncMock()
    return LangGraphEngine(
        config=LangGraphConfig.from_env(),
        event_publisher=recorder,
        blm_planning_service=service,
    )


class TestSpBlmGraphTopology:
    """图拓扑（8 节点 7 直连边+END——R3-1 钦定形态）。"""

    def test_supported_graphs_registered(self) -> None:
        """挂载点 1：_SUPPORTED_GRAPHS 含 SpBlmGraph（消告警判据）。"""
        from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine

        assert "SpBlmGraph" in LangGraphEngine._SUPPORTED_GRAPHS

    def test_build_graph_dispatch_branch(self) -> None:
        """挂载点 2：_build_graph 显式分派分支（漏分支将静默回退 BasicAgent）。"""
        import inspect

        from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine

        source = inspect.getsource(LangGraphEngine._build_graph)
        assert 'graph_name == "SpBlmGraph"' in source

    def test_graph_without_service_raises_validation(self) -> None:
        """未注入 blm_planning_service → ValidationError（SingleAgentWorkflow 先例）。"""
        from src.domain.exceptions import ValidationError
        from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
        from src.infrastructure.config.langgraph import LangGraphConfig

        engine = LangGraphEngine(config=LangGraphConfig.from_env(), event_publisher=AsyncMock())
        with pytest.raises(ValidationError):
            engine._build_graph("SpBlmGraph", {})

    def test_topology_eight_nodes_seven_edges(self) -> None:
        """节点集=阶段 1+六子步骤+综合（8 节点）；compile 无 checkpointer。"""
        from src.infrastructure.agent_orch.graphs.sp_blm_graph import build_sp_blm_graph

        service, _mocks = _make_service()
        graph = build_sp_blm_graph(service)
        expected_nodes = {
            "performance_gap",
            "insight_trend",
            "insight_market_customer",
            "insight_competition",
            "insight_self",
            "insight_opportunity",
            "insight_opportunity_gap",
            "synthesize",
        }
        actual_nodes = set(graph.get_graph().nodes.keys())
        assert expected_nodes.issubset(actual_nodes), f"节点集缺失: {expected_nodes - actual_nodes}"
        edges = graph.get_graph().edges
        assert len([e for e in edges if e.target != "__end__"]) >= 7, "直连边不足 7 条"

    async def test_engine_full_chain_graph_identity_anchor(self) -> None:
        """图身份锚：终态含 BLM 专属键 + 六步执行序==字面量期望（边序错乱即红——R1-9③）。"""
        service, _mocks = _make_service()
        engine = _make_engine(service)
        context = _make_context()
        run_id = await engine.submit_graph(
            "SpBlmGraph",
            {"agent_id": str(AGENT_ID), "plan_id": PLAN_ID, "task": TASK, "context": context},
        )
        final_state = await engine.get_graph_result(run_id)
        assert final_state is not None
        assert "gap_artifacts" in final_state, "图身份锚：终态含 BLM 专属键 gap_artifacts"
        assert "insight_step_results" in final_state
        assert "synthesis" in final_state
        assert len(final_state["insight_step_results"]) == 6
        assert final_state["plan_id"] == PLAN_ID
        # 顺序断言（字面量独立构造自 or.md 钦定序——不经被测枚举/服务生成期望）
        expected_order = ("trend", "market_customer", "competition", "self", "opportunity", "opportunity_gap")
        actual_order = tuple(s.step for s in final_state["insight_step_results"])
        assert actual_order == expected_order, f"六步执行序错乱: {actual_order}"

    async def test_engine_agent_decided_projection_pure_scalars(self) -> None:
        """DC-11 投影断言（链路接线七件⑦——R1-2）：AgentDecided 五键纯标量 + confidence==0.0。

        投影分支整段删除（VO 实例入 payload）或 confidence 回落 0.9 假值均红。
        """
        service, _mocks = _make_service()
        engine = _make_engine(service)
        run_id = await engine.submit_graph(
            "SpBlmGraph",
            {"agent_id": str(AGENT_ID), "plan_id": PLAN_ID, "task": TASK, "context": _make_context()},
        )
        final_state = await engine.get_graph_result(run_id)
        assert final_state is not None
        recorder = engine._event_publisher
        agent_decided = [c.args[0] for c in recorder.publish.await_args_list if type(c.args[0]).__name__ == "AgentDecided"]
        assert agent_decided, "SpBlmGraph 路径未发布 AgentDecided"
        event = agent_decided[0]
        payload = event.decision_result
        for key in ("workflow_status", "task_summary", "chain_summary", "evidence_ref", "retry_count"):
            assert key in payload, f"DC-11 投影缺键 {key}"
            value = payload[key]
            assert isinstance(value, (str, int, float, bool)), f"DC-11 投影键 {key} 非纯标量: {type(value)}"
        assert event.confidence == 0.0, "confidence 应显式 0.0（勿吃 0.9 假置信度——DC-11）"

    async def test_engine_degraded_steps_accumulated(self) -> None:
        """全链降级累积：LLM 全失败 → degraded_steps 含 8 步标识（481 上游数据面）。"""
        llm = _make_fake_llm(fail_schemas=frozenset({GapAnalysisSchema, InsightStepSchema, InsightSynthesisSchema}))
        service, _mocks = _make_service(llm)
        engine = _make_engine(service)
        run_id = await engine.submit_graph(
            "SpBlmGraph",
            {"agent_id": str(AGENT_ID), "plan_id": PLAN_ID, "task": TASK, "context": _make_context()},
        )
        final_state = await engine.get_graph_result(run_id)
        assert final_state is not None
        degraded = tuple(final_state["degraded_steps"])
        assert len(degraded) == 8, f"全降级 degraded_steps={degraded}"
