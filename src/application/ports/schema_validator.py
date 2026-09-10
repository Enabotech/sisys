"""应用层 Schema 验证端口模块

定义 SchemaValidatorPort 协议（应用层契约），
委托 jsonschema 库实现完整 JSON Schema Draft 7+ 验证。

设计依据：Story 4.3 AC-2
- 3 方法协议：validate_arguments / validate_output / validate_schema_compatibility
- 与领域层 SchemaValidator(核心子集)互补,扩展全 Draft 7+ 能力
- 通过 jsonschema 库 + 自定义 compatibility 检测实现
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Protocol, runtime_checkable

from src.domain.entities.tool import Tool
from src.domain.services.schema_validator import SchemaValidationResult


class ChangeType(str, Enum):
    """破坏性变更类型(强类型,便于 4.6 灰度策略匹配)"""

    REQUIRED_FIELD_ADDED = "required_field_added"
    REQUIRED_FIELD_REMOVED = "required_field_removed"
    FIELD_TYPE_NARROWED = "field_type_narrowed"
    FIELD_TYPE_CHANGED = "field_type_changed"
    ENUM_VALUE_REMOVED = "enum_value_removed"
    ADDITIONAL_PROPERTIES_RESTRICTED = "additional_props_restricted"
    NESTED_SCHEMA_TIGHTENED = "nested_schema_tightened"
    MIN_VALUE_INCREASED = "min_value_increased"


class NonBreakingChangeType(str, Enum):
    """非破坏性变更类型"""

    OPTIONAL_FIELD_ADDED = "optional_field_added"
    FIELD_TYPE_WIDENED = "field_type_widened"
    ENUM_VALUE_ADDED = "enum_value_added"
    ADDITIONAL_PROPERTIES_RELAXED = "additional_props_relaxed"
    DEFAULT_ADDED = "default_added"
    DESCRIPTION_UPDATED = "description_updated"
    PATTERN_RELAXED = "pattern_relaxed"


@dataclass(frozen=True)
class BreakingChange:
    """破坏性变更值对象

    Attributes:
        change_type: 变更类型枚举值
        path: JSON Pointer (RFC 6901),如 "/properties/name/type"
        old_value: 旧 schema 该位置的值
        new_value: 新 schema 该位置的值
        description: 人类可读描述
        severity: 严重程度(critical/major/minor),供 4.6 灰度策略分级
        remediation: 修复建议
    """

    change_type: ChangeType
    path: str
    old_value: Any | None
    new_value: Any | None
    description: str
    severity: Literal["critical", "major", "minor"] = "major"
    remediation: str | None = None


@dataclass(frozen=True)
class NonBreakingChange:
    """非破坏性变更值对象

    Attributes:
        change_type: 变更类型枚举值
        path: JSON Pointer
        old_value: 旧 schema 该位置的值
        new_value: 新 schema 该位置的值
        description: 人类可读描述
    """

    change_type: NonBreakingChangeType
    path: str
    old_value: Any | None
    new_value: Any | None
    description: str


@dataclass(frozen=True)
class SchemaCompatibilityResult:
    """Schema 兼容性检测结果值对象(对标 Avro SchemaValidatorResult)

    Attributes:
        is_compatible: 是否完全兼容
        compatibility_level: 兼容性级别(BACKWARD/FULL,对标 Avro 4 类)
        breaking_changes: 破坏性变更列表
        non_breaking_changes: 非破坏性变更列表
        schema_diff: 完整 diff 摘要(供 UI 渲染)
    """

    is_compatible: bool
    compatibility_level: Literal["BACKWARD", "FULL"] = "BACKWARD"
    breaking_changes: tuple[BreakingChange, ...] = ()
    non_breaking_changes: tuple[NonBreakingChange, ...] = ()
    schema_diff: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class SchemaValidatorPort(Protocol):
    """Schema 验证端口协议（应用层）

    委托 jsonschema 库实现完整 JSON Schema Draft 7+ 验证；
    领域层 SchemaValidator(AC-1)仅实现核心子集,本端口扩展全功能。
    """

    def validate_arguments(
        self,
        tool: Tool,
        arguments: dict[str, Any],
    ) -> SchemaValidationResult:
        """校验 Tool 输入参数是否符合 Tool.input_schema 契约(完整 Draft 7+ 验证)

        Args:
            tool: 工具实体
            arguments: 待校验的入参字典

        Returns:
            SchemaValidationResult(is_valid + violations + validated_at)
        """
        ...

    def validate_output(
        self,
        tool: Tool,
        output: dict[str, Any],
    ) -> SchemaValidationResult:
        """校验 Tool 输出是否符合 Tool.output_schema 契约(完整 Draft 7+ 验证)

        Args:
            tool: 工具实体
            output: 待校验的输出字典

        Returns:
            SchemaValidationResult
        """
        ...

    def validate_schema_compatibility(
        self,
        old_schema: dict,
        new_schema: dict,
    ) -> SchemaCompatibilityResult:
        """检测新旧 schema 兼容性(12 条规则)

        规则清单：
        - BREAKING:
          1. new.required ⊃ old.required (REQUIRED_FIELD_ADDED)
          2. new.required ⊆ old.required (REQUIRED_FIELD_REMOVED)
          3. 字段完全删除 (REQUIRED_FIELD_REMOVED)
          4. enum 缩小 (ENUM_VALUE_REMOVED)
          5. 类型完全变更 string→object/array/boolean (FIELD_TYPE_CHANGED)
          6. 类型收窄 integer→string/number→integer (FIELD_TYPE_NARROWED)
          7. additionalProperties: true→false (ADDITIONAL_PROPERTIES_RESTRICTED)
          8. 嵌套 schema 收紧 (NESTED_SCHEMA_TIGHTENED)
          9. minimum/minLength 增大 (MIN_VALUE_INCREASED)
        - NON_BREAKING:
          10. 类型放宽 integer→number (FIELD_TYPE_WIDENED)
          11. 字段新增(非 required) (OPTIONAL_FIELD_ADDED)
          12. additionalProperties: false→true (ADDITIONAL_PROPERTIES_RELAXED)

        Args:
            old_schema: 旧 schema
            new_schema: 新 schema

        Returns:
            SchemaCompatibilityResult(is_compatible + breaking_changes + non_breaking_changes)
        """
        ...


__all__ = [
    "SchemaValidatorPort",
    "SchemaCompatibilityResult",
    "BreakingChange",
    "NonBreakingChange",
    "ChangeType",
    "NonBreakingChangeType",
]
