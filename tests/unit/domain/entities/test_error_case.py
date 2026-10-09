"""Story 4.7: ErrorCase 聚合根单元测试.

覆盖构造不变量（UUID/签名 64 hex/分类计数守恒/自然键）、字段域校验
（截断边界/枚举值域）、非法构造抛 EntityValidationError(242)。

TDD 红→绿：本文件先于 src/domain/entities/error_case.py 实现（Subtask 1.1）。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from src.domain.entities.error_case import ErrorCase
from src.domain.exceptions import EntityValidationError
from src.domain.value_objects.validation_feedback import FeedbackOutcome

_SIG_64 = "a" * 64  # 完整 sha256 hexdigest（64 hex——三处口径同一）


def _make_case(**overrides: object) -> ErrorCase:
    """构造合法 ErrorCase 基准实例（默认 RECOVERED 首例形态）."""
    now = datetime.now(UTC)
    kwargs: dict = {
        "case_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "tool_id": uuid.uuid4(),
        "error_signature": _SIG_64,
        "error_category": "SCHEMA_VIOLATION",
        "stderr_excerpt": "Traceback ... KeyError: 'x'",
        "fix_summary": "将 result 前缀改为 OK_",
        "outcome": FeedbackOutcome.RECOVERED,
        "recovered_count": 1,
        "infeasible_count": 0,
        "occurrence_count": 1,
        "last_seen_at": now,
        "created_at": now,
    }
    kwargs.update(overrides)
    return ErrorCase(**kwargs)


class TestErrorCaseConstruction:
    """合法构造与默认值."""

    def test_valid_construction(self) -> None:
        """基准形态构造成功."""
        case = _make_case()
        assert case.error_signature == _SIG_64
        assert case.outcome == FeedbackOutcome.RECOVERED
        assert case.occurrence_count == 1

    def test_default_excerpts_are_empty(self) -> None:
        """stderr_excerpt/fix_summary 默认空串（构造器默认值与 migration DEFAULT '' 对齐）."""
        case = _make_case(stderr_excerpt=None, fix_summary=None)
        assert case.stderr_excerpt == ""
        assert case.fix_summary == ""


class TestErrorCaseInvariants:
    """构造不变量（非法构造抛 242）."""

    def test_invalid_signature_not_64_hex_raises(self) -> None:
        """签名必须为 64 hex（完整 sha256 hexdigest）."""
        with pytest.raises(EntityValidationError):
            _make_case(error_signature="a" * 16)

    def test_invalid_signature_non_hex_raises(self) -> None:
        """签名必须为 hex 字符."""
        with pytest.raises(EntityValidationError):
            _make_case(error_signature="z" * 64)

    def test_invalid_signature_0x_prefix_raises(self) -> None:
        """「0x」前缀 64 串不是合法 hexdigest（R2 收紧：int(,16) 曾宽容此形态）."""
        with pytest.raises(EntityValidationError):
            _make_case(error_signature="0x" + "a" * 62)

    def test_invalid_tenant_id_raises(self) -> None:
        """tenant_id 必须为有效 UUID."""
        with pytest.raises(EntityValidationError):
            _make_case(tenant_id="not-a-uuid")

    def test_invalid_tool_id_raises(self) -> None:
        """tool_id 必须为有效 UUID."""
        with pytest.raises(EntityValidationError):
            _make_case(tool_id=12345)

    def test_occurrence_count_mismatch_raises(self) -> None:
        """occurrence_count 必须等于 recovered_count + infeasible_count（R3-2 守恒）."""
        with pytest.raises(EntityValidationError):
            _make_case(recovered_count=1, infeasible_count=0, occurrence_count=2)

    def test_occurrence_count_zero_raises(self) -> None:
        """occurrence_count ≥ 1（案例行存在即至少一次观测）."""
        with pytest.raises(EntityValidationError):
            _make_case(recovered_count=0, infeasible_count=0, occurrence_count=0)

    def test_negative_counts_raise(self) -> None:
        """分类计数 ≥ 0."""
        with pytest.raises(EntityValidationError):
            _make_case(recovered_count=-1, infeasible_count=0, occurrence_count=-1)

    def test_stderr_excerpt_over_2000_raises_or_truncates(self) -> None:
        """stderr_excerpt 域 ≤2000（超限拒收或截断——域约束不静默溢出）."""
        case = _make_case(stderr_excerpt="x" * 3000)
        assert len(case.stderr_excerpt) <= 2000

    def test_fix_summary_over_2000_truncates(self) -> None:
        """fix_summary 域 ≤2000（覆写来源派生截断——R3-9）."""
        case = _make_case(fix_summary="y" * 3000)
        assert len(case.fix_summary) <= 2000

    def test_invalid_outcome_raises(self) -> None:
        """outcome 必须为 FeedbackOutcome 枚举成员."""
        with pytest.raises(EntityValidationError):
            _make_case(outcome="SOMETHING_ELSE")

    def test_created_at_must_be_timezone_aware(self) -> None:
        """created_at timezone-aware（naive datetime 拒收）."""
        naive = datetime(2026, 1, 1, 12, 0, 0)
        with pytest.raises(EntityValidationError):
            _make_case(created_at=naive)

    def test_error_category_empty_raises(self) -> None:
        """error_category 非空（首写定格——category 二次过滤前提）."""
        with pytest.raises(EntityValidationError):
            _make_case(error_category="")


class TestErrorCaseNaturalKey:
    """自然键语义."""

    def test_natural_key_composition(self) -> None:
        """自然键 = (tenant_id, tool_id, error_signature) 三元组."""
        case = _make_case()
        assert case.natural_key == (case.tenant_id, case.tool_id, case.error_signature)
