"""Story 4.7: EvolutionLogEntry 聚合根 + FixAttempt 值对象单元测试.

覆盖构造不变量（UUID/签名 64 hex/enhanced_retry_count ∈ [1,3]/trigger_code 枚举/
final_status 终态语义/fix_attempts 元组）、FixAttempt 边界形态
（llm_generation_failed 空串合法形态 + suggested_fix_excerpt 截断 ≤2000——R8-1）、
非法构造抛 EntityValidationError(242)。

TDD 红→绿：本文件先于 entities/evolution_log_entry.py 与
value_objects/validation_feedback.py 实现（Subtask 1.1）。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from src.domain.entities.evolution_log_entry import EvolutionLogEntry
from src.domain.exceptions import EntityValidationError
from src.domain.value_objects.validation_feedback import (
    FeedbackOutcome,
    FixAttempt,
    FixStrategy,
    TriggerCode,
)

_SIG_64 = "b" * 64


def _make_attempt(**overrides: object) -> FixAttempt:
    """构造合法 FixAttempt 基准实例（retry_failed 形态）."""
    kwargs: dict = {
        "attempt_no": 1,
        "attempt_execution_id": str(uuid.uuid4()),
        "error_signature": _SIG_64,
        "fix_strategy": FixStrategy.PURE_LLM,
        "stderr_excerpt": "Traceback ... ValueError: bad",
        "suggested_fix_excerpt": "方案A：将 result 前缀改为 OK_",
        "succeeded": False,
        "detail": "retry_failed",
    }
    kwargs.update(overrides)
    return FixAttempt(**kwargs)


def _make_entry(**overrides: object) -> EvolutionLogEntry:
    """构造合法 EvolutionLogEntry 基准实例（耗尽形态）."""
    kwargs: dict = {
        "log_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "tool_id": uuid.uuid4(),
        "execution_id": uuid.uuid4(),
        "tool_version": "1.0.0",
        "trigger_code": TriggerCode.EXCEPTION_389,
        "error_signature": _SIG_64,
        "enhanced_retry_count": 3,
        "fix_attempts": (_make_attempt(attempt_no=1), _make_attempt(attempt_no=2), _make_attempt(attempt_no=3)),
        "duration_sec": 12.5,
        "final_status": FeedbackOutcome.MARKED_INFEASIBLE,
        "created_at": datetime.now(UTC),
    }
    kwargs.update(overrides)
    return EvolutionLogEntry(**kwargs)


class TestFixAttemptValueObject:
    """FixAttempt 值对象."""

    def test_valid_construction(self) -> None:
        """基准形态构造成功."""
        attempt = _make_attempt()
        assert attempt.attempt_no == 1
        assert attempt.fix_strategy == FixStrategy.PURE_LLM

    def test_llm_generation_failed_boundary_form_is_legal(self) -> None:
        """边界形态：无重执行的 fix-gen 失败（attempt_execution_id/stderr/方案摘要全空串合法——R2-9）."""
        attempt = _make_attempt(
            attempt_execution_id="",
            stderr_excerpt="",
            suggested_fix_excerpt="",
            detail="llm_generation_failed",
        )
        assert attempt.attempt_execution_id == ""
        assert attempt.detail == "llm_generation_failed"

    def test_is_frozen(self) -> None:
        """frozen 值对象（不可变）——setattr 运行时验证（静态直赋对 frozen 属性非法）."""
        attempt = _make_attempt()
        with pytest.raises(AttributeError):
            setattr(attempt, "detail", "changed")

    def test_attempt_no_must_be_positive(self) -> None:
        """attempt_no 1-based."""
        with pytest.raises(EntityValidationError):
            _make_attempt(attempt_no=0)

    def test_signature_non_hex_raises(self) -> None:
        """签名必须为 hex 字符（R2：拒绝向用例——守卫判别力）."""
        with pytest.raises(EntityValidationError):
            _make_attempt(error_signature="x" * 64)

    def test_signature_0x_prefix_raises(self) -> None:
        """「0x」前缀 64 串不是合法 hexdigest（R2 收紧：int(,16) 曾宽容此形态）."""
        with pytest.raises(EntityValidationError):
            _make_attempt(error_signature="0x" + "a" * 62)

    def test_suggested_fix_excerpt_truncated_to_2000(self) -> None:
        """suggested_fix_excerpt 截断 ≤2000（R8-1 动作半边载荷边界）."""
        attempt = _make_attempt(suggested_fix_excerpt="z" * 3000)
        assert len(attempt.suggested_fix_excerpt) <= 2000

    def test_stderr_excerpt_truncated_to_2000(self) -> None:
        """stderr_excerpt 截断 ≤2000."""
        attempt = _make_attempt(stderr_excerpt="x" * 3000)
        assert len(attempt.stderr_excerpt) <= 2000

    def test_attempt_execution_id_invalid_uuid_raises(self) -> None:
        """attempt_execution_id 非空时必须为合法 UUID 字符串（空串=未重执行合法形态）."""
        with pytest.raises(EntityValidationError):
            _make_attempt(attempt_execution_id="not-an-uuid")

    def test_fix_strategy_enum_members(self) -> None:
        """三分支枚举（决策 #15）：CASE_GUIDED / NEGATIVE_CASE_GUIDED / PURE_LLM."""
        assert {s.value for s in FixStrategy} == {"CASE_GUIDED", "NEGATIVE_CASE_GUIDED", "PURE_LLM"}


