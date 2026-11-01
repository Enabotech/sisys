"""Story 6-1 — BLM 领域模型单元测试（枚举/四 VO/两领域事件）。

TDD 循环 A 载体：枚举序期望【独立构造】自 or.md 六子步骤钦定顺序
（循环自证红线——期望不经被测枚举生成）；VO frozen 不变量；事件
to_dict/from_dict roundtrip 与 DomainEvent._registry 自动注册。

Run with:
    poetry run pytest tests/unit/domain/test_blm_domain_models.py -v
"""

from __future__ import annotations

import uuid
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from typing import Any

import pytest

from src.domain.exceptions.business_exceptions import EntityValidationError
from src.domain.value_objects.blm_phases import (
    BlmPhase,
    BlmPlanningStatus,
    BlmTimelineEntry,
    InsightStepResult,
    InsightSynthesis,
    MarketInsightStep,
    PerformanceGapArtifacts,
)

# ===================================================================
# 枚举：顺序与值域（期望独立构造自 or.md——L385-415 六子步骤钦定序）
# ===================================================================


class TestBlmPhaseEnum:
    """BlmPhase 前两阶段枚举。"""

    def test_two_phases_values(self) -> None:
        """前两阶段枚举值（performance_gap/market_insight——六阶段扩展锚 Epic 10）。"""
        assert BlmPhase.PERFORMANCE_GAP.value == "performance_gap"
        assert BlmPhase.MARKET_INSIGHT.value == "market_insight"
        assert len(BlmPhase) == 2

    def test_phase_order(self) -> None:
        """阶段序：差距分析在前、市场洞察在后（§17.4.1 状态机序）。"""
        assert [p.value for p in BlmPhase] == ["performance_gap", "market_insight"]


class TestMarketInsightStepEnum:
    """MarketInsightStep 六子步骤枚举（OD-2 口径——机会差距分析钉死第六步）。"""

    def test_six_steps_exactly(self) -> None:
        """六值恰好（or.md L385-415 顺序——独立构造期望）。"""
        expected = ["trend", "market_customer", "competition", "self", "opportunity", "opportunity_gap"]
        assert [s.value for s in MarketInsightStep] == expected

    def test_order_independent_of_service(self) -> None:
        """枚举序断言不经被测服务生成（期望字面量独立构造——循环自证红线）。"""
        # 期望值与本测试同源构造，与 MarketInsightStep 实现解耦
        order_from_ormd = ("看趋势", "看市场与客户", "看竞争", "看自己", "看机会", "机会差距分析")
        step_names_zh = {
            "trend": "看趋势",
            "market_customer": "看市场与客户",
            "competition": "看竞争",
            "self": "看自己",
            "opportunity": "看机会",
            "opportunity_gap": "机会差距分析",
        }
        actual_zh = tuple(step_names_zh[s.value] for s in MarketInsightStep)
        assert actual_zh == order_from_ormd


# ===================================================================
# VO：BlmPlanningStatus（流程状态——AC-3 数据面载体）
# ===================================================================


def _make_timeline_entry(step: str = "performance_gap", **overrides: Any) -> BlmTimelineEntry:
    """timeline 条目工厂（默认最小合法形态 + 覆写）。"""
    fields: dict[str, Any] = {
        "step": step,
        "started_at": datetime.now(UTC),
        "completed_at": datetime.now(UTC),
        "status": "completed",
        "summary_excerpt": "步骤摘要",
        "degraded": False,
    }
    fields.update(overrides)
    return BlmTimelineEntry(**fields)


def _make_status(**overrides: Any) -> BlmPlanningStatus:
    """BlmPlanningStatus 工厂（默认最小合法形态 + 覆写）。"""
    fields: dict[str, Any] = {
        "plan_id": str(uuid.uuid4()),
        "phase": BlmPhase.PERFORMANCE_GAP,
        "current_step": "performance_gap",
        "completed_steps": 0,
        "total_steps": 8,
        "degraded_steps": (),
        "timeline": (),
    }
    fields.update(overrides)
    return BlmPlanningStatus(**fields)


