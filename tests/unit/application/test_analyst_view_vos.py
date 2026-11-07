"""Story 6-9 - 分析师视图七 VO + PhaseStatus 枚举单元测试（键契约+静态清单+构造守卫）.

覆盖面：
    - PhaseStatus 三值 str-Enum（成员/值/isinstance str——6-8 ExecutiveHealth 同族形态）；
    - BLM_SIX_PHASES 六元组逐对全量精确匹配（phase_key+phase_name 中文逐字——R3-F3：
      匹配单位是键值对非仅序；序 or.md L379 权威）；
    - 七 VO 键集 exact set（6/4/5/2/9/5/8——Task 0.1 冻结表逐键对齐，6-8 R1-F10 形态）；
    - 构造守卫 242 三形态（plan_id 非空/枚举成员校验裸 str 拒绝/计数 ≥0）+
      step_completed ≤ step_total 进度不变量；
    - frozen dataclass 纪律（拒可变）。

Run with:
    poetry run pytest tests/unit/application/test_analyst_view_vos.py -v
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from typing import Any

import pytest

from src.application.ports.analyst_view import (
    BLM_SIX_PHASES,
    AnalystView,
    AnalystViewPort,
    PhaseProgress,
    PhaseStatus,
    ProgressSection,
    ToolboxSection,
    ToolCategorySummary,
    ToolSummary,
    TraceabilitySection,
)
from src.domain.exceptions import EntityValidationError

# ===================================================================
# 构造工厂（预置覆盖参数供守卫负例——6-8 **overrides 形态）
# ===================================================================


def _make_tool_summary(**overrides: Any) -> ToolSummary:
    """合法 ToolSummary 构造工厂（投影白名单五键——L1 元数据直传形态）."""
    payload: dict[str, Any] = {
        "slug": "pestel-analysis",
        "tool_name": "PESTEL 分析",
        "category": "environment_analysis",
        "description": "宏观环境分析工具",
        "status": "active",
    }
    payload.update(overrides)
    return ToolSummary(**payload)


def _make_category(**overrides: Any) -> ToolCategorySummary:
    """合法 ToolCategorySummary 构造工厂."""
    payload: dict[str, Any] = {"category": "environment_analysis", "tool_count": 3}
    payload.update(overrides)
    return ToolCategorySummary(**payload)


def _make_stage(**overrides: Any) -> PhaseProgress:
    """合法 PhaseProgress 构造工厂."""
    payload: dict[str, Any] = {
        "phase_key": "performance_gap",
        "phase_name": "业绩差距分析",
        "status": PhaseStatus.COMPLETED,
        "step_completed": 1,
        "step_total": 1,
    }
    payload.update(overrides)
    return PhaseProgress(**payload)


def _make_toolbox(**overrides: Any) -> ToolboxSection:
    """合法 ToolboxSection 构造工厂."""
    payload: dict[str, Any] = {
        "degraded": False,
        "total_tools": 1,
        "tools": (_make_tool_summary(),),
        "categories": (_make_category(),),
    }
    payload.update(overrides)
    return ToolboxSection(**payload)


def _make_progress(**overrides: Any) -> ProgressSection:
    """合法 ProgressSection 构造工厂."""
    payload: dict[str, Any] = {
        "available": True,
        "degraded": False,
        "phase": "market_insight",
        "current_step": "trend",
        "completed_steps": 3,
        "total_steps": 8,
        "progress_percent": 37,
        "degraded_step_count": 1,
        "stages": (_make_stage(),),
    }
    payload.update(overrides)
    return ProgressSection(**payload)


def _make_traceability(**overrides: Any) -> TraceabilitySection:
    """合法 TraceabilitySection 构造工厂."""
    payload: dict[str, Any] = {
        "available": True,
        "degraded": False,
        "stage_count": 2,
        "chunk_count": 3,
        "document_count": 3,
        "jump_ready_count": 2,
        "degraded_stage_count": 0,
        "tree_build_degraded": False,
    }
    payload.update(overrides)
    return TraceabilitySection(**payload)


def _make_view(**overrides: Any) -> AnalystView:
    """合法 AnalystView 构造工厂."""
    payload: dict[str, Any] = {
        "plan_id": "123e4567-e89b-12d3-a456-426614174000",
        "generated_at": "2026-11-07T10:00:00+00:00",
        "build_degraded": False,
        "toolbox": _make_toolbox(),
        "progress": _make_progress(),
        "traceability": _make_traceability(),
    }
    payload.update(overrides)
    return AnalystView(**payload)


# ===================================================================
# PhaseStatus 三值枚举
# ===================================================================


class TestPhaseStatusEnum:
    """PhaseStatus 三值 str-Enum（进度态语义域——与 ExecutiveHealth 健康分级域正交）."""

    def test_three_members_exact(self) -> None:
        """三成员精确集合（completed/in_progress/not_started）."""
        assert {member.name for member in PhaseStatus} == {"COMPLETED", "IN_PROGRESS", "NOT_STARTED"}

    def test_member_values_lowercase(self) -> None:
        """成员值小写字符串."""
        assert PhaseStatus.COMPLETED.value == "completed"
        assert PhaseStatus.IN_PROGRESS.value == "in_progress"
        assert PhaseStatus.NOT_STARTED.value == "not_started"

    def test_str_enum_isinstance(self) -> None:
        """str-Enum（isinstance str——6-6 S8 教训：双形态判别防线）."""
        assert isinstance(PhaseStatus.COMPLETED, str)
        assert PhaseStatus.IN_PROGRESS == "in_progress"


# ===================================================================
# BLM_SIX_PHASES 六阶段静态清单（R3-F3：逐对全量精确匹配——键值对非仅序）
# ===================================================================


class TestSixPhasesConstant:
    """BLM_SIX_PHASES 六元组（阶段序 or.md L379 权威——逐对全量精确匹配）."""

    def test_six_pairs_exact_match(self) -> None:
        """六 (phase_key, phase_name) 对逐对全量精确匹配（中文全名逐字）."""
        assert BLM_SIX_PHASES == (
            ("performance_gap", "业绩差距分析"),
            ("market_insight", "市场洞察"),
            ("strategic_intent", "战略意图与目标"),
            ("innovation_focus", "创新焦点"),
            ("business_design", "业务设计"),
            ("execution_design", "执行设计"),
        )

    def test_six_pairs_length_and_types(self) -> None:
        """六元组长度与元素形态（tuple[tuple[str, str], ...]）."""
        assert len(BLM_SIX_PHASES) == 6
        for phase_key, phase_name in BLM_SIX_PHASES:
            assert isinstance(phase_key, str) and phase_key
            assert isinstance(phase_name, str) and phase_name


# ===================================================================
# 七 VO 键集 exact set（Task 0.1 冻结表逐键对齐）
# ===================================================================


class TestVOKeyContracts:
    """七 VO 键集 exact set 断言（6-6 R1-F10 激活先例形态）."""

    def test_analyst_view_six_keys(self) -> None:
        """AnalystView 6 键（含 build_degraded 顶层哨兵与 generated_at 视图锚）."""
        view = _make_view()
        assert {f.name for f in fields(view)} == {
            "plan_id",
            "generated_at",
            "build_degraded",
            "toolbox",
            "progress",
            "traceability",
        }

    def test_toolbox_section_four_keys(self) -> None:
        """ToolboxSection 4 键（degraded/total_tools/tools/categories）."""
        assert {f.name for f in fields(_make_toolbox())} == {
            "degraded",
            "total_tools",
            "tools",
            "categories",
        }

    def test_tool_summary_five_keys(self) -> None:
        """ToolSummary 5 键（投影白名单——slug/tool_name/category/description/status）."""
        assert {f.name for f in fields(_make_tool_summary())} == {
            "slug",
            "tool_name",
            "category",
            "description",
            "status",
        }

    def test_tool_category_summary_two_keys(self) -> None:
        """ToolCategorySummary 2 键（category/tool_count）."""
        assert {f.name for f in fields(_make_category())} == {"category", "tool_count"}

    def test_progress_section_nine_keys(self) -> None:
        """ProgressSection 9 键（步级计数直读+stages 六阶段全景）."""
        assert {f.name for f in fields(_make_progress())} == {
            "available",
            "degraded",
            "phase",
            "current_step",
            "completed_steps",
            "total_steps",
            "progress_percent",
            "degraded_step_count",
            "stages",
        }

    def test_phase_progress_five_keys(self) -> None:
        """PhaseProgress 5 键（phase_key/phase_name/status/step_completed/step_total）."""
        assert {f.name for f in fields(_make_stage())} == {
            "phase_key",
            "phase_name",
            "status",
            "step_completed",
            "step_total",
        }

    def test_traceability_section_eight_keys(self) -> None:
        """TraceabilitySection 8 键（两层哨兵分立+五计数——结论层恒单根节点不计入）."""
        assert {f.name for f in fields(_make_traceability())} == {
            "available",
            "degraded",
            "stage_count",
            "chunk_count",
            "document_count",
            "jump_ready_count",
            "degraded_stage_count",
            "tree_build_degraded",
        }

    def test_progress_section_default_six_stage_framework(self) -> None:
        """ProgressSection 默认值=空态形态（R3-F2 钦定：计数全 0+六阶段 not_started 框架恒在）."""
        progress = ProgressSection()
        assert progress.available is False
        assert progress.phase is None
        assert progress.current_step is None
        assert progress.completed_steps == 0
        assert progress.total_steps == 0  # 空态 0 非 8——总数语义由 stages 框架承载（与 6-8 分立注记）
        assert progress.progress_percent == 0
        assert progress.degraded_step_count == 0
        assert len(progress.stages) == 6
        assert all(stage.status is PhaseStatus.NOT_STARTED for stage in progress.stages)
        assert [stage.phase_key for stage in progress.stages] == [pair[0] for pair in BLM_SIX_PHASES]
        # 步数规划值框架恒在（1/7/0/0/0/0——数据缺席仅影响 status/step_completed）
        assert [stage.step_total for stage in progress.stages] == [1, 7, 0, 0, 0, 0]

    def test_toolbox_and_traceability_defaults(self) -> None:
        """ToolboxSection/TraceabilitySection 默认值（空态键恒在纪律——None/0/() 降级值）."""
        toolbox = ToolboxSection()
        assert toolbox.degraded is False
        assert toolbox.total_tools == 0
        assert toolbox.tools == ()
        assert toolbox.categories == ()
        traceability = TraceabilitySection()
        assert traceability.available is False
        assert traceability.degraded is False
        assert traceability.stage_count == 0
        assert traceability.tree_build_degraded is False


# ===================================================================
# 构造守卫（242 复用——三形态：plan_id 非空/枚举裸 str 拒绝/计数 ≥0）
# ===================================================================


class TestConstructionGuards:
    """构造守卫断言（242 复用——实体不变量场景钦定）."""

    def test_empty_plan_id_rejected(self) -> None:
        """空 plan_id 拒（242）."""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_view(plan_id="")
        assert exc_info.value.code == "EXCEPTION_242"

    def test_non_string_plan_id_rejected(self) -> None:
        """非 str plan_id 拒（242）."""
        with pytest.raises(EntityValidationError):
            _make_view(plan_id=12345)

    def test_bare_str_status_rejected(self) -> None:
        """裸 str status 拒（枚举成员校验——PhaseProgress 守卫）."""
        bare_status: Any = "completed"
        with pytest.raises(EntityValidationError) as exc_info:
            _make_stage(status=bare_status)
        assert exc_info.value.code == "EXCEPTION_242"

    def test_toolbox_negative_count_rejected(self) -> None:
        """toolbox 段负计数拒（total_tools）."""
        with pytest.raises(EntityValidationError):
            _make_toolbox(total_tools=-1)

    def test_category_negative_count_rejected(self) -> None:
        """category 负计数拒（tool_count）."""
        with pytest.raises(EntityValidationError):
            _make_category(tool_count=-1)

    def test_progress_negative_counts_rejected(self) -> None:
        """progress 段负计数拒（三计数逐项枚举）."""
        for field_name in ("completed_steps", "total_steps", "degraded_step_count"):
            with pytest.raises(EntityValidationError):
                _make_progress(**{field_name: -1})

    def test_stage_negative_counts_rejected(self) -> None:
        """stage 负计数拒（step_completed/step_total）."""
        for field_name in ("step_completed", "step_total"):
            with pytest.raises(EntityValidationError):
                _make_stage(**{field_name: -1})

    def test_stage_completed_exceeds_total_rejected(self) -> None:
        """step_completed > step_total 拒（进度不变量——后四阶段 0≤0 恒真）."""
        with pytest.raises(EntityValidationError):
            _make_stage(step_completed=3, step_total=1)

    def test_traceability_negative_counts_rejected(self) -> None:
        """traceability 段负计数拒（五计数逐项枚举）."""
        for field_name in ("stage_count", "chunk_count", "document_count", "jump_ready_count", "degraded_stage_count"):
            with pytest.raises(EntityValidationError):
                _make_traceability(**{field_name: -1})

    def test_zero_counts_accepted(self) -> None:
        """零值合法对照腿（空态全 0 形态可构造）."""
        assert _make_toolbox(total_tools=0, tools=(), categories=()).total_tools == 0
        assert _make_traceability(stage_count=0, chunk_count=0, document_count=0, jump_ready_count=0).available is True
        assert _make_stage(step_completed=0, step_total=0).status is PhaseStatus.COMPLETED


# ===================================================================
# frozen dataclass 纪律
# ===================================================================


class TestDataclassDiscipline:
    """frozen dataclass 纪律（七 VO 全 frozen——拒可变）."""

    def test_all_vos_frozen(self) -> None:
        """七 VO 拒原地突变（FrozenInstanceError——setattr 动态形态，frozen 属性直赋值 mypy 视为 read-only 写入）."""
        with pytest.raises(FrozenInstanceError):
            setattr(_make_view(), "plan_id", "mutated")
        with pytest.raises(FrozenInstanceError):
            setattr(_make_progress(), "completed_steps", 5)
        with pytest.raises(FrozenInstanceError):
            setattr(_make_tool_summary(), "slug", "mutated")

    def test_port_runtime_checkable(self) -> None:
        """AnalystViewPort runtime_checkable Protocol（应用层端口在册形态）."""
        assert hasattr(AnalystViewPort, "build_analyst_view")
