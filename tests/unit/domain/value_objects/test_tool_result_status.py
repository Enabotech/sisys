"""Story 4.7: ToolResultStatus.INFEASIBLE 枚举扩展单元测试.

覆盖 additive 枚举值（infeasible）、INVALID 既有「可重试」语义契约不回归、
SUCCESS 证据包契约不变量不回归、5 值全集边界。

TDD 红→绿：本文件先于枚举值追加（Subtask 1.7）。
"""

from __future__ import annotations

import uuid

import pytest

from src.domain.exceptions import EntityValidationError, EvidenceValidationFailedError
from src.domain.services.schema_validator import SchemaViolation
from src.domain.value_objects.tool_execution import ToolResult, ToolResultStatus


def _violation() -> SchemaViolation:
    """构造测试用 SchemaViolation."""
    return SchemaViolation(path="$.x", expected="int", actual="str", message="not int")


class TestInfeasibleStatus:
    """INFEASIBLE 新枚举值."""

    def test_infeasible_member_exists(self) -> None:
        """INFEASIBLE 枚举成员存在且值为 infeasible."""
        assert ToolResultStatus.INFEASIBLE.value == "infeasible"

    def test_enum_has_five_values(self) -> None:
        """5 值全集（4 既有 + infeasible additive）."""
        statuses = {s.value for s in ToolResultStatus}
        assert statuses == {"success", "failed", "invalid", "insufficient_data", "infeasible"}

    def test_infeasible_is_str_enum(self) -> None:
        """(str, Enum) 形态保持（additive 加值不改变基类）."""
        assert isinstance(ToolResultStatus.INFEASIBLE, str)
        assert ToolResultStatus.INFEASIBLE == "infeasible"


class TestInvalidSemanticsNotRegressed:
    """INVALID 既有「可重试」语义契约不回归（:247-249 注释契约）."""

    def test_invalid_with_violations_constructible(self) -> None:
        """INVALID + violations 非空可构造（AC-4 契约——4.7 订阅者依赖）."""
        result = ToolResult(
            tool_id=uuid.uuid4(),
            status=ToolResultStatus.INVALID,
            output={},
            evidence_package=None,
            validation_violations=(_violation(),),
        )
        assert result.status == ToolResultStatus.INVALID

    def test_invalid_without_violations_or_output_raises(self) -> None:
        """INVALID 空 violations 且空 output 抛 242（既有不变量）."""
        with pytest.raises(EntityValidationError):
            ToolResult(
                tool_id=uuid.uuid4(),
                status=ToolResultStatus.INVALID,
                output={},
                evidence_package=None,
            )


class TestSuccessContractNotRegressed:
    """SUCCESS 证据包契约不变量不回归（validate_complete → 386）."""

    def test_success_requires_evidence_package(self) -> None:
        """SUCCESS 无证据包调 validate_complete 抛 386（4.3 立法——重放边界注记依据）."""
        result = ToolResult(
            tool_id=uuid.uuid4(),
            status=ToolResultStatus.SUCCESS,
            output={"plan": "p", "result": "r"},
            evidence_package=None,
        )
        with pytest.raises(EvidenceValidationFailedError):
            result.validate_complete()


class TestInfeasibleResultContract:
    """INFEASIBLE 结果构造契约（AC-3——output 携带失败摘要）."""

    def test_infeasible_constructible_without_evidence(self) -> None:
        """INFEASIBLE 无证据包可构造（不适用 SUCCESS 证据包契约）."""
        result = ToolResult(
            tool_id=uuid.uuid4(),
            status=ToolResultStatus.INFEASIBLE,
            output={"error_signature": "a" * 64, "enhanced_retry_count": 3},
            evidence_package=None,
        )
        assert result.status == ToolResultStatus.INFEASIBLE
        assert result.retry_count == 0