class TestBlmPlanningStatus:
    """BlmPlanningStatus VO 不变量。"""

    def test_frozen(self) -> None:
        """frozen dataclass（构造后不可变）。"""
        status = _make_status()
        with pytest.raises(FrozenInstanceError):
            setattr(status, "completed_steps", 3)  # 内建 setattr 触发 frozen __setattr__（静态检查不误报）

    def test_total_steps_pinned_to_eight(self) -> None:
        """total_steps=8 钦定（performance_gap+六子步骤+synthesis）——非 8 拒绝。"""
        with pytest.raises(EntityValidationError):
            _make_status(total_steps=9)

    def test_completed_steps_bounded(self) -> None:
        """completed_steps 不越界（<= total_steps）。"""
        with pytest.raises(EntityValidationError):
            _make_status(completed_steps=9)

    def test_progress_percent_calculation(self) -> None:
        """进度百分比 = completed_steps / total_steps * 100（分母恒 8）。"""
        assert _make_status(completed_steps=0).progress_percent == 0.0
        assert _make_status(completed_steps=4).progress_percent == 50.0
        assert _make_status(completed_steps=8).progress_percent == 100.0

    def test_timeline_entry_structure(self) -> None:
        """timeline 条目结构钦定六字段（step/started_at/completed_at/status/summary_excerpt/degraded）。"""
        entry = _make_timeline_entry()
        assert entry.step == "performance_gap"
        assert entry.status == "completed"
        assert entry.degraded is False
        assert isinstance(entry.started_at, datetime)
        assert isinstance(entry.completed_at, datetime)

    def test_timeline_rejects_foreign_entry(self) -> None:
        """timeline 拒绝非 BlmTimelineEntry 元素（类型守卫）。"""
        with pytest.raises(EntityValidationError):
            _make_status(timeline=({"step": "not-an-entry"},))

    def test_degraded_steps_tuple(self) -> None:
        """degraded_steps 元组形态（AC-6③ 降级清单）。"""
        status = _make_status(degraded_steps=("trend",), completed_steps=8)
        assert status.degraded_steps == ("trend",)

    def test_entry_to_dict_serializable(self) -> None:
        """timeline 条目 to_dict 可 JSON 序列化（快照契约——datetime→isoformat）。"""
        import json

        entry = _make_timeline_entry()
        payload = entry.to_dict()
        serialized = json.dumps(payload)  # 不抛即通过
        assert "started_at" in payload
        assert isinstance(payload["started_at"], str)
        assert json.loads(serialized)["step"] == "performance_gap"


# ===================================================================
# VO：PerformanceGapArtifacts / InsightStepResult / InsightSynthesis
# ===================================================================


class TestPerformanceGapArtifacts:
    """阶段 1 产物 VO（§17.4.2 四字段语义 + 降级标记对称）。"""

    def test_four_fields_present(self) -> None:
        """四字段语义对齐伪码产物定义（financial_gap/operational_gap/root_causes/portfolio_health）。"""
        artifacts = PerformanceGapArtifacts(
            financial_gap="财务差距量化结论",
            operational_gap="运营差距分析结论",
            root_causes=("根因一", "根因二"),
            portfolio_health="业务组合健康度评估",
        )
        assert artifacts.financial_gap
        assert artifacts.operational_gap
        assert artifacts.root_causes == ("根因一", "根因二")
        assert artifacts.portfolio_health

    def test_default_not_degraded(self) -> None:
        """默认不降级（degraded=False + 空原因——降级标记与 InsightStepResult 对称）。"""
        artifacts = PerformanceGapArtifacts(financial_gap="f", operational_gap="o", root_causes=("r",), portfolio_health="p")
        assert artifacts.degraded is False
        assert artifacts.degrade_reason == ""

    def test_frozen(self) -> None:
        """frozen dataclass。"""
        artifacts = PerformanceGapArtifacts(financial_gap="f", operational_gap="o", root_causes=("r",), portfolio_health="p")
        with pytest.raises(FrozenInstanceError):
            setattr(artifacts, "degraded", True)


