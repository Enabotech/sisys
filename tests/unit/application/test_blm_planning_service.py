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
    MARKET_INSIGHT_STEP_SCHEMA,
    PERFORMANCE_GAP_CONFIG,
    CompetitionInsightSchema,
    GapAnalysisSchema,
    InsightSynthesisSchema,
    MarketCustomerInsightSchema,
    OpportunityGapInsightSchema,
    OpportunityInsightSchema,
    SelfInsightSchema,
    TrendInsightSchema,
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

#: 六类型化 Schema 全族（calls 过滤与全量 fail 注入共用——SSOT 映射取值族；
#: 6-2 三 Fake 适配后分派键 = GapAnalysis + 六类型化 + InsightSynthesis 八键族）
TYPED_STEP_SCHEMAS: frozenset[type] = frozenset(MARKET_INSIGHT_STEP_SCHEMA.values())


# ===================================================================
# Fake LLM（BLM 面三 Schema 分派 + 失败注入 + 配置捕获）
# ===================================================================


def _make_fake_llm(
    *,
    fail_schemas: frozenset[type] = frozenset(),
    fail_first_calls: int = 0,
    empty_synthesis: bool = False,
    config_error: bool = False,
    corrupt_schemas: frozenset[type] = frozenset(),
) -> Any:
    """BLM 面 Fake LLM（AsyncMock spec=LLMClientPort——外部 SaaS 豁免替身）。

    Args:
        fail_schemas: 对指定 Schema 恒抛 LLMAPIError（降级终态注入）。
        fail_first_calls: 前 N 次调用抛 LLMAPIError（瞬时故障——重试后成功）。
        empty_synthesis: synthesis 分派返回空 conclusions（R1-10② 空结论形态）。
        config_error: 每次调用抛 LLMConfigError（R1-10④ 确定性配置错误形态）。
        corrupt_schemas: 对指定 Schema 返回非 Schema 实例（结构守卫 444 非瞬时
            ——校验失败降级路径注入，6-2 AC-4）。
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
        if response_schema in corrupt_schemas:
            return object()  # 非 Schema 实例（isinstance 守卫 444——结构守卫失败非瞬时）
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
        # 六类型化 Schema 分派（6-2——summary 带「市场洞察步骤摘要:{step}」分步
        # 标记（R1-F10——仿验收 _FAKE_STEP_SUMMARY_PREFIX 形态），count 断言锚与
        # 分步断言双消费；返回体字段族与冻结表逐字段对齐）
        if response_schema is TrendInsightSchema:
            return TrendInsightSchema(
                summary="市场洞察步骤摘要:trend",
                findings=["发现一", "发现二"],
                pestel_political="政策维度评估",
                pestel_economic="经济维度评估",
                pestel_social="社会维度评估",
                pestel_technological="技术维度评估",
                pestel_environmental="环境维度评估",
                pestel_legal="法律维度评估",
                technology_roadmap=["技术演进要点"],
                scenario_plans=["情景规划要点"],
            )
        if response_schema is MarketCustomerInsightSchema:
            return MarketCustomerInsightSchema(
                summary="市场洞察步骤摘要:market_customer",
                findings=["发现一", "发现二"],
                customer_segments=["细分群体要点"],
                demand_priority_matrix=["需求优先要点"],
                value_proposition_map=["价值主张要点"],
            )
        if response_schema is CompetitionInsightSchema:
            return CompetitionInsightSchema(
                summary="市场洞察步骤摘要:competition",
                findings=["发现一", "发现二"],
                five_forces_supplier_power="供应商议价能力评估",
                five_forces_buyer_power="购买者议价能力评估",
                five_forces_new_entrants="新进入者威胁评估",
                five_forces_substitutes="替代品威胁评估",
                five_forces_rivalry="现有竞争者强度评估",
                competitor_radar=["能力雷达要点"],
                strategy_recommendations=["竞争策略要点"],
            )
        if response_schema is SelfInsightSchema:
            return SelfInsightSchema(
                summary="市场洞察步骤摘要:self",
                findings=["发现一", "发现二"],
                internal_capabilities=["内部能力要点"],
                vrio_assessment=["VRIO 评估要点"],
                resource_constraints=["资源约束要点"],
            )
        if response_schema is OpportunityInsightSchema:
            return OpportunityInsightSchema(
                summary="市场洞察步骤摘要:opportunity",
                findings=["发现一", "发现二"],
                opportunity_list=["机会要点"],
                priority_ranking=["优先级要点"],
                growth_path=["增长路径要点"],
            )
        if response_schema is OpportunityGapInsightSchema:
            return OpportunityGapInsightSchema(
                summary="市场洞察步骤摘要:opportunity_gap",
                findings=["发现一", "发现二"],
                gap_quantification=["差距量化要点"],
                capability_match_matrix=["匹配矩阵要点"],
                closure_strategies=["弥合策略要点"],
            )
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
    chain_archive: Any | None = None,
) -> tuple[BlmPlanningService, dict[str, Any]]:
    """构造被测服务 + mock 依赖字典。

    Args:
        fake_llm: Fake LLM（缺省新造）。
        guard_error: 隔离预检注入异常（449 触发面）。
        registry_error: 工具注册注入异常（380 触发面）。
        search_error: 检索注入异常（检索失败降级面）。
        chain_archive: 思维链归档服务替身（6-4 挂接注入——None 即尾参缺席
            等价性形态，既有用例零适配先例）。
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
        chain_archive_service=chain_archive,
    )
    return service, {
        "llm": llm,
        "tool_execution": tool_execution,
        "registry": registry,
        "guard": guard,
        "hybrid": hybrid,
        "snapshot_repo": snapshot_repo,
        "publisher": publisher,
        "chain_archive": chain_archive,
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

    async def test_system_prompt_injects_tools_l1_tool_name(self) -> None:
        """system 面注入档案 tools_l1 全量（DC-5）——真实 ToolMetadata 字段口径（R2-1）。

        ToolMetadata 字段是 tool_name（非 name）——字段错配即 system_prompt
        恒空转（R2-1 判定的生产断裂形态）。
        """
        from src.application.ports.skill_loader import ToolMetadata

        profile = MagicMock()
        profile.agent_id = AGENT_ID
        profile.tools_l1 = (
            ToolMetadata(tool_name="PESTEL 分析", slug="pestel-analysis", category="market", input_schema={}, output_schema={}),
            ToolMetadata(tool_name="SWOT-TOWS", slug="swot-tows", category="strategy", input_schema={}, output_schema={}),
        )
        context = BlmPlanningContext(plan_id=PLAN_ID, agent_id=AGENT_ID, profile_result=profile, task=TASK)
        service, mocks = _make_service()
        await service.run_performance_gap_analysis(context)
        system_prompt = mocks["llm"]._state["calls"][0].get("system_prompt")
        assert system_prompt, "system_prompt 不应为空（tools_l1 全量注入——DC-5，R2-1）"
        assert "PESTEL 分析" in system_prompt and "SWOT-TOWS" in system_prompt, (
            "system 面应含 tool_name 清单（字段口径 tool_name——R2-1）"
        )

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
        """工具成功步 tool_used 回填 slug + evidence_refs 回填检索命中 id（VO 契约，R1-10⑤/R2-2）。"""
        service, _mocks = _make_service()
        result = await service.run_insight_step(MarketInsightStep.TREND, _make_context(), {})
        assert result.tool_used == "swot-tows", "工具成功步应回填 slug（tool.slug 口径钦定）"
        assert result.evidence_refs == ("chunk-001",), "检索命中的证据 id 应回填 evidence_refs（R2-2）"

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
        step_calls = [c for c in mocks["llm"]._state["calls"] if c["schema"] in TYPED_STEP_SCHEMAS]
        assert len(step_calls) == 6
        for call, (step, config) in zip(step_calls, MARKET_INSIGHT_STEP_CONFIG.items()):
            assert config.role_prefix in call["prompt"], f"{step.value} prompt 缺视角前缀"
            for slug in config.tool_candidates:
                assert slug in call["prompt"], f"{step.value} prompt 缺工具候选 {slug}（全量白名单注入——R1-9⑤）"

    async def test_each_step_temperature_profile(self) -> None:
        """每步温度档=配置表钦定（8 步温度映射唯一源）。"""
        service, mocks = _make_service()
        await _run_six_steps(service, _make_context())
        step_calls = [c for c in mocks["llm"]._state["calls"] if c["schema"] in TYPED_STEP_SCHEMAS]
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
        """注入侧锚：synthesis prompt 含六步产物摘要（漏传/错配/重复注入任一形态可判别——R1-F10 分步标记）。"""
        service, mocks = _make_service()
        context = _make_context()
        steps = await _run_six_steps(service, context)
        await service.synthesize_insights({"insight_steps": tuple(steps)}, context)
        synthesis_calls = [c for c in mocks["llm"]._state["calls"] if c["schema"] is InsightSynthesisSchema]
        assert synthesis_calls
        prompt = synthesis_calls[-1]["prompt"]
        # 六步 Fake 产出均含「市场洞察步骤摘要」标记——prompt 注入面可见
        assert prompt.count("市场洞察步骤摘要") == 6, "synthesis prompt 未含全部六步摘要"
        # 分步标记逐一断言（Fake summary 带步名——错配/重复注入时计数形断言
        # 不红、分步断言红；R1-F10）
        for step_value in ("trend", "market_customer", "competition", "self", "opportunity", "opportunity_gap"):
            assert f"市场洞察步骤摘要:{step_value}" in prompt, f"synthesis prompt 缺 {step_value} 分步摘要（R1-F10）"

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
        llm = _make_fake_llm(fail_schemas=TYPED_STEP_SCHEMAS)
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

    async def test_tool_degraded_step_keeps_structured_output(self) -> None:
        """工具面降级 + LLM 成功 → structured_output 非 None（R1-F1 收窄口径钉语义：
        None ⟺ LLM 调用/校验失败；工具/检索面降级而 LLM 成功时与 summary/findings
        非空对称——信封三字段同进退，6-3 读侧禁按「degraded ⇒ null」建模）。"""
        service, _mocks = _make_service(
            guard_error=IsolationOperationForbiddenError(
                agent_id=str(AGENT_ID), operation="tool_access", reason="tool_not_in_allowlist:swot-tows"
            )
        )
        result = await service.run_insight_step(MarketInsightStep.TREND, _make_context(), {})
        assert result.degraded is True, "工具面降级标记"
        assert result.degrade_reason, "工具面降级原因非空"
        assert result.summary, "直接推理续行——LLM 产物非空"
        assert result.structured_output is not None, "工具面降级不丢弃类型化产物（R1-F1）"
        assert result.structured_output["summary"] == result.summary, "信封与产物同源"

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
        llm = _make_fake_llm(fail_schemas=TYPED_STEP_SCHEMAS)
        service, mocks = _make_service(llm)
        context = _make_context()
        first = await service.run_insight_step(MarketInsightStep.TREND, context, {})
        assert first.degraded
        # 第二步：prior_outputs 含降级产物
        await service.run_insight_step(MarketInsightStep.MARKET_CUSTOMER, context, {"insight_steps": (first,)})
        step_calls = [c for c in mocks["llm"]._state["calls"] if c["schema"] in TYPED_STEP_SCHEMAS]
        # 按步骤名定位「看市场与客户」首次调用（TREND 失败含重试会占多个 calls 槽位）
        market_customer_calls = [c for c in step_calls if "看市场与客户" in c["prompt"]]
        assert market_customer_calls, "未捕获看市场与客户步骤调用"
        second_prompt = market_customer_calls[0]["prompt"]
        assert "降级" in second_prompt, "下游 prompt 未含降级标注（⑥规则 1）"

    async def test_synthesis_lists_degraded_inputs(self) -> None:
        """规则 2：synthesis 结论必须列举 degraded 输入（不可无标注吞并）。"""
        llm = _make_fake_llm(fail_schemas=TYPED_STEP_SCHEMAS)
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
        trend_calls = [c for c in mocks["llm"]._state["calls"] if c["schema"] is TrendInsightSchema and "看趋势" in c["prompt"]]
        assert trend_calls, "未捕获看趋势步骤调用"
        assert "[降级] 步骤 performance_gap 降级" in trend_calls[0]["prompt"], "gap 降级标注未注入阶段 2 prompt"
        # 综合报告携带标记：degraded_inputs 含 performance_gap（规则 3 半句）
        synthesis = await service.synthesize_insights({"insight_steps": tuple(steps), "performance_gap": gap}, context)
        assert "performance_gap" in synthesis.degraded_inputs, "综合报告未携带阶段 1 降级标记（规则 3）"

    async def test_gap_normal_summary_injected_into_phase2_prompt(self) -> None:
        """规则 1 正常形态：gap 非 None 非 degraded → 阶段 2 prompt 含 gap 摘要段（R2-3）。"""
        service, mocks = _make_service()
        context = _make_context()
        gap = await service.run_performance_gap_analysis(context)
        assert not gap.degraded
        await service.run_insight_step(MarketInsightStep.TREND, context, {"performance_gap": gap, "insight_steps": ()})
        trend_calls = [c for c in mocks["llm"]._state["calls"] if c["schema"] is TrendInsightSchema and "看趋势" in c["prompt"]]
        assert trend_calls, "未捕获看趋势步骤调用"
        assert "阶段 1 业绩差距分析产物摘要" in trend_calls[0]["prompt"], "gap 正常摘要段未注入阶段 2 prompt（R2-3）"
        assert "财务差距=" in trend_calls[0]["prompt"], "gap 摘要应含财务差距标签（四字段全量形态——财务差距=子串兼容锚，R2-3）"

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
        """latest 快照 state_data 契约（session_id=前缀+plan_id；timeline 六键）。

        6-2 适配：save 调用含 latest 与 per-step 双键族——本用例守卫 latest 形态
        （session_id 无后缀），per-step 七键契约归 TestStepCheckpoint。"""
        service, mocks = _make_service()
        context = _make_context()
        await service.run_performance_gap_analysis(context)
        await service.run_insight_step(MarketInsightStep.TREND, context, {"insight_steps": ()})
        save_calls = mocks["snapshot_repo"].save.await_args_list
        assert save_calls, "快照未写入"
        latest_saves = [c.args[0] for c in save_calls if c.args[0].session_id == f"{BLM_PLANNING_SESSION_PREFIX}{PLAN_ID}"]
        assert latest_saves, "latest 快照未写入"
        for snapshot in latest_saves:
            data = snapshot.state_data
            assert data["plan_id"] == PLAN_ID
            assert data["total_steps"] == 8
            for entry in data["timeline"]:
                assert set(entry) == {"step", "started_at", "completed_at", "status", "summary_excerpt", "degraded"}

    async def test_latest_snapshot_form_unchanged(self) -> None:
        """latest 快照 save 调用形态与 6-1 一致（per-step 新增不污染 latest 键——零回归锚）。"""
        service, mocks = _make_service()
        context = _make_context()
        await service.run_performance_gap_analysis(context)
        await service.run_insight_step(MarketInsightStep.TREND, context, {"insight_steps": ()})
        from src.application.ports.blm_planning import BLM_PLANNING_SNAPSHOT_STAGE

        save_calls = mocks["snapshot_repo"].save.await_args_list
        latest_saves = [c.args[0] for c in save_calls if c.args[0].session_id == f"{BLM_PLANNING_SESSION_PREFIX}{PLAN_ID}"]
        assert latest_saves, "latest 快照写入缺失（6-1 行为回归）"
        for snapshot in latest_saves:
            assert snapshot.stage_id == BLM_PLANNING_SNAPSHOT_STAGE
            assert snapshot.ttl_seconds == 86400, "TTL 沿用 CheckpointSnapshot 既有默认 86400"


# ===================================================================
# 6-2 循环 A：类型化分派 + structured_output 填充
# ===================================================================


#: 六步专属 Schema 名期望（独立构造字面量——与 SSOT 表解耦，禁 import 反射自证）
EXPECTED_TYPED_SCHEMA_NAMES: tuple[str, ...] = (
    "TrendInsightSchema",
    "MarketCustomerInsightSchema",
    "CompetitionInsightSchema",
    "SelfInsightSchema",
    "OpportunityInsightSchema",
    "OpportunityGapInsightSchema",
)

#: trend 步 structured_output 期望键族（独立构造——model_dump 键域断言锚）
EXPECTED_TREND_DUMP_KEYS: frozenset[str] = frozenset(
    {
        "summary",
        "findings",
        "pestel_political",
        "pestel_economic",
        "pestel_social",
        "pestel_technological",
        "pestel_environmental",
        "pestel_legal",
        "technology_roadmap",
        "scenario_plans",
    }
)


class TestTypedSchemaDispatch:
    """6-2 类型化分派（SSOT 映射查表——服务层零 if-else 硬编码）。"""

    async def test_each_step_dispatches_dedicated_schema(self) -> None:
        """六步调用按执行序各传该步专属类型化 Schema（Fake calls 记录断言）。"""
        service, mocks = _make_service()
        await _run_six_steps(service, _make_context())
        typed_name_set = set(EXPECTED_TYPED_SCHEMA_NAMES)
        step_calls = [c for c in mocks["llm"]._state["calls"] if c["schema"].__name__ in typed_name_set]
        assert len(step_calls) == 6, f"六类型化调用应恰 6 次（实际 {len(step_calls)}）"
        for call, expected_name in zip(step_calls, EXPECTED_TYPED_SCHEMA_NAMES):
            assert call["schema"].__name__ == expected_name, (
                f"应分派 {expected_name}（实际 {call['schema'].__name__}——硬编码/错配嫌疑）"
            )

    async def test_structured_output_filled_with_model_dump_keys(self) -> None:
        """类型化结果填充 structured_output（键域=Schema 字段族；信封同源双公共字段）。"""
        service, _mocks = _make_service()
        results = await _run_six_steps(service, _make_context())
        for step_result in results:
            structured = getattr(step_result, "structured_output", None)
            assert structured is not None, f"步骤 {step_result.step} structured_output 未填充"
            assert structured["summary"] == step_result.summary, "summary 与信封不同源（R3-1）"
            assert list(structured["findings"]) == list(step_result.findings), "findings 与信封不同源（R3-1）"
        trend = next(r for r in results if r.step == "trend")
        assert set(trend.structured_output) == EXPECTED_TREND_DUMP_KEYS, (
            f"trend dump 键族不一致: {set(trend.structured_output) ^ EXPECTED_TREND_DUMP_KEYS}"
        )

    async def test_invalid_schema_instance_degrades_step(self) -> None:
        """校验失败（返回非 Schema 实例→结构守卫 444 非瞬时）→ 完整降级信封 +
        structured_output=None，流程继续（其余步正常）。"""
        from src.application.services.blm_planning_prompts import TrendInsightSchema

        llm = _make_fake_llm(corrupt_schemas=frozenset({TrendInsightSchema}))
        service, _mocks = _make_service(llm)
        results = await _run_six_steps(service, _make_context())
        by_step = {r.step: r for r in results}
        degraded = by_step["trend"]
        assert degraded.degraded is True, "非法实例步应降级（结构守卫 444）"
        assert degraded.degrade_reason, "降级原因非空（完整信封）"
        assert degraded.structured_output is None, "降级步 structured_output 应 None"
        for step_value in ("market_customer", "competition", "self", "opportunity", "opportunity_gap"):
            assert by_step[step_value].degraded is False, f"{step_value} 应正常（互不传染）"
            assert by_step[step_value].structured_output is not None

    async def test_degraded_step_structured_output_none(self) -> None:
        """LLM 持续失败降级步 structured_output=None（None ⟺ LLM 调用/校验失败——AC-4；
        工具/检索面降级而 LLM 成功时非 None——见 test_tool_degraded_step_keeps_structured_output）。"""
        from src.application.services.blm_planning_prompts import MARKET_INSIGHT_STEP_SCHEMA

        llm = _make_fake_llm(fail_schemas=frozenset(MARKET_INSIGHT_STEP_SCHEMA.values()))
        service, _mocks = _make_service(llm)
        results = await _run_six_steps(service, _make_context())
        for step_result in results:
            assert step_result.degraded is True
            assert step_result.structured_output is None, "LLM 失败降级步 structured_output 应 None"


# ===================================================================
# 6-2 循环 B：per-step Checkpoint 快照写入
# ===================================================================

#: per-step state_data 七键期望（独立构造——端口文件第三级契约镜像）
EXPECTED_STEP_SNAPSHOT_KEYS: frozenset[str] = frozenset(
    {
        "step",
        "plan_id",
        "summary",
        "structured_output",
        "degraded",
        "degrade_reason",
        "completed_steps",
    }
)


class TestStepCheckpoint:
    """per-step Checkpoint 快照骨架（AC-2——6-3 恢复点位数据面）。"""

    async def test_per_step_snapshot_written_for_each_step(self) -> None:
        """每步完成时额外 save 一份 per-step 快照（session_id 后缀/stage_id/state_data 七键）。"""
        service, mocks = _make_service()
        context = _make_context()
        await service.run_performance_gap_analysis(context)
        results = await _run_six_steps(service, context)
        save_calls = mocks["snapshot_repo"].save.await_args_list
        per_step_saves = {c.args[0].session_id: c.args[0] for c in save_calls if f"{PLAN_ID}:" in c.args[0].session_id}
        assert len(per_step_saves) == 6, f"per-step 快照应恰 6 份（实际 {len(per_step_saves)}）"
        for step_result in results:
            session_id = f"{BLM_PLANNING_SESSION_PREFIX}{PLAN_ID}:{step_result.step}"
            assert session_id in per_step_saves, f"{step_result.step} per-step 快照缺失"
            snapshot = per_step_saves[session_id]
            assert snapshot.stage_id == f"market_insight_{step_result.step}", (
                f"{step_result.step} stage_id={snapshot.stage_id} 错配"
            )
            assert set(snapshot.state_data) == EXPECTED_STEP_SNAPSHOT_KEYS, (
                f"{step_result.step} state_data 键族不一致: {set(snapshot.state_data) ^ EXPECTED_STEP_SNAPSHOT_KEYS}"
            )
            assert snapshot.state_data["step"] == step_result.step
            assert snapshot.state_data["plan_id"] == PLAN_ID
            assert snapshot.state_data["structured_output"] is not None

    async def test_completed_steps_list_includes_gap_and_current(self) -> None:
        """completed_steps 为含该步的已完成步骤标识清单（timeline 裸 step 值口径——R1-F5
        校准；首步即含 performance_gap——R1-6 钉死）。"""
        service, mocks = _make_service()
        context = _make_context()
        await service.run_performance_gap_analysis(context)
        await service.run_insight_step(MarketInsightStep.TREND, context, {"insight_steps": ()})
        trend_save = next(
            c.args[0]
            for c in mocks["snapshot_repo"].save.await_args_list
            if c.args[0].session_id == f"{BLM_PLANNING_SESSION_PREFIX}{PLAN_ID}:trend"
        )
        assert trend_save.state_data["completed_steps"] == ["performance_gap", "trend"], (
            f"首步 completed_steps 应含阶段 1 与该步（timeline step 口径——R1-6 自然实现）: "
            f"{trend_save.state_data['completed_steps']}"
        )

    async def test_degraded_step_snapshot_contains_marker(self) -> None:
        """LLM 失败降级步同样触发 per-step 快照（degraded 标记 + structured_output 键恒在、值为 None）。"""
        from src.application.services.blm_planning_prompts import TrendInsightSchema

        llm = _make_fake_llm(fail_schemas=frozenset({TrendInsightSchema}))
        service, mocks = _make_service(llm)
        context = _make_context()
        await _run_six_steps(service, context)
        trend_save = next(
            c.args[0]
            for c in mocks["snapshot_repo"].save.await_args_list
            if c.args[0].session_id == f"{BLM_PLANNING_SESSION_PREFIX}{PLAN_ID}:trend"
        )
        state = trend_save.state_data
        assert state["degraded"] is True, "降级标记未入 state_data"
        assert state["degrade_reason"], "降级原因未入 state_data"
        assert "structured_output" in state, "structured_output 键缺失（键恒在契约）"
        assert state["structured_output"] is None, "LLM 失败降级步 structured_output 应 None"

    async def test_per_step_snapshot_write_failure_swallowed(self) -> None:
        """per-step 快照写入异常被吞且流程不中断（容错——与 latest 同语义）。"""
        service, mocks = _make_service()
        context = _make_context()

        original_save = mocks["snapshot_repo"].save

        async def _failing_save(snapshot: Any) -> None:
            """per-step 键写入抛异常；latest 键正常（双契约分离容错验证）。"""
            if f"{PLAN_ID}:" in snapshot.session_id:
                raise RuntimeError("Redis 写入失败（注入）")
            await original_save(snapshot)

        mocks["snapshot_repo"].save.side_effect = _failing_save
        results = await _run_six_steps(service, context)
        assert len(results) == 6, "per-step 写入失败不应中断流程"
        assert all(r.summary for r in results), "全部步骤产物正常（容错不降级）"

    async def test_per_step_snapshot_ttl_default(self) -> None:
        """TTL 沿用 CheckpointSnapshot 既有默认 86400（6-3 升级 30 天——OD-1）。"""
        service, mocks = _make_service()
        context = _make_context()
        await service.run_insight_step(MarketInsightStep.TREND, context, {"insight_steps": ()})
        trend_save = next(
            c.args[0]
            for c in mocks["snapshot_repo"].save.await_args_list
            if c.args[0].session_id == f"{BLM_PLANNING_SESSION_PREFIX}{PLAN_ID}:trend"
        )
        assert trend_save.ttl_seconds == 86400


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

    async def test_engine_rerun_same_plan_id_raises_482(self) -> None:
        """482 图链路组合锚（R3-1）：同 plan_id 经真实引擎二次 submit → PlanningStateError 穿透。

        服务层锚（test_same_plan_id_rerun_rejected_482）+ 引擎泛图透传锚之外，
        SpBlmGraph×482 组合面固化：节点抛领域异常 → 引擎 DomainError re-raise
        （非 RuntimeError 包装、非 481 终态缺失掩盖）。
        """
        from src.domain.exceptions.planning_exceptions import PlanningStateError

        service, _mocks = _make_service()
        engine = _make_engine(service)
        parameters = {"agent_id": str(AGENT_ID), "plan_id": PLAN_ID, "task": TASK, "context": _make_context()}
        first_run = await engine.submit_graph("SpBlmGraph", parameters)
        assert await engine.get_graph_result(first_run) is not None
        with pytest.raises(PlanningStateError) as exc_info:
            await engine.submit_graph("SpBlmGraph", parameters)
        assert exc_info.value.code == "EXCEPTION_482"
        assert "重跑" in str(exc_info.value.message) or "重跑" in str(exc_info.value)

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
        llm = _make_fake_llm(fail_schemas=frozenset({GapAnalysisSchema, InsightSynthesisSchema}) | TYPED_STEP_SCHEMAS)
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


# ===================================================================
# Story 6-4：思维链挂接用例族（三方法挂接/回传三件套/尾参可选等价性守护）
# ===================================================================


def _make_chain_archive_mock(*, return_none: bool = False, raise_error: BaseException | None = None) -> Any:
    """思维链归档服务替身工厂（AsyncMock(spec=端口协议)——单元测试 Mock 红线）。

    Args:
        return_none: compose_and_archive_step_chain 恒返回 None（445 组装
            失败降级面——chain 缺席台账注入）。
        raise_error: compose_and_archive_step_chain 抛出注入异常（CR1-F6
            挂接段宽捕兜底面——非 284/445 意外形态降级续行注入）。
    """
    from src.application.ports.chain_of_thought_archive import (
        ChainOfThoughtArchiveServicePort,
        ChainRecord,
    )
    from src.application.services.chain_of_thought_archive_service import compose_step_chain

    mock = AsyncMock(spec=ChainOfThoughtArchiveServicePort)
    if raise_error is not None:
        mock.compose_and_archive_step_chain = AsyncMock(side_effect=raise_error)
    elif return_none:
        mock.compose_and_archive_step_chain = AsyncMock(return_value=None)
    else:
        mock.compose_and_archive_step_chain = AsyncMock(
            side_effect=lambda plan_id, stage, material: ChainRecord(
                stage=stage,
                chain=compose_step_chain(material),
                archived=True,
                archive_id=f"archive-{stage}",
            )
        )
    mock.query_chain_trace = AsyncMock(return_value=None)
    return mock


def _make_chain_context() -> BlmPlanningContext:
    """UUID 形态 plan_id 上下文（挂接测试专用——归档是首个 UUID 硬消费方 R3-F4，
    既有 PLAN_ID='plan-test-1' 非 UUID 会被守卫正确拒绝）。"""
    profile = MagicMock()
    profile.agent_id = AGENT_ID
    return BlmPlanningContext(plan_id=str(uuid.uuid4()), agent_id=AGENT_ID, profile_result=profile, task=TASK)


class TestChainArchiveHookup:
    """6-4 挂接用例族（尾参可选注入 + 三方法挂接段 + 素材采集判别）。"""

    def test_tail_param_none_keeps_service_construction(self) -> None:
        """尾参 None 等价性守护（构造成功——既有 6-1/6-2 用例零适配的基座）。"""
        service, mocks = _make_service()
        assert service is not None
        assert mocks["chain_archive"] is None

    async def test_gap_method_hooks_chain_archive(self) -> None:
        """gap 方法挂接：末尾触发组装归档（stage 锚+素材采集判别——R1-F3 gap 型）。"""
        chain_mock = _make_chain_archive_mock()
        service, _mocks = _make_service(chain_archive=chain_mock)
        context = _make_chain_context()
        await service.run_performance_gap_analysis(context)
        chain_mock.compose_and_archive_step_chain.assert_awaited_once()
        args = chain_mock.compose_and_archive_step_chain.await_args.args
        plan_uuid, stage, material = args
        assert plan_uuid == uuid.UUID(context.plan_id)
        assert stage == "performance_gap"
        assert material.stage == "performance_gap"
        assert material.display_name == "业绩差距分析"
        assert material.tool_slug == "swot-tows"  # 执行轨迹第三位单数 slug（mock registry slug 在位）
        assert material.evidence_count == 1  # hybrid mock 单条命中
        assert material.findings_count == 2  # root_causes 计数（单测 Fake gap 两根因）
        assert material.structured_ok is True
        assert set(material.payload) == {
            "financial_gap",
            "operational_gap",
            "root_causes",
            "portfolio_health",
            "degraded",
            "degrade_reason",
        }

    async def test_insight_step_hooks_chain_archive(self) -> None:
        """六子方法挂接：stage 前缀拼装公式 + 素材采集判别（R3-F7/R1-F3）。"""
        chain_mock = _make_chain_archive_mock()
        service, _mocks = _make_service(chain_archive=chain_mock)
        context = _make_chain_context()
        await service.run_insight_step(MarketInsightStep.TREND, context, {"performance_gap": None, "insight_steps": ()})
        chain_mock.compose_and_archive_step_chain.assert_awaited_once()
        _, stage, material = chain_mock.compose_and_archive_step_chain.await_args.args
        assert stage == "market_insight_trend"
        assert material.display_name == "看趋势"
        assert material.role_prefix == "以 CEO 宏观趋势判断与 CTO 技术趋势分析的双重视角"
        assert material.tool_slug == "swot-tows"
        assert material.findings_count == 2  # Fake trend findings 2 条
        assert "summary" in material.payload and "findings" in material.payload

    async def test_synthesis_hooks_chain_archive(self) -> None:
        """synthesis 方法挂接：模块常量语义 + 无工具无检索素材形态。"""
        chain_mock = _make_chain_archive_mock()
        service, _mocks = _make_service(chain_archive=chain_mock)
        context = _make_chain_context()
        results = await _run_six_steps(service, context)
        await service.synthesize_insights({"insight_steps": tuple(results), "performance_gap": None}, context)
        chain_mock.compose_and_archive_step_chain.assert_awaited()
        _, stage, material = chain_mock.compose_and_archive_step_chain.await_args.args
        assert stage == "market_insight_synthesis"
        assert material.display_name == "市场洞察综合"
        assert material.role_prefix == "CMO"
        assert material.tool_slug == ""  # synthesis 无工具
        assert material.evidence_count == 0  # synthesis 无检索
        assert set(material.payload) == {"conclusions", "degraded_inputs"}

    async def test_full_eight_steps_accumulate_chain_records(self) -> None:
        """全链 8 步累积（run_state.chain_records——回传三件套①）。"""
        chain_mock = _make_chain_archive_mock()
        service, _mocks = _make_service(chain_archive=chain_mock)
        context = _make_chain_context()
        await service.run_performance_gap_analysis(context)
        results = await _run_six_steps(service, context)
        await service.synthesize_insights({"insight_steps": tuple(results), "performance_gap": None}, context)
        assert chain_mock.compose_and_archive_step_chain.await_count == 8
        projected = service.project_chain_records(context.plan_id)
        assert len(projected) == 8
        assert [record.stage for record in projected] == [
            "performance_gap",
            "market_insight_trend",
            "market_insight_market_customer",
            "market_insight_competition",
            "market_insight_self",
            "market_insight_opportunity",
            "market_insight_opportunity_gap",
            "market_insight_synthesis",
        ]

    async def test_none_chain_archive_zero_hookup_calls(self) -> None:
        """尾参 None 时零挂接（与现状逐字节等价——快照/事件行为不变）。"""
        service, mocks = _make_service()  # chain_archive=None
        context = _make_context()
        await service.run_performance_gap_analysis(context)
        await _run_six_steps(service, context)
        assert mocks["snapshot_repo"].save.await_count == 13  # gap latest×1 + 六子（per-step+latest）×6
        assert service.project_chain_records(PLAN_ID) == []

    async def test_compose_none_skips_append(self) -> None:
        """compose 返回 None（445 降级）时跳过追加（chain 缺席台账——R1-F5）。"""
        chain_mock = _make_chain_archive_mock(return_none=True)
        service, _mocks = _make_service(chain_archive=chain_mock)
        context = _make_chain_context()
        await service.run_performance_gap_analysis(context)
        chain_mock.compose_and_archive_step_chain.assert_awaited_once()
        assert service.project_chain_records(context.plan_id) == []  # None 不追加

    async def test_compose_unexpected_error_degrades_and_continues(self) -> None:
        """compose 抛非 284/445 意外异常时宽捕降级续行（CR1-F6——OD-5 完整捕获面）。

        RuntimeError 注入钉死宽捕形态：日后有人收窄为 except DomainError 必红
        （RuntimeError 非 DomainError 系——判别力锚）。
        """
        chain_mock = _make_chain_archive_mock(raise_error=RuntimeError("归档链路意外故障（注入）"))
        service, _mocks = _make_service(chain_archive=chain_mock)
        context = _make_chain_context()
        artifacts = await service.run_performance_gap_analysis(context)  # 不抛异常即过
        assert artifacts is not None  # 领域产物不因观测面失败丢弃
        chain_mock.compose_and_archive_step_chain.assert_awaited_once()
        assert service.project_chain_records(context.plan_id) == []  # 意外形态 chain 缺席台账

    async def test_hookup_keeps_snapshot_and_event_calls_unchanged(self) -> None:
        """挂接不改变快照写与事件发布调用次数（可观测面非流程面——OD-5）。"""
        context_none = _make_context()
        service_none, mocks_none = _make_service()
        await service_none.run_performance_gap_analysis(context_none)
        snapshot_calls_none = mocks_none["snapshot_repo"].save.await_count
        event_calls_none = mocks_none["publisher"].publish.await_count

        context_hooked = _make_context()
        chain_mock = _make_chain_archive_mock()
        service_hooked, mocks_hooked = _make_service(chain_archive=chain_mock)
        await service_hooked.run_performance_gap_analysis(context_hooked)
        assert mocks_hooked["snapshot_repo"].save.await_count == snapshot_calls_none
        assert mocks_hooked["publisher"].publish.await_count == event_calls_none

    async def test_malformed_plan_id_degrades_without_exception(self) -> None:
        """畸形 plan_id UUID 守卫（R3-F4——转换失败该步 chain 缺席+降级续行）。"""
        chain_mock = _make_chain_archive_mock()
        service, _mocks = _make_service(chain_archive=chain_mock)
        context = BlmPlanningContext(plan_id="not-a-uuid", agent_id=AGENT_ID, profile_result=MagicMock(), task=TASK)
        artifacts = await service.run_performance_gap_analysis(context)  # 不抛异常即过
        assert artifacts is not None
        chain_mock.compose_and_archive_step_chain.assert_not_awaited()  # 守卫先于归档调用
        assert service.project_chain_records("not-a-uuid") == []

    async def test_archive_failure_ledger_appended(self) -> None:
        """归档失败 284 台账（archived=False 的 ChainRecord 仍追加——失败可见可数）。"""

        chain_mock = _make_chain_archive_mock()
        chain_mock.compose_and_archive_step_chain = AsyncMock(
            side_effect=lambda plan_id, stage, material: _record_with(stage, archived=False, archive_id="")
        )
        service, _mocks = _make_service(chain_archive=chain_mock)
        context = _make_chain_context()
        await service.run_performance_gap_analysis(context)
        projected = service.project_chain_records(context.plan_id)
        assert len(projected) == 1
        assert projected[0].archived is False
        assert projected[0].archive_id == ""


def _record_with(stage: str, *, archived: bool, archive_id: str) -> Any:
    """构造 ChainRecord（归档失败台账形态——链构造辅助）。"""
    from src.application.ports.chain_of_thought_archive import ChainRecord
    from src.domain.value_objects.chain_of_thought import ChainOfThought

    return ChainRecord(
        stage=stage,
        chain=ChainOfThought(
            input_summary=f"input-{stage}",
            reflection=f"reflection-{stage}",
            tools_used=(),
            constraints_check="constraints",
            final_answer='{"stage": "%s"}' % stage,
        ),
        archived=archived,
        archive_id=archive_id,
    )


class TestChainGraphWiring:
    """6-4 回传三件套③（图适配器直写）+ AgentDecided 投影真实化（循环 B）。"""

    async def test_graph_final_state_carries_eight_chains(self) -> None:
        """图终态 chain_records 恰 8 条（三类节点适配器直写行活着——R1-F1③）。"""
        chain_mock = _make_chain_archive_mock()
        plan_id = str(uuid.uuid4())
        service, _mocks = _make_service(chain_archive=chain_mock)
        engine = _make_engine(service)
        profile = MagicMock()
        profile.agent_id = AGENT_ID
        run_id = await engine.submit_graph(
            "SpBlmGraph",
            {
                "agent_id": str(AGENT_ID),
                "plan_id": plan_id,
                "task": TASK,
                "context": BlmPlanningContext(plan_id=plan_id, agent_id=AGENT_ID, profile_result=profile, task=TASK),
            },
        )
        final_state = await engine.get_graph_result(run_id)
        assert final_state is not None
        chain_records = final_state.get("chain_records")
        assert chain_records is not None, "终态 state 缺 chain_records 键（适配器直写行缺失——R1-F1③）"
        assert len(chain_records) == 8, f"图终态 chain_records={len(chain_records)} 条 期望=8"
        assert isinstance(chain_records, list)  # state 承载 list（投影返回——R2-F5 读侧归一归用例）

    async def test_agent_decided_chain_summary_realized_from_last_chain(self) -> None:
        """投影 chain_summary == 末条思维链 final_answer[:200]（值级断言——AC-2）。"""
        from src.application.services.chain_of_thought_archive_service import compose_step_chain

        chain_mock = _make_chain_archive_mock()
        plan_id = str(uuid.uuid4())
        service, _mocks = _make_service(chain_archive=chain_mock)
        engine = _make_engine(service)
        profile = MagicMock()
        profile.agent_id = AGENT_ID
        run_id = await engine.submit_graph(
            "SpBlmGraph",
            {
                "agent_id": str(AGENT_ID),
                "plan_id": plan_id,
                "task": TASK,
                "context": BlmPlanningContext(plan_id=plan_id, agent_id=AGENT_ID, profile_result=profile, task=TASK),
            },
        )
        final_state = await engine.get_graph_result(run_id)
        assert final_state is not None
        last_chain = final_state["chain_records"][-1]
        expected_summary = compose_step_chain(_synthesis_material_of(service, plan_id)).final_answer[:200]
        recorder = engine._event_publisher
        agent_decided = [c.args[0] for c in recorder.publish.await_args_list if type(c.args[0]).__name__ == "AgentDecided"]
        assert agent_decided, "SpBlmGraph 路径未发布 AgentDecided"
        payload = agent_decided[0].decision_result
        assert payload["chain_summary"] == expected_summary, (
            f"chain_summary 实测={payload['chain_summary']!r} 期望=末条 final_answer[:200]={expected_summary!r}"
        )
        assert last_chain.chain.final_answer[:200] == expected_summary  # 同源锚（末条即 synthesis）

    async def test_agent_decided_empty_fallback_keeps_first_conclusion(self) -> None:
        """空回退分支（R1-F12——chain_records 空时回退 first_conclusion 现值）。"""
        service, _mocks = _make_service()  # chain 尾参 None → chain_records 空
        engine = _make_engine(service)
        run_id = await engine.submit_graph(
            "SpBlmGraph",
            {"agent_id": str(AGENT_ID), "plan_id": PLAN_ID, "task": TASK, "context": _make_context()},
        )
        final_state = await engine.get_graph_result(run_id)
        assert final_state is not None
        assert final_state.get("chain_records", []) == []
        synthesis = final_state["synthesis"]
        first_conclusion = synthesis.conclusions[0] if synthesis.conclusions else ""
        recorder = engine._event_publisher
        agent_decided = [c.args[0] for c in recorder.publish.await_args_list if type(c.args[0]).__name__ == "AgentDecided"]
        assert agent_decided
        payload = agent_decided[0].decision_result
        assert payload["chain_summary"] == (first_conclusion or "")[:200], (
            "空回退分支漂移（chain_records 空时应回退 first_conclusion 现值——R1-F12）"
        )


def _synthesis_material_of(service: BlmPlanningService, plan_id: str) -> Any:
    """从服务 run_state 提取 synthesis 步组装素材（mock compose 调用面重建——
    投影断言期望构造辅助）。"""

    chain_service = service._chain_archive_service
    assert isinstance(chain_service, AsyncMock)  # 运行时真身校验 + Optional 类型收窄双效（CR1-R1）
    calls = list(chain_service.compose_and_archive_step_chain.await_args_list)
    synthesis_calls = [c for c in calls if c.args[1] == "market_insight_synthesis"]
    assert synthesis_calls, "synthesis 步 compose 调用缺失"
    return synthesis_calls[0].args[2]
