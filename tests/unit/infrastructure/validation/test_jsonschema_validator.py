"""JsonSchemaValidatorImpl 单元测试（Story 4.3 AC-2）

测试覆盖：
1. validate_arguments / validate_output 正确转换 jsonschema.ValidationError → SchemaViolation
2. 空 schema 向后兼容
3. validate_schema_compatibility 12 条规则检测
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from src.application.ports.schema_validator import (
    ChangeType,
    NonBreakingChangeType,
)
from src.domain.entities.tool import Tool, ToolCategory, ToolStatus
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
# 1. validate_arguments / validate_output
# ============================================================================


def test_validate_arguments_with_full_draft7_features() -> None:
    """完整 Draft 7+ 验证：支持 $ref / allOf 等领域层 SchemaValidator 不支持的关键词"""
    tool = _make_tool(
        input_schema={
            "type": "object",
            "properties": {
                "value": {"type": "integer", "minimum": 0, "maximum": 100},
                "email": {"type": "string", "format": "email"},
            },
            "required": ["value"],
        }
    )
    impl = JsonSchemaValidatorImpl()
    result = impl.validate_arguments(tool, {"value": 50, "email": "a@b.com"})
    assert result.is_valid is True


def test_validate_arguments_minimum_violation() -> None:
    """minimum 校验违规 → violations 非空"""
    tool = _make_tool(
        input_schema={
            "type": "object",
            "properties": {"age": {"type": "integer", "minimum": 0}},
        }
    )
    impl = JsonSchemaValidatorImpl()
    result = impl.validate_arguments(tool, {"age": -1})
    assert result.is_valid is False
    assert len(result.violations) >= 1
    assert any(v.path == "/age" for v in result.violations)


def test_validate_output_empty_schema_passes() -> None:
    """空 schema 向后兼容 → 通过"""
    tool = _make_tool(input_schema={}, output_schema={})
    impl = JsonSchemaValidatorImpl()
    result = impl.validate_output(tool, {"anything": "goes"})
    assert result.is_valid is True


def test_validate_arguments_violation_to_schema_violation() -> None:
    """jsonschema.ValidationError 正确转换为 SchemaViolation(path/expected/message)"""
    tool = _make_tool(
        input_schema={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
    )
    impl = JsonSchemaValidatorImpl()
    result = impl.validate_arguments(tool, {"name": 123})
    assert result.is_valid is False
    violation = result.violations[0]
    assert violation.path == "/name"
    assert "type" in violation.expected
    assert "string" in violation.message or "integer" in violation.message


# ============================================================================
# 2. validate_schema_compatibility - 12 条规则
# ============================================================================


def test_compatibility_required_added_is_breaking() -> None:
    """规则 1: new.required ⊃ old.required → REQUIRED_FIELD_ADDED(BREAKING)"""
    impl = JsonSchemaValidatorImpl()
    old = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}
    new = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a", "b"]}
    result = impl.validate_schema_compatibility(old, new)
    assert not result.is_compatible
    assert any(c.change_type == ChangeType.REQUIRED_FIELD_ADDED for c in result.breaking_changes)


def test_compatibility_required_removed_is_breaking() -> None:
    """规则 2: new.required ⊆ old.required → REQUIRED_FIELD_REMOVED(BREAKING)"""
    impl = JsonSchemaValidatorImpl()
    old = {"type": "object", "required": ["a", "b"]}
    new = {"type": "object", "required": ["a"]}
    result = impl.validate_schema_compatibility(old, new)
    assert not result.is_compatible
    assert any(c.change_type == ChangeType.REQUIRED_FIELD_REMOVED for c in result.breaking_changes)


def test_compatibility_field_removed_is_breaking() -> None:
    """规则 3: 字段完全删除 → REQUIRED_FIELD_REMOVED(BREAKING)"""
    impl = JsonSchemaValidatorImpl()
    old = {"properties": {"a": {"type": "string"}, "b": {"type": "string"}}}
    new = {"properties": {"a": {"type": "string"}}}
    result = impl.validate_schema_compatibility(old, new)
    assert not result.is_compatible
    assert any(c.change_type == ChangeType.REQUIRED_FIELD_REMOVED for c in result.breaking_changes)


def test_compatibility_enum_value_removed_is_breaking() -> None:
    """规则 4: enum 缩小 → ENUM_VALUE_REMOVED(BREAKING)"""
    impl = JsonSchemaValidatorImpl()
    old = {"properties": {"status": {"type": "string", "enum": ["a", "b", "c"]}}}
    new = {"properties": {"status": {"type": "string", "enum": ["a", "b"]}}}
    result = impl.validate_schema_compatibility(old, new)
    assert not result.is_compatible
    assert any(c.change_type == ChangeType.ENUM_VALUE_REMOVED for c in result.breaking_changes)


def test_compatibility_type_changed_is_breaking() -> None:
    """规则 5: 类型完全变更(string → object) → FIELD_TYPE_CHANGED(BREAKING)"""
    impl = JsonSchemaValidatorImpl()
    old = {"properties": {"x": {"type": "string"}}}
    new = {"properties": {"x": {"type": "object"}}}
    result = impl.validate_schema_compatibility(old, new)
    assert not result.is_compatible
    assert any(c.change_type == ChangeType.FIELD_TYPE_CHANGED for c in result.breaking_changes)


def test_compatibility_type_narrowed_is_breaking() -> None:
    """规则 6: 类型收窄(integer → string) → FIELD_TYPE_NARROWED(BREAKING)"""
    impl = JsonSchemaValidatorImpl()
    old = {"properties": {"x": {"type": "integer"}}}
    new = {"properties": {"x": {"type": "string"}}}
    result = impl.validate_schema_compatibility(old, new)
    assert not result.is_compatible
    assert any(c.change_type == ChangeType.FIELD_TYPE_NARROWED for c in result.breaking_changes)


def test_compatibility_additional_properties_restricted_is_breaking() -> None:
    """规则 7: additionalProperties true→false → ADDITIONAL_PROPERTIES_RESTRICTED(BREAKING)"""
    impl = JsonSchemaValidatorImpl()
    old: dict = {"additionalProperties": True}
    new = {"additionalProperties": False}
    result = impl.validate_schema_compatibility(old, new)
    assert not result.is_compatible
    assert any(c.change_type == ChangeType.ADDITIONAL_PROPERTIES_RESTRICTED for c in result.breaking_changes)


def test_compatibility_minimum_increased_is_breaking() -> None:
    """规则 9: minimum 增大 → MIN_VALUE_INCREASED(BREAKING)"""
    impl = JsonSchemaValidatorImpl()
    old = {"properties": {"age": {"type": "integer", "minimum": 0}}}
    new = {"properties": {"age": {"type": "integer", "minimum": 18}}}
    result = impl.validate_schema_compatibility(old, new)
    assert not result.is_compatible
    assert any(c.change_type == ChangeType.MIN_VALUE_INCREASED for c in result.breaking_changes)


def test_compatibility_type_widened_is_non_breaking() -> None:
    """规则 10: 类型放宽(integer → number) → NON_BREAKING FIELD_TYPE_WIDENED"""
    impl = JsonSchemaValidatorImpl()
    old = {"properties": {"x": {"type": "integer"}}}
    new = {"properties": {"x": {"type": "number"}}}
    result = impl.validate_schema_compatibility(old, new)
    assert result.is_compatible is True
    assert any(c.change_type == NonBreakingChangeType.FIELD_TYPE_WIDENED for c in result.non_breaking_changes)


def test_compatibility_optional_field_added_is_non_breaking() -> None:
    """规则 11: 字段新增(非 required) → NON_BREAKING OPTIONAL_FIELD_ADDED"""
    impl = JsonSchemaValidatorImpl()
    old = {"properties": {"a": {"type": "string"}}}
    new = {"properties": {"a": {"type": "string"}, "b": {"type": "string"}}}
    result = impl.validate_schema_compatibility(old, new)
    assert result.is_compatible is True
    assert any(c.change_type == NonBreakingChangeType.OPTIONAL_FIELD_ADDED for c in result.non_breaking_changes)


def test_compatibility_additional_properties_relaxed_is_non_breaking() -> None:
    """规则 12: additionalProperties false→true → NON_BREAKING ADDITIONAL_PROPERTIES_RELAXED"""
    impl = JsonSchemaValidatorImpl()
    old = {"additionalProperties": False}
    new = {"additionalProperties": True}
    result = impl.validate_schema_compatibility(old, new)
    assert result.is_compatible is True
    assert any(c.change_type == NonBreakingChangeType.ADDITIONAL_PROPERTIES_RELAXED for c in result.non_breaking_changes)


def test_compatibility_no_changes_is_compatible() -> None:
    """相同 schema → is_compatible=True + 0 changes"""
    impl = JsonSchemaValidatorImpl()
    schema = {"properties": {"a": {"type": "string"}}, "required": ["a"]}
    result = impl.validate_schema_compatibility(schema, schema)
    assert result.is_compatible is True
    assert len(result.breaking_changes) == 0
    assert len(result.non_breaking_changes) == 0
