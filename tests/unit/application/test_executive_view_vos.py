"""Story 6-8 - 高管简化视图六 VO + ExecutiveHealth 枚举单元测试.

覆盖面（Task 0.1 冻结表逐键对齐）：
    - 六 VO 键集 exact set（ExecutiveView 8 / PlanningSection 8 / ApprovalSection 10 /
      AuditSection 7（无 available 键——OD-4）/ ReportSection 8 / AuditEventSummary 4）；
    - 构造守卫 242 三形态（空 plan_id 拒 / 裸 str health 拒 / 四段负计数拒——EntityValidationError）；
    - ExecutiveHealth 枚举成员与值域（全仓首个三值分级枚举——green/amber/red）。

Run with:
    poetry run pytest tests/unit/application/test_executive_view_vos.py -v
"""

from __future__ import annotations

from dataclasses import fields
from typing import Any

import pytest

from src.application.ports.executive_view import (
    ApprovalSection,
    AuditEventSummary,
    AuditSection,
    ExecutiveHealth,
    ExecutiveView,
    PlanningSection,
    ReportSection,
)
from src.domain.exceptions import EntityValidationError

# ===================================================================
# 构造工厂（合法形态基准——守卫断言的对照腿）
# ===================================================================


def _make_planning(**overrides: Any) -> PlanningSection:
    """合法 PlanningSection 构造工厂（预置覆盖参数供守卫负例）."""
    payload: dict[str, Any] = {
        "available": True,
        "degraded": False,
        "completed_steps": 3,
        "total_steps": 8,
        "progress_percent": 37,
        "current_step": "market_insight_competition",
        "degraded_step_count": 1,
        "last_activity_at": "2026-11-06T10:00:00+00:00",
    }
    payload.update(overrides)
    return PlanningSection(**payload)


def _make_approval(**overrides: Any) -> ApprovalSection:
    """合法 ApprovalSection 构造工厂."""
    payload: dict[str, Any] = {
        "available": True,
        "degraded": False,
        "total_checkpoints": 3,
        "completed_count": 2,
        "in_sync_count": 3,
        "pending_sync_count": 0,
        "invalidated_count": 0,
        "last_recovery_mode": "replay",
        "last_recovery_confirmed_by": "ceo-acceptance",
        "last_recovered_at": "2026-11-06T10:00:00+00:00",
    }
    payload.update(overrides)
    return ApprovalSection(**payload)


def _make_audit(**overrides: Any) -> AuditSection:
    """合法 AuditSection 构造工厂（recent_events 恒元组——frozen 纪律）."""
    payload: dict[str, Any] = {
        "degraded": False,
        "window_days": 7,
        "window_start": "2026-10-30T10:00:00+00:00",
        "window_end": "2026-11-06T10:00:00+00:00",
        "total_events": 5,
        "recent_events": (
            AuditEventSummary(
                action_type="exec-view:probe",
                actor="exec-view-actor",
                target_resource="exec-view-target",
                timestamp="2026-11-06T09:59:59+00:00",
            ),
        ),
        "last_event_at": "2026-11-06T09:59:59+00:00",
    }
    payload.update(overrides)
    return AuditSection(**payload)


def _make_report(**overrides: Any) -> ReportSection:
    """合法 ReportSection 构造工厂."""
    payload: dict[str, Any] = {
        "available": True,
        "degraded": False,
        "report_id": "0f0e0d0c-0b0a-0908-0706-050403020100",
        "report_type": "markdown",
        "file_path": "/tmp/sisys-reports/plan.md",
        "section_count": 11,
        "degraded_section_count": 2,
        "generated_at": "2026-11-06T10:00:00+00:00",
    }
    payload.update(overrides)
    return ReportSection(**payload)


def _make_view(**overrides: Any) -> ExecutiveView:
    """合法 ExecutiveView 构造工厂（默认 GREEN 全健康形态）."""
    payload: dict[str, Any] = {
        "plan_id": "123e4567-e89b-12d3-a456-426614174000",
        "generated_at": "2026-11-06T10:00:00+00:00",
        "health": ExecutiveHealth.GREEN,
        "build_degraded": False,
        "planning": _make_planning(),
        "approval": _make_approval(),
        "audit": _make_audit(),
        "report": _make_report(),
    }
    payload.update(overrides)
    return ExecutiveView(**payload)


# ===================================================================
# ExecutiveHealth 枚举（全仓首个三值分级枚举——OD-4）
# ===================================================================


class TestExecutiveHealthEnum:
    """ExecutiveHealth 三值 str-Enum 值域断言."""

    def test_three_members(self) -> None:
        """枚举恰三成员（green/amber/red——值对齐 UX v2.1 三色语义）."""
        assert {member.name for member in ExecutiveHealth} == {"GREEN", "AMBER", "RED"}

    def test_member_values(self) -> None:
        """成员值小写三色（amber 不用 yellow——UX v2.1 英文用词单源）."""
        assert ExecutiveHealth.GREEN.value == "green"
        assert ExecutiveHealth.AMBER.value == "amber"
        assert ExecutiveHealth.RED.value == "red"

    def test_is_str_enum(self) -> None:
        """str-Enum 形态（isinstance str 成立——CLI 打印零转换）."""
        assert isinstance(ExecutiveHealth.GREEN, str)


# ===================================================================
# 六 VO 键集 exact set（Task 0.1 冻结表——实现禁增删键）
# ===================================================================