class TestInsightStepResult:
    """六子步骤通用信封 VO（结构化程度止于信封层——类型化 Schema 归 6-2）。"""

    def test_envelope_fields(self) -> None:
        """信封六字段（step/summary/findings/tool_used/evidence_refs/degraded）。"""
        result = InsightStepResult(
            step="trend",
            summary="宏观趋势要点",
            findings=("发现一",),
            tool_used="pestel-analysis",
            evidence_refs=("doc_1",),
        )
        assert result.step == "trend"
        assert result.degraded is False
        assert result.degrade_reason == ""

    def test_degraded_step_full_envelope(self) -> None:
        """降级步=完整信封（degraded=True+原因+空 summary/findings——恒满 6 元素前提）。"""
        result = InsightStepResult(
            step="trend",
            summary="",
            findings=(),
            tool_used="",
            evidence_refs=(),
            degraded=True,
            degrade_reason="LLM 调用失败（注入）",
        )
        assert result.degraded is True
        assert result.degrade_reason

    def test_frozen(self) -> None:
        """frozen dataclass。"""
        result = InsightStepResult(step="trend", summary="s", findings=(), tool_used="", evidence_refs=())
        with pytest.raises(FrozenInstanceError):
            setattr(result, "summary", "x")


def _make_insight_step(**overrides: Any) -> InsightStepResult:
    """InsightStepResult 工厂（默认最小合法形态 + 覆写——structured_output 扩展组共用）。"""
    fields: dict[str, Any] = {
        "step": "trend",
        "summary": "宏观趋势要点",
        "findings": ("发现一",),
        "tool_used": "pestel-analysis",
        "evidence_refs": ("doc_1",),
    }
    fields.update(overrides)
    return InsightStepResult(**fields)


class TestInsightStepResultStructuredOutput:
    """信封扩展 structured_output（6-2 AC-1/AC-2 承载面——值域守卫白名单两层声明：
    守卫白名单 str/int/float/bool + list[str] 刻意比 Schema 声明白名单
    str/float/list[str] 宽一格——纵深防御：守卫是应用层值域兜底而非生成面约束）。"""

    def test_defaults_to_none_backcompat(self) -> None:
        """默认 None（向后兼容——6-1 既有构造/断言零破坏）。"""
        result = _make_insight_step()
        assert result.structured_output is None

    def test_accepts_flat_scalars_and_str_lists(self) -> None:
        """正常填充：键 str + 值 JSON 标量（str/int/float/bool）与 list[str]。"""
        result = _make_insight_step(
            structured_output={
                "summary": "趋势结论",
                "findings": ["发现一", "发现二"],
                "pestel_political": "政策维度评估",
                "priority_score": 9.5,
                "rank": 2,
                "confirmed": True,
            }
        )
        assert result.structured_output is not None
        assert result.structured_output["summary"] == "趋势结论"
        assert result.structured_output["findings"] == ["发现一", "发现二"]
        assert result.structured_output["priority_score"] == 9.5
        assert result.structured_output["rank"] == 2
        assert result.structured_output["confirmed"] is True

    def test_rejects_non_str_key(self) -> None:
        """键非 str 拒绝（构造器守卫 242）。"""
        with pytest.raises(EntityValidationError):
            _make_insight_step(structured_output={1: "非法键"})

    def test_rejects_nested_dict_value(self) -> None:
        """嵌套 dict 值拒绝（防 pydantic 对象/字典渗入领域层——domain 零依赖红线）。"""
        with pytest.raises(EntityValidationError):
            _make_insight_step(structured_output={"nested": {"inner": "违例"}})

    def test_rejects_list_with_non_str_items(self) -> None:
        """list[dict]/list[int] 等非 str 元素列表拒绝（扁平化强制——OD-5）。"""
        with pytest.raises(EntityValidationError):
            _make_insight_step(structured_output={"matrix": [{"row": "违例"}]})

    def test_rejects_arbitrary_object_value(self) -> None:
        """任意对象值拒绝（pydantic BaseModel 实例同族违例——model_dump 前渗入即拒）。"""

        class _PydanticLike:
            """pydantic 对象替身（属性载体——值域守卫不识别即拒）。"""

            summary = "x"

        with pytest.raises(EntityValidationError):
            _make_insight_step(structured_output={"schema_object": _PydanticLike()})

    def test_rejects_none_value(self) -> None:
        """None 值拒绝（禁 Optional[X]/None 值——model_dump 对 Optional 字段产 None 会炸本守卫）。"""
        with pytest.raises(EntityValidationError):
            _make_insight_step(structured_output={"optional_field": None})

    def test_empty_dict_allowed(self) -> None:
        """空 dict 合法（键域守卫最小形态）。"""
        result = _make_insight_step(structured_output={})
        assert result.structured_output == {}

    def test_degraded_step_envelope_with_none_structured(self) -> None:
        """LLM 失败降级步语义约定：degraded=True + structured_output=None 完整信封
        （None ⟺ LLM 调用/校验失败，由服务层保证——AC-4 收窄口径；VO 层不强制组合校验）。"""
        result = _make_insight_step(summary="", findings=(), degraded=True, degrade_reason="LLM 调用失败（注入）")
        assert result.degraded is True
        assert result.structured_output is None

    def test_hash_raises_typeerror_with_structured_output(self) -> None:
        """携 dict 载荷的信封不可哈希（frozen dataclass hash 含 dict 字段——R1-F8 锚）。

        潜伏性契约变化钉测：默认 None 形态 hash 正常（None 可哈希），携 dict
        载荷形态抛 TypeError——消费面将信封入 set/dict 键前必须先经 to_dict
        形态转换（docstring 契约的行为锚）。
        """
        import pytest

        with_dict = _make_insight_step(structured_output={"summary": "趋势结论"})
        with pytest.raises(TypeError, match="unhashable"):
            hash(with_dict)
        without_dict = _make_insight_step()
        assert isinstance(hash(without_dict), int), "默认 None 形态 hash 正常（None 可哈希）"