class TestEvolutionLogEntryConstruction:
    """合法构造."""

    def test_valid_construction(self) -> None:
        """基准形态（3 attempt 耗尽）构造成功."""
        entry = _make_entry()
        assert entry.final_status == FeedbackOutcome.MARKED_INFEASIBLE
        assert entry.enhanced_retry_count == 3
        assert len(entry.fix_attempts) == 3

    def test_recovered_form(self) -> None:
        """恢复形态（attempt 2 成功——1 条失败 + 1 条成功）。"""
        entry = _make_entry(
            enhanced_retry_count=2,
            fix_attempts=(_make_attempt(attempt_no=1), _make_attempt(attempt_no=2, succeeded=True, detail="ok")),
            final_status=FeedbackOutcome.RECOVERED,
            duration_sec=5.0,
        )
        assert entry.final_status == FeedbackOutcome.RECOVERED


class TestEvolutionLogEntryInvariants:
    """构造不变量（非法构造抛 242）."""

    def test_invalid_signature_raises(self) -> None:
        """签名 64 hex."""
        with pytest.raises(EntityValidationError):
            _make_entry(error_signature="b" * 63)

    def test_invalid_signature_non_hex_raises(self) -> None:
        """签名必须为 hex 字符（R2：拒绝向用例——守卫判别力）."""
        with pytest.raises(EntityValidationError):
            _make_entry(error_signature="x" * 64)

    def test_invalid_signature_0x_prefix_raises(self) -> None:
        """「0x」前缀 64 串不是合法 hexdigest（R2 收紧：int(,16) 曾宽容此形态）."""
        with pytest.raises(EntityValidationError):
            _make_entry(error_signature="0x" + "a" * 62)

    def test_enhanced_retry_count_below_1_raises(self) -> None:
        """enhanced_retry_count ∈ [1,3]——下界."""
        with pytest.raises(EntityValidationError):
            _make_entry(enhanced_retry_count=0)

    def test_enhanced_retry_count_above_3_raises(self) -> None:
        """enhanced_retry_count ∈ [1,3]——上界."""
        with pytest.raises(EntityValidationError):
            _make_entry(enhanced_retry_count=4)

    def test_invalid_trigger_code_raises(self) -> None:
        """trigger_code 限 389/382（失败模式第一维分类）。"""
        with pytest.raises(EntityValidationError):
            _make_entry(trigger_code="EXCEPTION_385")

    def test_invalid_final_status_raises(self) -> None:
        """final_status 限终态二值（RECOVERED/MARKED_INFEASIBLE）。"""
        with pytest.raises(EntityValidationError):
            _make_entry(final_status="RUNNING")

    def test_invalid_execution_id_raises(self) -> None:
        """execution_id 有效 UUID（幂等键）。"""
        with pytest.raises(EntityValidationError):
            _make_entry(execution_id="bad-id")

    def test_naive_created_at_raises(self) -> None:
        """created_at timezone-aware."""
        with pytest.raises(EntityValidationError):
            _make_entry(created_at=datetime(2026, 1, 1))

    def test_negative_duration_raises(self) -> None:
        """duration_sec ≥ 0（闭环墙钟时长）。"""
        with pytest.raises(EntityValidationError):
            _make_entry(duration_sec=-1.0)

    def test_fix_attempts_count_must_match_enhanced_retry_count(self) -> None:
        """fix_attempts 条数 == enhanced_retry_count（每次尝试一条记录）。"""
        with pytest.raises(EntityValidationError):
            _make_entry(
                enhanced_retry_count=2,
                fix_attempts=(_make_attempt(attempt_no=1),),
            )


class TestTriggerCodeEnum:
    """TriggerCode 枚举契约."""

    def test_members(self) -> None:
        """两成员（389/382）."""
        assert {c.value for c in TriggerCode} == {"EXCEPTION_389", "EXCEPTION_382"}

    def test_str_comparison(self) -> None:
        """str Enum 与字符串比较（BDD/存储层 str 形态兼容）。"""
        assert TriggerCode.EXCEPTION_389 == "EXCEPTION_389"


class TestFeedbackOutcomeEnum:
    """FeedbackOutcome 枚举契约."""

    def test_members(self) -> None:
        """两终态成员."""
        assert {o.value for o in FeedbackOutcome} == {"RECOVERED", "MARKED_INFEASIBLE"}