class TestVOKeyContracts:
    """六 VO 键集 exact set 断言（6-6 R1-F10 激活先例形态）."""

    def test_executive_view_eight_keys(self) -> None:
        """ExecutiveView 8 键（含 build_degraded 顶层哨兵与 generated_at 视图锚）."""
        view = _make_view()
        assert {f.name for f in fields(view)} == {
            "plan_id",
            "generated_at",
            "health",
            "build_degraded",
            "planning",
            "approval",
            "audit",
            "report",
        }

    def test_planning_section_eight_keys(self) -> None:
        """PlanningSection 8 键（degraded_step_count 派生计数+last_activity_at timeline 派生）."""
        assert {f.name for f in fields(_make_planning())} == {
            "available",
            "degraded",
            "completed_steps",
            "total_steps",
            "progress_percent",
            "current_step",
            "degraded_step_count",
            "last_activity_at",
        }

    def test_approval_section_ten_keys(self) -> None:
        """ApprovalSection 10 键（sync 三态分布+恢复留痕三键）."""
        assert {f.name for f in fields(_make_approval())} == {
            "available",
            "degraded",
            "total_checkpoints",
            "completed_count",
            "in_sync_count",
            "pending_sync_count",
            "invalidated_count",
            "last_recovery_mode",
            "last_recovery_confirmed_by",
            "last_recovered_at",
        }

    def test_audit_section_seven_keys_no_available(self) -> None:
        """AuditSection 7 键且无 available（窗口零事件是合法空态非不可得——OD-4）."""
        assert {f.name for f in fields(_make_audit())} == {
            "degraded",
            "window_days",
            "window_start",
            "window_end",
            "total_events",
            "recent_events",
            "last_event_at",
        }

    def test_report_section_eight_keys(self) -> None:
        """ReportSection 8 键（generated_at=created_at.isoformat() 派生映射——R1-F4）."""
        assert {f.name for f in fields(_make_report())} == {
            "available",
            "degraded",
            "report_id",
            "report_type",
            "file_path",
            "section_count",
            "degraded_section_count",
            "generated_at",
        }

    def test_audit_event_summary_four_keys(self) -> None:
        """AuditEventSummary 4 键（投影白名单——审计行 15 键禁入高管视图）."""
        assert {f.name for f in fields(AuditEventSummary(action_type="a", actor="b", target_resource="c", timestamp="d"))} == {
            "action_type",
            "actor",
            "target_resource",
            "timestamp",
        }

    def test_frozen_dataclasses(self) -> None:
        """六 VO 全 frozen（可变性拒绝——读侧 DTO 不可变纪律）."""
        from dataclasses import FrozenInstanceError

        view: Any = _make_view()
        with pytest.raises(FrozenInstanceError):
            view.build_degraded = True

    def test_recent_events_tuple_type(self) -> None:
        """recent_events 恒元组形态（frozen 纪律——list 输入归一化）."""
        audit = _make_audit(recent_events=[])
        assert isinstance(audit.recent_events, tuple)


# ===================================================================
# 构造守卫 242（EntityValidationError——三形态+四段负计数全枚举）
# ===================================================================


class TestConstructionGuards:
    """构造守卫断言（242 复用——实体不变量场景钦定；R1-F28 四段计数逐段枚举）."""

    def test_empty_plan_id_rejected(self) -> None:
        """空 plan_id 拒（242）."""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_view(plan_id="")
        assert exc_info.value.code == "EXCEPTION_242"

    def test_bare_str_health_rejected(self) -> None:
        """裸 str health 拒（枚举成员校验——ArchiveType validate 同款形态）."""
        bare_health: Any = "green"
        with pytest.raises(EntityValidationError) as exc_info:
            _make_view(health=bare_health)
        assert exc_info.value.code == "EXCEPTION_242"

    def test_planning_negative_count_rejected(self) -> None:
        """planning 段负计数拒（completed/total/degraded_step_count 三计数）."""
        for field_name in ("completed_steps", "total_steps", "degraded_step_count"):
            with pytest.raises(EntityValidationError):
                _make_planning(**{field_name: -1})

    def test_approval_negative_count_rejected(self) -> None:
        """approval 段负计数拒（total+三态四计数）."""
        for field_name in ("total_checkpoints", "completed_count", "in_sync_count", "pending_sync_count", "invalidated_count"):
            with pytest.raises(EntityValidationError):
                _make_approval(**{field_name: -1})

    def test_report_negative_count_rejected(self) -> None:
        """report 段负计数拒（section 双计数）."""
        for field_name in ("section_count", "degraded_section_count"):
            with pytest.raises(EntityValidationError):
                _make_report(**{field_name: -1})

    def test_audit_negative_total_rejected(self) -> None:
        """audit 段 total_events 负值拒（R1 订正：四段计数含 audit）."""
        with pytest.raises(EntityValidationError):
            _make_audit(total_events=-1)

    def test_zero_counts_accepted(self) -> None:
        """零计数合法（空态键恒在降级值——零数据 plan 合法形态）."""
        planning = _make_planning(
            completed_steps=0,
            progress_percent=0,
            degraded_step_count=0,
            current_step=None,
            last_activity_at=None,
        )
        assert planning.completed_steps == 0
        approval = _make_approval(
            total_checkpoints=0,
            completed_count=0,
            in_sync_count=0,
            last_recovery_mode=None,
            last_recovery_confirmed_by=None,
            last_recovered_at=None,
        )
        assert approval.total_checkpoints == 0
        report = _make_report(
            available=False,
            report_id=None,
            report_type=None,
            file_path=None,
            section_count=0,
            degraded_section_count=0,
            generated_at=None,
        )
        assert report.section_count == 0