class TestInsightSynthesis:
    """综合洞察 VO（AC-6⑥ degraded_inputs 规则载体）。"""

    def test_synthesis_fields(self) -> None:
        """conclusions + degraded_inputs 双字段。"""
        synthesis = InsightSynthesis(conclusions=("结论一", "结论二"), degraded_inputs=())
        assert synthesis.conclusions == ("结论一", "结论二")
        assert synthesis.degraded_inputs == ()

    def test_self_degraded_form(self) -> None:
        """synthesis 自身降级：conclusions=空 + degraded_inputs 自含标记（R3-4 钦定）。"""
        synthesis = InsightSynthesis(conclusions=(), degraded_inputs=("market_insight_synthesis",))
        assert synthesis.conclusions == ()
        assert "market_insight_synthesis" in synthesis.degraded_inputs

    def test_frozen(self) -> None:
        """frozen dataclass。"""
        synthesis = InsightSynthesis(conclusions=("c",), degraded_inputs=())
        with pytest.raises(FrozenInstanceError):
            setattr(synthesis, "conclusions", ("x",))


# ===================================================================
# 领域事件：PlanningStarted / BlmStageCompleted
# ===================================================================


class TestPlanningEvents:
    """planning_events 扩展（保留既有 StrategicDeviationWarning——勿整文件覆盖）。"""

    def test_strategic_deviation_warning_survives(self) -> None:
        """既有事件类仍在（扩展非覆盖）。"""
        from src.domain.events.planning_events import StrategicDeviationWarning

        assert StrategicDeviationWarning is not None

    def test_planning_started_roundtrip(self) -> None:
        """PlanningStarted to_dict/from_dict roundtrip（DomainEvent 既有契约）。"""
        from src.domain.events.planning_events import PlanningStarted

        event = PlanningStarted(
            plan_id=str(uuid.uuid4()),
            agent_id=uuid.uuid4(),
            tenant_id="tenant-1",
        )
        restored = PlanningStarted.from_dict(event.to_dict())
        assert isinstance(restored, PlanningStarted), "roundtrip 应还原为子类实例（类型收窄+判别力）"
        assert restored.plan_id == event.plan_id
        assert restored.agent_id == event.agent_id
        assert restored.event_type == "PlanningStarted"

    def test_blm_stage_completed_roundtrip(self) -> None:
        """BlmStageCompleted roundtrip + stage 字段保留。"""
        from src.domain.events.planning_events import BlmStageCompleted

        event = BlmStageCompleted(
            plan_id=str(uuid.uuid4()),
            agent_id=uuid.uuid4(),
            stage="market_insight_trend",
            summary_excerpt="看趋势完成",
        )
        restored = BlmStageCompleted.from_dict(event.to_dict())
        assert isinstance(restored, BlmStageCompleted), "roundtrip 应还原为子类实例（类型收窄+判别力）"
        assert restored.stage == "market_insight_trend"
        assert restored.summary_excerpt == "看趋势完成"

    def test_auto_registration_in_registry(self) -> None:
        """event_type 字段声明经 __init_subclass__ 自动注册进 DomainEvent._registry。"""
        from src.domain.events.base import DomainEvent
        from src.domain.events.planning_events import BlmStageCompleted, PlanningStarted

        assert DomainEvent._registry.get("PlanningStarted") is PlanningStarted
        assert DomainEvent._registry.get("BlmStageCompleted") is BlmStageCompleted

    @pytest.mark.parametrize(
        "stage",
        [
            "performance_gap",
            "market_insight_trend",
            "market_insight_market_customer",
            "market_insight_competition",
            "market_insight_self",
            "market_insight_opportunity",
            "market_insight_opportunity_gap",
            "market_insight_synthesis",
        ],
    )
    def test_stage_valid_domain(self, stage: str) -> None:
        """stage 合法域：8 值全集（performance_gap+六子步骤+synthesis）。"""
        from src.domain.events.planning_events import BlmStageCompleted

        event = BlmStageCompleted(plan_id=str(uuid.uuid4()), agent_id=uuid.uuid4(), stage=stage)
        assert event.stage == stage

    def test_stage_invalid_value_rejected(self) -> None:
        """stage 越域值拒绝（枚举域守卫——防自由字符串漂移）。"""
        from src.domain.events.planning_events import BlmStageCompleted

        with pytest.raises(EntityValidationError):
            BlmStageCompleted(plan_id=str(uuid.uuid4()), agent_id=uuid.uuid4(), stage="market_insight_看风险")

    def test_summary_excerpt_truncated_to_200(self) -> None:
        """summary_excerpt ≤200 截断（fix_attempts violations_excerpt 先例）。"""
        from src.domain.events.planning_events import BlmStageCompleted

        event = BlmStageCompleted(
            plan_id=str(uuid.uuid4()),
            agent_id=uuid.uuid4(),
            stage="performance_gap",
            summary_excerpt="长" * 500,
        )
        assert len(event.summary_excerpt) <= 200

    def test_events_exported_from_package(self) -> None:
        """events/__init__.py 导出更新（两新事件可从包级导入）。"""
        import src.domain.events as events_package

        assert events_package.BlmStageCompleted.__name__ == "BlmStageCompleted"
        assert events_package.PlanningStarted.__name__ == "PlanningStarted"

    def test_domain_zero_third_party(self) -> None:
        """domain 层零第三方依赖（dataclass + 标准库——六边形红线抽样）。"""
        import ast
        from pathlib import Path

        module_path = Path("src/domain/value_objects/blm_phases.py")
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] in {"dataclasses", "datetime", "enum", "typing", "uuid", "__future__"}, (
                        f"blm_phases 引入非标准库: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                assert node.module.split(".")[0] in {
                    "dataclasses",
                    "datetime",
                    "enum",
                    "typing",
                    "uuid",
                    "__future__",
                    "src",
                }, f"blm_phases 引入非标准库: {node.module}"


def test_event_datetime_aware() -> None:
    """事件默认时间戳 timezone-aware（UTC）。"""
    from src.domain.events.planning_events import PlanningStarted

    event = PlanningStarted(plan_id=str(uuid.uuid4()), agent_id=uuid.uuid4())
    assert event.started_at.tzinfo is not None
