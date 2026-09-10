"""SchemaValidator 领域服务单元测试（Story 4.3 AC-1）

测试覆盖：
1. SchemaValidationResult + SchemaViolation 值对象（to_dict 序列化）
2. SchemaValidator 6 项校验规则：
   - 类型校验（type keyword）
   - 必填字段（required keyword）
   - 未声明字段禁止（additionalProperties=false 防 LLM 模型漂移）
   - 枚举约束（enum keyword）
   - 数组 items（items keyword）
   - 嵌套对象 properties（递归）
3. 空 schema 向后兼容（4.1a 既有 Tool 兼容性回归）
4. SchemaViolation 序列化脱敏（_sanitize_actual 处理 datetime/UUID/Decimal/bytes/嵌套）
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.domain.entities.tool import Tool, ToolCategory, ToolStatus
from src.domain.services.schema_validator import (
    SchemaValidationResult,
    SchemaValidator,
    SchemaViolation,
)


def _make_tool(
    input_schema: dict | None = None,
    output_schema: dict | None = None,
) -> Tool:
    """构造测试用 Tool 实体。"""
    now = datetime.now(UTC)
    return Tool(
        tool_id=uuid.uuid4(),
        name="test-tool",
        description="t",
        category=ToolCategory.ANALYSIS,
        input_schema=input_schema if input_schema is not None else {},
        output_schema=output_schema if output_schema is not None else {},
        status=ToolStatus.ACTIVE,
        version="1.0.0",
        created_at=now,
        updated_at=now,
    )


# ============================================================================
# 1. SchemaValidationResult + SchemaViolation 值对象
# ============================================================================


def test_schema_validation_result_creation_valid() -> None:
    """构造合法的 SchemaValidationResult（is_valid=True,violations 为空）"""
    result = SchemaValidationResult(is_valid=True)
    assert result.is_valid is True
    assert result.violations == ()
    assert result.validated_at is not None


def test_schema_validation_result_creation_invalid() -> None:
    """构造非法的 SchemaValidationResult（is_valid=False + violations）"""
    violation = SchemaViolation(
        path="/name",
        expected="string",
        actual=123,
        message="must be string",
    )
    result = SchemaValidationResult(is_valid=False, violations=(violation,))
    assert result.is_valid is False
    assert len(result.violations) == 1
    assert result.violations[0].path == "/name"


def test_schema_validation_result_to_dict() -> None:
    """SchemaValidationResult.to_dict() 序列化三字段"""
    violation = SchemaViolation(
        path="/x",
        expected="integer",
        actual="not-int",
        message="type mismatch",
    )
    result = SchemaValidationResult(is_valid=False, violations=(violation,))
    serialized = result.to_dict()
    assert serialized["is_valid"] is False
    assert len(serialized["violations"]) == 1
    assert serialized["violations"][0]["path"] == "/x"
    assert serialized["violations"][0]["expected"] == "integer"
    assert "validated_at" in serialized


def test_schema_violation_frozen() -> None:
    """SchemaViolation 是 frozen dataclass,不允许修改"""
    violation = SchemaViolation(
        path="/x",
        expected="string",
        actual=1,
        message="m",
    )
    with pytest.raises(Exception):  # FrozenInstanceError
        violation.path = "/y"  # type: ignore[misc]


# ============================================================================
# 2. 类型校验（type keyword）
# ============================================================================


def test_type_string_passes() -> None:
    """type=string 且实际值是字符串 → 通过"""
    tool = _make_tool(input_schema={"type": "object", "properties": {"name": {"type": "string"}}})
    result = SchemaValidator.validate_arguments(tool, {"name": "hello"})
    assert result.is_valid is True


def test_type_string_fails() -> None:
    """type=string 但实际值是整数 → 校验失败 + violation.path 指向错误字段"""
    tool = _make_tool(input_schema={"type": "object", "properties": {"name": {"type": "string"}}})
    result = SchemaValidator.validate_arguments(tool, {"name": 123})
    assert result.is_valid is False
    assert len(result.violations) >= 1
    violation = result.violations[0]
    assert violation.path == "/name"
    assert "string" in violation.expected


# ============================================================================
# 3. 必填字段（required keyword）
# ============================================================================


def test_required_field_present_passes() -> None:
    """required 字段全部存在 → 通过"""
    tool = _make_tool(
        input_schema={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
    )
    result = SchemaValidator.validate_arguments(tool, {"name": "hello"})
    assert result.is_valid is True


def test_required_field_missing_fails() -> None:
    """required 字段缺失 → 校验失败"""
    tool = _make_tool(
        input_schema={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
    )
    result = SchemaValidator.validate_arguments(tool, {})
    assert result.is_valid is False
    assert any(v.path == "/name" for v in result.violations)


# ============================================================================
# 4. additionalProperties=false 防 LLM 模型漂移
# ============================================================================


def test_additional_properties_false_rejects_unknown_field() -> None:
    """additionalProperties=false 时未声明字段被拒绝(防 LLM 模型漂移)"""
    tool = _make_tool(
        input_schema={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "additionalProperties": False,
        }
    )
    result = SchemaValidator.validate_arguments(tool, {"name": "x", "unknown_field": "y"})
    assert result.is_valid is False
    assert any(v.path == "/unknown_field" for v in result.violations)


def test_default_injects_additional_properties_false() -> None:
    """SchemaValidator 默认对所有 properties 子 schema 注入 additionalProperties=false"""
    tool = _make_tool(
        input_schema={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            # 故意不声明 additionalProperties
        }
    )
    result = SchemaValidator.validate_arguments(tool, {"name": "x", "extra": "y"})
    assert result.is_valid is False


# ============================================================================
# 5. 枚举约束（enum keyword）
# ============================================================================


def test_enum_valid_value_passes() -> None:
    """enum 值在集合内 → 通过"""
    tool = _make_tool(
        input_schema={
            "type": "object",
            "properties": {"status": {"type": "string", "enum": ["active", "inactive"]}},
        }
    )
    result = SchemaValidator.validate_arguments(tool, {"status": "active"})
    assert result.is_valid is True


def test_enum_invalid_value_fails() -> None:
    """enum 值不在集合内 → 校验失败"""
    tool = _make_tool(
        input_schema={
            "type": "object",
            "properties": {"status": {"type": "string", "enum": ["active", "inactive"]}},
        }
    )
    result = SchemaValidator.validate_arguments(tool, {"status": "unknown"})
    assert result.is_valid is False
    assert any(v.path == "/status" for v in result.violations)


# ============================================================================
# 6. 数组 items 校验
# ============================================================================


def test_array_items_type_passes() -> None:
    """数组 items 类型符合 → 通过"""
    tool = _make_tool(
        input_schema={
            "type": "object",
            "properties": {"tags": {"type": "array", "items": {"type": "string"}}},
        }
    )
    result = SchemaValidator.validate_arguments(tool, {"tags": ["a", "b", "c"]})
    assert result.is_valid is True


def test_array_items_type_fails() -> None:
    """数组 items 类型不符 → 校验失败 + path 含索引"""
    tool = _make_tool(
        input_schema={
            "type": "object",
            "properties": {"tags": {"type": "array", "items": {"type": "string"}}},
        }
    )
    result = SchemaValidator.validate_arguments(tool, {"tags": ["a", 1, "c"]})
    assert result.is_valid is False
    assert any(v.path == "/tags/1" for v in result.violations)


# ============================================================================
# 7. 嵌套对象 properties 递归校验
# ============================================================================


def test_nested_object_recursion_passes() -> None:
    """嵌套对象 properties 递归 → 通过"""
    tool = _make_tool(
        input_schema={
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {"age": {"type": "integer"}},
                }
            },
        }
    )
    result = SchemaValidator.validate_arguments(tool, {"user": {"age": 25}})
    assert result.is_valid is True


def test_nested_object_recursion_fails() -> None:
    """嵌套对象 properties 递归校验 → 失败时 path 含完整路径"""
    tool = _make_tool(
        input_schema={
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {"age": {"type": "integer"}},
                }
            },
        }
    )
    result = SchemaValidator.validate_arguments(tool, {"user": {"age": "not-int"}})
    assert result.is_valid is False
    assert any(v.path == "/user/age" for v in result.violations)


# ============================================================================
# 8. 空 schema 向后兼容（4.1a 回归）
# ============================================================================


def test_empty_input_schema_passes() -> None:
    """Tool.input_schema={} 时 validate_arguments 返回 is_valid=True(向后兼容 4.1a 既有 Tool)"""
    tool = _make_tool(input_schema={})
    result = SchemaValidator.validate_arguments(tool, {"anything": "goes"})
    assert result.is_valid is True


def test_empty_output_schema_passes() -> None:
    """Tool.output_schema={} 时 validate_output 返回 is_valid=True"""
    tool = _make_tool(output_schema={})
    result = SchemaValidator.validate_output(tool, {"anything": "goes"})
    assert result.is_valid is True


# ============================================================================
# 9. SchemaViolation 序列化脱敏（_sanitize_actual）
# ============================================================================


def test_violation_sanitize_datetime() -> None:
    """SchemaViolation.to_dict() 对 datetime 脱敏为 ISO 字符串"""
    dt = datetime(2026, 9, 10, 12, 0, 0, tzinfo=UTC)
    violation = SchemaViolation(path="/t", expected="datetime", actual=dt, message="m")
    serialized = violation.to_dict()
    assert isinstance(serialized["actual"], str)
    assert "2026" in serialized["actual"]


def test_violation_sanitize_uuid() -> None:
    """SchemaViolation.to_dict() 对 UUID 脱敏为字符串"""
    u = uuid.uuid4()
    violation = SchemaViolation(path="/u", expected="uuid", actual=u, message="m")
    serialized = violation.to_dict()
    assert isinstance(serialized["actual"], str)
    assert serialized["actual"] == str(u)


def test_violation_sanitize_decimal() -> None:
    """SchemaViolation.to_dict() 对 Decimal 脱敏为字符串"""
    d = Decimal("123.45")
    violation = SchemaViolation(path="/d", expected="decimal", actual=d, message="m")
    serialized = violation.to_dict()
    assert isinstance(serialized["actual"], str)


def test_violation_sanitize_bytes() -> None:
    """SchemaViolation.to_dict() 对 bytes 脱敏为 hex 字符串"""
    b = b"binary-data"
    violation = SchemaViolation(path="/b", expected="bytes", actual=b, message="m")
    serialized = violation.to_dict()
    assert isinstance(serialized["actual"], str)


def test_violation_sanitize_nested_dict() -> None:
    """SchemaViolation.to_dict() 递归处理嵌套 dict"""
    violation = SchemaViolation(
        path="/obj",
        expected="object",
        actual={"key": uuid.uuid4(), "nested": [datetime.now(UTC)]},
        message="m",
    )
    serialized = violation.to_dict()
    assert isinstance(serialized["actual"], dict)
    assert isinstance(serialized["actual"]["key"], str)
    assert isinstance(serialized["actual"]["nested"][0], str)


def test_violation_sanitize_nan_fallback() -> None:
    """SchemaViolation.to_dict() 对 NaN/Inf 兜底为 None(JSON 不支持)"""
    nan_value = float("nan")
    inf_value = float("inf")
    violation1 = SchemaViolation(path="/n", expected="number", actual=nan_value, message="m")
    violation2 = SchemaViolation(path="/i", expected="number", actual=inf_value, message="m")
    assert violation1.to_dict()["actual"] is None
    assert violation2.to_dict()["actual"] is None


# ============================================================================
# 10. validate_output 与 validate_arguments 行为一致（共用实现）
# ============================================================================


def test_validate_output_fails_on_type_mismatch() -> None:
    """validate_output 与 validate_arguments 共用同一校验逻辑"""
    tool = _make_tool(output_schema={"type": "object", "properties": {"result": {"type": "integer"}}})
    result = SchemaValidator.validate_output(tool, {"result": "not-int"})
    assert result.is_valid is False
    assert any(v.path == "/result" for v in result.violations)
