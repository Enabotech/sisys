"""Story 4.1a: ToolExecution 值对象单元测试

TDD 测试覆盖：
- ToolCall frozen dataclass 不变性
- ExecutionContext frozen dataclass 不变性 + 边界
- ToolResultStatus 4 值边界
- EvidencePackage 9 字段 + 完整性校验
- ToolResult 完整性校验（success 必填 evidence_package）
"""

from __future__ import annotations

import uuid
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from src.domain.exceptions import (
    EntityValidationError,
    EvidenceValidationFailedError,
)
from src.domain.value_objects.tool_execution import (
    EvidencePackage,
    ExecutionContext,
    ToolCall,
    ToolResult,
    ToolResultStatus,
)


def _make_execution_context(**kwargs) -> ExecutionContext:
    """工厂函数：构造测试 ExecutionContext"""
    defaults = {
        "tenant_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "session_id": "sess-1",
        "trace_id": "trace-1",
        "timeout_sec": 60.0,
    }
    defaults.update(kwargs)
    return ExecutionContext(**defaults)


def _make_evidence_package(**kwargs) -> EvidencePackage:
    """工厂函数：构造测试 EvidencePackage"""
    defaults = {
        "input_hash": "abc123",
        "rule_version": "BLM-v3.2",
        "plan": "step 1: ...",
        "code": "result = 1 + 1",
        "result": "2",
        "observation": "ok",
        "validation": "valid",
        "confidence": 0.95,
        "citations": ["cite-1"],
    }
    defaults.update(kwargs)
    return EvidencePackage(**defaults)


class TestToolCall:
    """ToolCall 值对象测试"""

    def test_required_fields(self) -> None:
        tool_id = uuid.uuid4()
        call = ToolCall(tool_id=tool_id)
        assert call.tool_id == tool_id
        assert call.arguments == {}

    def test_with_arguments(self) -> None:
        tool_id = uuid.uuid4()
        call = ToolCall(
            tool_id=tool_id,
            arguments={"x": 1},
            tenant_id=uuid.uuid4(),
        )
        assert call.arguments == {"x": 1}
        assert call.tenant_id is not None

    def test_frozen_dataclass(self) -> None:
        call = ToolCall(tool_id=uuid.uuid4())
        with pytest.raises(FrozenInstanceError):
            call.arguments = {"y": 2}  # type: ignore[misc]


class TestExecutionContext:
    """ExecutionContext 值对象测试"""

    def test_required_tenant_id(self) -> None:
        ctx = _make_execution_context()
        assert ctx.tenant_id is not None

    def test_timeout_must_be_positive(self) -> None:
        with pytest.raises(EntityValidationError):
            _make_execution_context(timeout_sec=0)
        with pytest.raises(EntityValidationError):
            _make_execution_context(timeout_sec=-1.0)

    def test_default_timeout(self) -> None:
        ctx = _make_execution_context(timeout_sec=60.0)
        assert ctx.timeout_sec == 60.0

    def test_frozen_dataclass(self) -> None:
        ctx = _make_execution_context()
        with pytest.raises(FrozenInstanceError):
            ctx.session_id = "other"  # type: ignore[misc]


class TestToolResultStatus:
    """ToolResultStatus 枚举测试"""

    def test_has_four_values(self) -> None:
        statuses = {s.value for s in ToolResultStatus}
        assert len(statuses) == 4

    def test_contains_all_statuses(self) -> None:
        expected = {"success", "failed", "invalid", "insufficient_data"}
        actual = {s.value for s in ToolResultStatus}
        assert actual == expected


class TestEvidencePackage:
    """EvidencePackage 值对象测试"""

    def test_has_nine_fields(self) -> None:
        """EvidencePackage 必含 9 字段"""
        ep = _make_evidence_package()
        assert ep.input_hash == "abc123"
        assert ep.rule_version == "BLM-v3.2"
        assert ep.plan == "step 1: ..."
        assert ep.code == "result = 1 + 1"
        assert ep.result == "2"
        assert ep.observation == "ok"
        assert ep.validation == "valid"
        assert ep.confidence == 0.95
        assert ep.citations == ["cite-1"]

    def test_default_values(self) -> None:
        """默认值"""
        ep = EvidencePackage()
        assert ep.input_hash == ""
        assert ep.confidence == 0.0
        assert ep.citations == []

    def test_completeness_pass(self) -> None:
        """完整性校验通过"""
        ep = _make_evidence_package()
        assert ep.validate_complete() is True

    def test_completeness_fail_missing_plan(self) -> None:
        """缺 plan 字段抛 EvidenceValidationFailedError"""
        ep = _make_evidence_package(plan="")
        with pytest.raises(EvidenceValidationFailedError) as exc_info:
            ep.validate_complete()
        assert "plan" in exc_info.value.context["missing_fields"]

    def test_completeness_fail_missing_multiple_fields(self) -> None:
        """缺多字段抛 EvidenceValidationFailedError"""
        ep = _make_evidence_package(plan="", code="")
        with pytest.raises(EvidenceValidationFailedError) as exc_info:
            ep.validate_complete()
        missing = exc_info.value.context["missing_fields"]
        assert "plan" in missing
        assert "code" in missing

    def test_completeness_confidence_out_of_range(self) -> None:
        """confidence 越界"""
        ep = _make_evidence_package(confidence=1.5)
        with pytest.raises(EvidenceValidationFailedError):
            ep.validate_complete()


class TestToolResult:
    """ToolResult 值对象测试"""

    def test_basic_construct(self) -> None:
        result = ToolResult(
            tool_id=uuid.uuid4(),
            status=ToolResultStatus.SUCCESS,
        )
        assert result.status == ToolResultStatus.SUCCESS

    def test_completed_at_after_started_at(self) -> None:
        with pytest.raises(EntityValidationError):
            now = datetime.now(UTC)
            ToolResult(
                tool_id=uuid.uuid4(),
                status=ToolResultStatus.SUCCESS,
                started_at=now,
                completed_at=now - timedelta(seconds=1),
            )

    def test_success_requires_evidence_package(self) -> None:
        """success 状态必须包含 evidence_package"""
        result = ToolResult(
            tool_id=uuid.uuid4(),
            status=ToolResultStatus.SUCCESS,
            evidence_package=None,
        )
        with pytest.raises(EvidenceValidationFailedError):
            result.validate_complete()

    def test_success_with_complete_evidence_package(self) -> None:
        """success + 完整 evidence_package"""
        result = ToolResult(
            tool_id=uuid.uuid4(),
            status=ToolResultStatus.SUCCESS,
            evidence_package=_make_evidence_package(),
        )
        assert result.validate_complete() is True

    def test_failed_status_no_evidence_required(self) -> None:
        """failed 状态不强制 evidence_package"""
        result = ToolResult(
            tool_id=uuid.uuid4(),
            status=ToolResultStatus.FAILED,
            evidence_package=None,
        )
        assert result.validate_complete() is True

    def test_invalid_status_no_evidence_required(self) -> None:
        """invalid 状态不强制 evidence_package"""
        result = ToolResult(
            tool_id=uuid.uuid4(),
            status=ToolResultStatus.INVALID,
            evidence_package=None,
        )
        assert result.validate_complete() is True
