"""ToolResult 字段扩展单元测试（Story 4.3 AC-4）

测试覆盖：
1. ToolResult 新增 validation_violations / retry_count 字段
2. status=INVALID 时 validation_violations 非空 OR output 非空(向后兼容 4.1a)
3. EvidencePackage.validation 接受 str | dict
4. ToolResultValidationError schema_violations 参数(向后兼容)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from src.domain.exceptions import (
    EvidenceValidationFailedError,
    ToolResultValidationError,
)
from src.domain.services.schema_validator import SchemaViolation
from src.domain.value_objects.tool_execution import (
    EvidencePackage,
    ToolResult,
    ToolResultStatus,
)


def _make_minimal_result(**overrides) -> ToolResult:
    """构造最小合法 ToolResult(便于覆盖测试)"""
    # 默认值显式列出(避免 **dict 解包触发 mypy invariant 报错)
    base_kwargs: dict[str, Any] = {
        "tool_id": uuid.uuid4(),
        "status": ToolResultStatus.SUCCESS,
        "output": {},
        "evidence_package": EvidencePackage(
            input_hash="h",
            rule_version="v",
            plan="p",
            code="c",
            result="r",
            observation="o",
            validation="passed",
            confidence=0.5,
        ),
        "started_at": datetime.now(UTC),
        "completed_at": datetime.now(UTC),
    }
    # overrides 显式赋值(避免 dict 不变性与 mypy 类型推导冲突)
    for key, value in overrides.items():
        base_kwargs[key] = value
    return ToolResult(
        tool_id=base_kwargs["tool_id"],
        status=base_kwargs["status"],
        output=base_kwargs["output"],
        evidence_package=base_kwargs["evidence_package"],
        started_at=base_kwargs["started_at"],
        completed_at=base_kwargs["completed_at"],
        **{
            k: v
            for k, v in base_kwargs.items()
            if k
            not in {
                "tool_id",
                "status",
                "output",
                "evidence_package",
                "started_at",
                "completed_at",
            }
        },
    )


# ============================================================================
# 1. 新增字段
# ============================================================================


def test_tool_result_has_validation_violations_field() -> None:
    """ToolResult 必须含 validation_violations 字段(默认空 tuple)"""
    result = _make_minimal_result()
    assert result.validation_violations == ()


def test_tool_result_has_retry_count_field() -> None:
    """ToolResult 必须含 retry_count 字段(默认 0)"""
    result = _make_minimal_result()
    assert result.retry_count == 0


def test_tool_result_retry_count_increment() -> None:
    """retry_count 可显式设置(供重试路径使用)"""
    result = _make_minimal_result(retry_count=2)
    assert result.retry_count == 2


# ============================================================================
# 2. status=INVALID 行为(Story 4.3 向后兼容 4.1a 既有失败路径)
# ============================================================================


def test_invalid_status_passes_with_violations() -> None:
    """status=INVALID + validation_violations 非空 → 通过(Story 4.3 扩展路径)"""
    violation = SchemaViolation(path="/x", expected="string", actual=1, message="m")
    result = _make_minimal_result(
        status=ToolResultStatus.INVALID,
        evidence_package=None,
        output={},
        validation_violations=(violation,),
    )
    assert result.validation_violations == (violation,)


def test_invalid_status_raises_when_no_violations_and_no_output() -> None:
    """Round 2 P1-1:AC-4 契约严格化 — status=INVALID 时 validation_violations 与 output 至少一项非空

    Story 4.3 AC-4 契约(Round 2 修正):
    status=INVALID 时必须有 validation_violations(Schema 校验失败信息)
    或 output(LLM 实际输出,但 schema 不匹配)。两者皆空 → EntityValidationError。

    向后兼容说明:4.1a 既有代码路径使用 status=FAILED / status=SUCCESS,
    不使用 status=INVALID。Story 4.3 引入 status=INVALID 必须携带违规信息,
    否则下游 4.7 Validation Feedback 订阅者无法区分"INVALID(可重试)"
    与"FAILED(纯执行失败)"语义。
    """
    from src.domain.exceptions import EntityValidationError

    with pytest.raises(EntityValidationError) as exc_info:
        _make_minimal_result(
            status=ToolResultStatus.INVALID,
            evidence_package=None,
            output={},
            validation_violations=(),
        )
    assert "validation_violations|output" in str(exc_info.value.context.get("sub_field", ""))


def test_invalid_status_passes_when_has_violations() -> None:
    """status=INVALID + 有 violations → 通过校验(Round 2 P1-1)"""
    result = _make_minimal_result(
        status=ToolResultStatus.INVALID,
        evidence_package=None,
        output={},
        validation_violations=(SchemaViolation(path="/x", expected="string", actual=123, message="bad"),),
    )
    assert result.status == ToolResultStatus.INVALID


def test_invalid_status_passes_when_has_output() -> None:
    """status=INVALID + 有 output → 通过校验(Round 2 P1-1)"""
    result = _make_minimal_result(
        status=ToolResultStatus.INVALID,
        evidence_package=None,
        output={"partial": "result"},
        validation_violations=(),
    )
    assert result.status == ToolResultStatus.INVALID


# ============================================================================
# 3. EvidencePackage.validation 升级(接受 str | dict)
# ============================================================================


def test_evidence_package_validation_accepts_string() -> None:
    """EvidencePackage.validation 接受 str(向后兼容 4.1a)"""
    ep = EvidencePackage(
        input_hash="h",
        rule_version="v",
        plan="p",
        code="c",
        result="r",
        observation="o",
        validation="passed",
    )
    ep.validate_complete()  # 不抛错


def test_evidence_package_validation_accepts_dict() -> None:
    """EvidencePackage.validation 接受 dict(Story 4.3 结构化失败详情)"""
    ep = EvidencePackage(
        input_hash="h",
        rule_version="v",
        plan="p",
        code="c",
        result="r",
        observation="o",
        validation={"passed": False, "violations": [{"path": "/x", "message": "m"}]},
    )
    ep.validate_complete()  # 不抛错


def test_evidence_package_validation_dict_must_have_passed_key() -> None:
    """EvidencePackage.validation 为 dict 时必须含 'passed' 键"""
    ep = EvidencePackage(
        input_hash="h",
        rule_version="v",
        plan="p",
        code="c",
        result="r",
        observation="o",
        validation={"violations": []},  # 缺 passed
    )
    with pytest.raises(EvidenceValidationFailedError):
        ep.validate_complete()


# ============================================================================
# 4. ToolResultValidationError schema_violations 参数(向后兼容)
# ============================================================================


def test_tool_result_validation_error_backward_compat_no_violations() -> None:
    """ToolResultValidationError 不传 schema_violations → 向后兼容(默认 None)"""
    err = ToolResultValidationError(
        message="m",
        tool_id="tid",
        execution_id="eid",
        reason="r",
    )
    assert "schema_violations" not in err.context


def test_tool_result_validation_error_with_violations() -> None:
    """ToolResultValidationError 传 schema_violations → context 含 violations"""
    violations = [{"path": "/x", "expected": "string", "actual": 1, "message": "m"}]
    err = ToolResultValidationError(
        message="m",
        tool_id="tid",
        execution_id="eid",
        schema_violations=violations,
    )
    assert err.context["schema_violations"] == violations
