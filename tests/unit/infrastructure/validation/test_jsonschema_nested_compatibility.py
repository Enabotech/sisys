"""嵌套 schema 兼容性测试(Round 2 P0-3 修复守护)

覆盖范围:
1. _check_nested_schema_changes 递归检测嵌套 properties 子字段
2. 嵌套层 type 收窄(string→integer)→ NESTED_SCHEMA_TIGHTENED
3. 嵌套层 type 放宽(integer→number)→ 非破坏性
4. 嵌套层 enum 缩小 → NESTED_SCHEMA_TIGHTENED
5. 嵌套层 required 新增 → NESTED_SCHEMA_TIGHTENED
6. 嵌套层 additionalProperties true→false → NESTED_SCHEMA_TIGHTENED
7. 3 层以上嵌套递归终止
"""

from __future__ import annotations

import pytest

from src.application.ports.schema_validator import (
    ChangeType,
)
from src.infrastructure.validation.jsonschema_validator import (
    JsonSchemaValidatorImpl,
)


@pytest.fixture
def validator() -> JsonSchemaValidatorImpl:
    return JsonSchemaValidatorImpl()


class TestNestedSchemaCompatibility:
    """Round 2 P0-3:_check_nested_schema_changes 递归检测嵌套 schema 变化"""

    def test_nested_type_narrowing_string_to_integer_is_breaking(
        self,
        validator: JsonSchemaValidatorImpl,
    ) -> None:
        """嵌套层 type 收窄:string→integer → 破坏性"""
        old = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {"age": {"type": "string"}},
                },
            },
        }
        new = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {"age": {"type": "integer"}},
                },
            },
        }
        result = validator.validate_schema_compatibility(old, new)

        # 嵌套 type 收窄(string→integer)是破坏性
        nested_changes = [bc for bc in result.breaking_changes if bc.change_type == ChangeType.NESTED_SCHEMA_TIGHTENED]
        assert any("/properties/user/properties/age/type" in bc.path for bc in nested_changes)

    def test_nested_type_widening_integer_to_number_is_non_breaking(
        self,
        validator: JsonSchemaValidatorImpl,
    ) -> None:
        """嵌套层 type 放宽:integer→number → 非破坏性(数字家族)"""
        old = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {"age": {"type": "integer"}},
                },
            },
        }
        new = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {"age": {"type": "number"}},
                },
            },
        }
        result = validator.validate_schema_compatibility(old, new)

        # 嵌套 type 放宽(integer→number)是非破坏性
        assert not any(
            bc.change_type == ChangeType.NESTED_SCHEMA_TIGHTENED and "/properties/user/properties/age/type" in bc.path
            for bc in result.breaking_changes
        )
        # 应该出现在 non_breaking_changes 中
        assert any("/properties/user/properties/age/type" in nbc.path for nbc in result.non_breaking_changes)

    def test_nested_enum_shrinking_is_breaking(
        self,
        validator: JsonSchemaValidatorImpl,
    ) -> None:
        """嵌套层 enum 缩小 → NESTED_SCHEMA_TIGHTENED"""
        old = {
            "type": "object",
            "properties": {
                "config": {
                    "type": "object",
                    "properties": {
                        "mode": {"enum": ["read", "write", "admin"]},
                    },
                },
            },
        }
        new = {
            "type": "object",
            "properties": {
                "config": {
                    "type": "object",
                    "properties": {
                        "mode": {"enum": ["read", "write"]},  # 删除 "admin"
                    },
                },
            },
        }
        result = validator.validate_schema_compatibility(old, new)

        nested_changes = [bc for bc in result.breaking_changes if bc.change_type == ChangeType.NESTED_SCHEMA_TIGHTENED]
        assert any("/properties/config/properties/mode/enum" in bc.path for bc in nested_changes)

    def test_nested_required_added_is_breaking(
        self,
        validator: JsonSchemaValidatorImpl,
    ) -> None:
        """嵌套层 required 新增 → NESTED_SCHEMA_TIGHTENED"""
        old = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            },
        }
        new = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "email": {"type": "string"},
                    },
                    "required": ["name", "email"],  # 新增 required
                },
            },
        }
        result = validator.validate_schema_compatibility(old, new)

        nested_changes = [bc for bc in result.breaking_changes if bc.change_type == ChangeType.NESTED_SCHEMA_TIGHTENED]
        assert any(
            "/properties/user/properties/email" in bc.path or "/properties/user/required" in bc.path for bc in nested_changes
        )

    def test_nested_additional_properties_restricted_is_breaking(
        self,
        validator: JsonSchemaValidatorImpl,
    ) -> None:
        """嵌套层 additionalProperties true→false → NESTED_SCHEMA_TIGHTENED"""
        old = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "additionalProperties": True,
                },
            },
        }
        new = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "additionalProperties": False,
                },
            },
        }
        result = validator.validate_schema_compatibility(old, new)

        nested_changes = [bc for bc in result.breaking_changes if bc.change_type == ChangeType.NESTED_SCHEMA_TIGHTENED]
        assert any("/properties/user/additionalProperties" in bc.path for bc in nested_changes)

    def test_three_level_deep_nested_type_change_detected(
        self,
        validator: JsonSchemaValidatorImpl,
    ) -> None:
        """3 层嵌套 properties 子字段 type 变化也能被检测到"""
        old = {
            "type": "object",
            "properties": {
                "level1": {
                    "type": "object",
                    "properties": {
                        "level2": {
                            "type": "object",
                            "properties": {
                                "level3_field": {"type": "string"},
                            },
                        },
                    },
                },
            },
        }
        new = {
            "type": "object",
            "properties": {
                "level1": {
                    "type": "object",
                    "properties": {
                        "level2": {
                            "type": "object",
                            "properties": {
                                "level3_field": {"type": "integer"},  # string→integer
                            },
                        },
                    },
                },
            },
        }
        result = validator.validate_schema_compatibility(old, new)

        # 3 层嵌套的 type 收窄应被检测
        nested_changes = [bc for bc in result.breaking_changes if bc.change_type == ChangeType.NESTED_SCHEMA_TIGHTENED]
        assert any("/properties/level1/properties/level2/properties/level3_field/type" in bc.path for bc in nested_changes)

    def test_nested_no_change_returns_compatible(
        self,
        validator: JsonSchemaValidatorImpl,
    ) -> None:
        """嵌套 schema 无变化 → 完全兼容"""
        old = new = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            },
        }
        result = validator.validate_schema_compatibility(old, new)

        assert result.is_compatible is True
        assert len(result.breaking_changes) == 0
