"""SchemaValidatorPort 端口契约测试（Story 4.3 AC-2）

11 维度契约验证：
1. Protocol @runtime_checkable 校验
2. validate_arguments 方法签名
3. validate_output 方法签名
4. validate_schema_compatibility 方法签名
5. JsonSchemaValidatorImpl 实现完整
6. 所有方法非 async def
7. 空 schema 向后兼容
8. SchemaViolation 序列化字段完整性
9. SchemaCompatibilityResult 字段完整性
10. BreakingChange / NonBreakingChange 值对象字段
11. ChangeType 枚举值完整
"""

from __future__ import annotations

import uuid
from dataclasses import fields
from datetime import UTC, datetime

from src.application.ports.schema_validator import (
    BreakingChange,
    ChangeType,
    NonBreakingChange,
    NonBreakingChangeType,
    SchemaCompatibilityResult,
    SchemaValidatorPort,
)
from src.domain.entities.tool import Tool, ToolCategory, ToolStatus
from src.domain.services.schema_validator import (
    SchemaValidationResult,
    SchemaViolation,
)
from src.infrastructure.validation.jsonschema_validator import JsonSchemaValidatorImpl


def _make_tool(input_schema: dict, output_schema: dict | None = None) -> Tool:
    now = datetime.now(UTC)
    return Tool(
        tool_id=uuid.uuid4(),
        name="t",
        description="t",
        category=ToolCategory.ANALYSIS,
        input_schema=input_schema,
        output_schema=output_schema or {},
        status=ToolStatus.ACTIVE,
        version="1.0.0",
        created_at=now,
        updated_at=now,
    )


# ============================================================================
# 1. Protocol @runtime_checkable
# ============================================================================


def test_protocol_runtime_checkable() -> None:
    """JsonSchemaValidatorImpl 必须实现 SchemaValidatorPort Protocol"""
    impl = JsonSchemaValidatorImpl()
    assert isinstance(impl, SchemaValidatorPort)


def test_protocol_has_three_methods() -> None:
    """Protocol 必须有 3 个方法:validate_arguments / validate_output / validate_schema_compatibility"""
    method_names = {"validate_arguments", "validate_output", "validate_schema_compatibility"}
    for name in method_names:
        assert hasattr(SchemaValidatorPort, name), f"缺少方法 {name}"


# ============================================================================
# 2-4. 方法签名验证
# ============================================================================


def test_validate_arguments_signature() -> None:
    """validate_arguments 签名:(tool, arguments) -> SchemaValidationResult"""
    impl = JsonSchemaValidatorImpl()
    tool = _make_tool(input_schema={"type": "object"})
    result = impl.validate_arguments(tool, {})
    assert isinstance(result, SchemaValidationResult)


def test_validate_output_signature() -> None:
    """validate_output 签名:(tool, output) -> SchemaValidationResult"""
    impl = JsonSchemaValidatorImpl()
    tool = _make_tool(input_schema={}, output_schema={"type": "object"})
    result = impl.validate_output(tool, {})
    assert isinstance(result, SchemaValidationResult)


def test_validate_schema_compatibility_signature() -> None:
    """validate_schema_compatibility 签名:(old_schema, new_schema) -> SchemaCompatibilityResult"""
    impl = JsonSchemaValidatorImpl()
    result = impl.validate_schema_compatibility({}, {})
    assert isinstance(result, SchemaCompatibilityResult)


# ============================================================================
# 5. 实现完整性
# ============================================================================


def test_impl_implements_all_protocol_methods() -> None:
    """JsonSchemaValidatorImpl 必须实现 Protocol 全部方法"""
    impl = JsonSchemaValidatorImpl()
    for name in ["validate_arguments", "validate_output", "validate_schema_compatibility"]:
        assert hasattr(impl, name), f"缺少方法 {name}"
        assert callable(getattr(impl, name)), f"{name} 必须可调用"


def test_methods_not_async() -> None:
    """所有方法为同步 def（非 async）— 委托 jsonschema 同步 API"""
    import inspect

    method_names = ["validate_arguments", "validate_output", "validate_schema_compatibility"]
    for name in method_names:
        method = getattr(JsonSchemaValidatorImpl, name)
        assert not inspect.iscoroutinefunction(method), f"{name} 必须为同步 def"


# ============================================================================
# 6. 空 schema 向后兼容
# ============================================================================


def test_empty_schema_passes() -> None:
    """空 schema → is_valid=True(向后兼容)"""
    impl = JsonSchemaValidatorImpl()
    tool = _make_tool(input_schema={}, output_schema={})
    assert impl.validate_arguments(tool, {}).is_valid is True
    assert impl.validate_output(tool, {}).is_valid is True


# ============================================================================
# 7-8. SchemaViolation / SchemaValidationResult 字段完整性
# ============================================================================


def test_schema_violation_four_fields() -> None:
    """SchemaViolation 必须 4 字段:path / expected / actual / message"""
    expected = {f.name for f in fields(SchemaViolation) if f.init}
    assert expected == {"path", "expected", "actual", "message"}


def test_schema_validation_result_three_fields() -> None:
    """SchemaValidationResult 必须 3 字段:is_valid / violations / validated_at"""
    expected = {f.name for f in fields(SchemaValidationResult) if f.init}
    assert expected == {"is_valid", "violations", "validated_at"}


# ============================================================================
# 9-10. SchemaCompatibilityResult / BreakingChange / NonBreakingChange 字段
# ============================================================================


def test_schema_compatibility_result_five_fields() -> None:
    """SchemaCompatibilityResult 必须 5 字段"""
    expected = {f.name for f in fields(SchemaCompatibilityResult) if f.init}
    assert expected == {
        "is_compatible",
        "compatibility_level",
        "breaking_changes",
        "non_breaking_changes",
        "schema_diff",
    }


def test_breaking_change_seven_fields() -> None:
    """BreakingChange 必须 7 字段"""
    expected = {f.name for f in fields(BreakingChange) if f.init}
    assert expected == {
        "change_type",
        "path",
        "old_value",
        "new_value",
        "description",
        "severity",
        "remediation",
    }


def test_non_breaking_change_five_fields() -> None:
    """NonBreakingChange 必须 5 字段"""
    expected = {f.name for f in fields(NonBreakingChange) if f.init}
    assert expected == {
        "change_type",
        "path",
        "old_value",
        "new_value",
        "description",
    }


# ============================================================================
# 11. ChangeType 枚举完整性
# ============================================================================


def test_change_type_has_eight_values() -> None:
    """ChangeType 枚举必须 8 类破坏性变更类型(AC-2 验收清单)"""
    values = {v.value for v in ChangeType}
    expected = {
        "required_field_added",
        "required_field_removed",
        "field_type_narrowed",
        "field_type_changed",
        "enum_value_removed",
        "additional_props_restricted",
        "nested_schema_tightened",
        "min_value_increased",
    }
    assert values == expected


def test_non_breaking_change_type_has_seven_values() -> None:
    """NonBreakingChangeType 枚举必须 7 类非破坏性变更类型"""
    values = {v.value for v in NonBreakingChangeType}
    expected = {
        "optional_field_added",
        "field_type_widened",
        "enum_value_added",
        "additional_props_relaxed",
        "default_added",
        "description_updated",
        "pattern_relaxed",
    }
    assert values == expected
