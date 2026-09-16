"""基础设施层 JSON Schema 验证器实现模块

实现 JsonSchemaValidatorImpl,委托 jsonschema 库执行完整 Draft 7+ 验证。

设计依据：Story 4.3 AC-2
- 使用 jsonschema ^4.19 Draft7Validator
- iter_errors() 而非 validate() 提供完整错误反馈
- 自实现 validate_schema_compatibility() 12 条规则
"""

from __future__ import annotations

import logging
from typing import Any

from jsonschema import Draft7Validator
from jsonschema import ValidationError as JsonSchemaValidationError

from src.application.ports.schema_validator import (
    BreakingChange,
    ChangeType,
    NonBreakingChange,
    NonBreakingChangeType,
    SchemaCompatibilityResult,
    SchemaValidatorPort,
)
from src.domain.entities.tool import Tool
from src.domain.services.schema_validator import (
    SchemaValidationResult,
    SchemaViolation,
)

logger = logging.getLogger(__name__)


class JsonSchemaValidatorImpl(SchemaValidatorPort):
    """JSON Schema Draft 7+ 验证器实现(委托 jsonschema 库)

    领域层 SchemaValidator 仅实现核心子集(type/required/additionalProperties/enum/items/properties),
    本实现扩展为完整 Draft 7+ 能力(含 $ref / allOf / anyOf / oneOf / format / const 等)。

    关键决策：
    - 使用 iter_errors() 而非 validate(),提供所有违规的完整列表(而非首个错误即抛)
    - validate_schema_compatibility() 自实现 12 条规则,覆盖 8 类破坏性 + 4 类非破坏性变更
    """

    def validate_arguments(
        self,
        tool: Tool,
        arguments: dict[str, Any],
    ) -> SchemaValidationResult:
        """校验入参（完整 Draft 7+ 验证）

        Args:
            tool: 工具实体
            arguments: 待校验入参

        Returns:
            SchemaValidationResult
        """
        return self._validate(tool.input_schema, arguments)

    def validate_output(
        self,
        tool: Tool,
        output: dict[str, Any],
    ) -> SchemaValidationResult:
        """校验出参（完整 Draft 7+ 验证）

        Args:
            tool: 工具实体
            output: 待校验输出

        Returns:
            SchemaValidationResult
        """
        return self._validate(tool.output_schema, output)

    def _validate(
        self,
        schema: dict[str, Any],
        instance: dict[str, Any],
    ) -> SchemaValidationResult:
        """统一校验入口(jsonschema Draft 7+ Draft7Validator)

        Args:
            schema: JSON Schema(可为空 dict,视为通过)
            instance: 待校验数据

        Returns:
            SchemaValidationResult
        """
        # 空 schema 视为通配,直接通过
        if not schema:
            return SchemaValidationResult(is_valid=True)

        validator = Draft7Validator(schema)
        violations = list(validator.iter_errors(instance))
        if not violations:
            return SchemaValidationResult(is_valid=True)

        schema_violations = tuple(self._convert_violations(violations))
        return SchemaValidationResult(
            is_valid=False,
            violations=schema_violations,
        )

    @staticmethod
    def _convert_violations(
        jsonschema_errors: list[JsonSchemaValidationError],
    ) -> list[SchemaViolation]:
        """将 jsonschema ValidationError 列表转换为 SchemaViolation 列表

        路径转换：jsonschema 使用 deque/absolute_path,转为 JSON Pointer (RFC 6901) 字符串。
        消息转换：使用 jsonschema 原生 message 字段(人类可读)。

        Args:
            jsonschema_errors: jsonschema.ValidationError 列表

        Returns:
            SchemaViolation 列表
        """
        violations: list[SchemaViolation] = []
        for err in jsonschema_errors:
            path = JsonSchemaValidatorImpl._format_path(err.absolute_path)
            violations.append(
                SchemaViolation(
                    path=path,
                    expected=str(err.validator),
                    actual=err.instance,
                    message=err.message,
                )
            )
        return violations

    @staticmethod
    def _format_path(absolute_path) -> str:
        """将 jsonschema absolute_path(deque)转为 JSON Pointer (RFC 6901) 字符串

        Args:
            absolute_path: jsonschema 的 deque 路径

        Returns:
            JSON Pointer 字符串(如 "/properties/name/type")
        """
        if not absolute_path:
            return "/"
        parts = [str(p) for p in absolute_path]
        return "/" + "/".join(parts)

    # ===== Schema 兼容性检测（12 条规则） =====

    def validate_schema_compatibility(
        self,
        old_schema: dict[str, Any],
        new_schema: dict[str, Any],
    ) -> SchemaCompatibilityResult:
        """检测新旧 schema 兼容性(12 条规则,8 类破坏性 + 4 类非破坏性)

        Args:
            old_schema: 旧 schema
            new_schema: 新 schema

        Returns:
            SchemaCompatibilityResult
        """
        breaking_changes: list[BreakingChange] = []
        non_breaking_changes: list[NonBreakingChange] = []
        schema_diff: dict[str, Any] = {}

        # 规则 1+2: required 字段变化(REQUIRED_FIELD_ADDED / REQUIRED_FIELD_REMOVED)
        old_required = set(old_schema.get("required", []) or [])
        new_required = set(new_schema.get("required", []) or [])
        added_required = new_required - old_required
        removed_required = old_required - new_required
        for req in added_required:
            breaking_changes.append(
                BreakingChange(
                    change_type=ChangeType.REQUIRED_FIELD_ADDED,
                    path=f"/required/{req}",
                    old_value=None,
                    new_value=req,
                    description=f"Required field '{req}' added",
                    severity="major",
                    remediation="新版本要求旧客户端提供此字段,可能导致旧调用失败",
                )
            )
        for req in removed_required:
            breaking_changes.append(
                BreakingChange(
                    change_type=ChangeType.REQUIRED_FIELD_REMOVED,
                    path=f"/required/{req}",
                    old_value=req,
                    new_value=None,
                    description=f"Required field '{req}' removed",
                    severity="minor",
                    remediation="新版本不再要求此字段,旧调用仍兼容",
                )
            )

        # 规则 3+4+5+6+10+11: properties 字段变化
        old_props = old_schema.get("properties", {}) or {}
        new_props = new_schema.get("properties", {}) or {}
        old_keys, new_keys = set(old_props.keys()), set(new_props.keys())

        # 规则 3: 字段完全删除
        for key in old_keys - new_keys:
            breaking_changes.append(
                BreakingChange(
                    change_type=ChangeType.REQUIRED_FIELD_REMOVED,
                    path=f"/properties/{key}",
                    old_value=old_props[key],
                    new_value=None,
                    description=f"Field '{key}' removed",
                    severity="major",
                )
            )
        # 规则 11: 字段新增(非 required)
        for key in new_keys - old_keys:
            non_breaking_changes.append(
                NonBreakingChange(
                    change_type=NonBreakingChangeType.OPTIONAL_FIELD_ADDED,
                    path=f"/properties/{key}",
                    old_value=None,
                    new_value=new_props[key],
                    description=f"Optional field '{key}' added",
                )
            )
        # 规则 4+5+6+10: 共同字段的 type/enum 变化
        for key in old_keys & new_keys:
            old_sub = old_props[key]
            new_sub = new_props[key]
            old_type = old_sub.get("type") if isinstance(old_sub, dict) else None
            new_type = new_sub.get("type") if isinstance(new_sub, dict) else None
            if old_type != new_type:
                self._classify_type_change(key, old_type, new_type, breaking_changes, non_breaking_changes)
            # 规则 4: enum 缩小
            old_enum = old_sub.get("enum") if isinstance(old_sub, dict) else None
            new_enum = new_sub.get("enum") if isinstance(new_sub, dict) else None
            if old_enum and new_enum:
                removed_values = set(old_enum) - set(new_enum)
                if removed_values:
                    breaking_changes.append(
                        BreakingChange(
                            change_type=ChangeType.ENUM_VALUE_REMOVED,
                            path=f"/properties/{key}/enum",
                            old_value=old_enum,
                            new_value=new_enum,
                            description=f"Enum values removed: {removed_values}",
                            severity="major",
                        )
                    )
                added_values = set(new_enum) - set(old_enum)
                if added_values:
                    non_breaking_changes.append(
                        NonBreakingChange(
                            change_type=NonBreakingChangeType.ENUM_VALUE_ADDED,
                            path=f"/properties/{key}/enum",
                            old_value=old_enum,
                            new_value=new_enum,
                            description=f"Enum values added: {added_values}",
                        )
                    )

        # 规则 7+12: additionalProperties 松紧变化
        old_ap = old_schema.get("additionalProperties", True)
        new_ap = new_schema.get("additionalProperties", True)
        if old_ap is True and new_ap is False:
            breaking_changes.append(
                BreakingChange(
                    change_type=ChangeType.ADDITIONAL_PROPERTIES_RESTRICTED,
                    path="/additionalProperties",
                    old_value=True,
                    new_value=False,
                    description="additionalProperties restricted from true to false",
                    severity="major",
                    remediation="旧实例可能含未声明字段,新 schema 将拒绝",
                )
            )
        elif old_ap is False and new_ap is True:
            non_breaking_changes.append(
                NonBreakingChange(
                    change_type=NonBreakingChangeType.ADDITIONAL_PROPERTIES_RELAXED,
                    path="/additionalProperties",
                    old_value=False,
                    new_value=True,
                    description="additionalProperties relaxed from false to true",
                )
            )

        # 规则 8: 嵌套 schema 收紧(Round 2 P0-3:递归 properties 子字段 type/enum/required/additionalProperties 单独检查)
        # 上面 loop 仅检查顶层 properties 的 type/enum/required,但嵌套层
        # (如 properties.user.properties.email.type 改变)漏报
        # 新增递归检查 + required / enum / additionalProperties 嵌套层检测
        self._check_nested_schema_changes(
            old_props,
            new_props,
            breaking_changes,
            non_breaking_changes,
        )

        # 规则 9: minimum / minLength 增大
        for key in old_keys & new_keys:
            old_sub = old_props[key]
            new_sub = new_props[key]
            if not isinstance(old_sub, dict) or not isinstance(new_sub, dict):
                continue
            for limit_key in ("minimum", "minLength", "minItems"):
                old_val = old_sub.get(limit_key)
                new_val = new_sub.get(limit_key)
                if old_val is not None and new_val is not None and new_val > old_val:
                    breaking_changes.append(
                        BreakingChange(
                            change_type=ChangeType.MIN_VALUE_INCREASED,
                            path=f"/properties/{key}/{limit_key}",
                            old_value=old_val,
                            new_value=new_val,
                            description=f"{limit_key} increased from {old_val} to {new_val}",
                            severity="minor",
                        )
                    )

        # 构建 schema_diff
        schema_diff = {
            "added_required": list(added_required),
            "removed_required": list(removed_required),
            "removed_fields": list(old_keys - new_keys),
            "added_fields": list(new_keys - old_keys),
        }

        is_compatible = len(breaking_changes) == 0
        return SchemaCompatibilityResult(
            is_compatible=is_compatible,
            compatibility_level="BACKWARD",
            breaking_changes=tuple(breaking_changes),
            non_breaking_changes=tuple(non_breaking_changes),
            schema_diff=schema_diff,
        )

    @staticmethod
    def _check_nested_schema_changes(
        old_props: dict[str, Any],
        new_props: dict[str, Any],
        breaking_changes: list[BreakingChange],
        non_breaking_changes: list[NonBreakingChange],
        _path_prefix: str = "/properties",
    ) -> None:
        """Round 2 P0-3:递归检查嵌套 schema 变化

        对嵌套 properties 子字段(type/enum/required/additionalProperties)做兼容性检测,
        避免顶层 loop 只检查 first-level 漏报嵌套层破坏性变更。

        Args:
            old_props: 旧 schema 的 properties dict
            new_props: 新 schema 的 properties dict
            breaking_changes: 累计 breaking_changes(就地修改)
            non_breaking_changes: 累计 non_breaking_changes(就地修改)
            _path_prefix: 当前递归路径前缀(内部参数)
        """
        old_keys = set(old_props.keys())
        new_keys = set(new_props.keys())

        # 递归检查共同 keys 的 type/enum/required 变化
        for key in old_keys & new_keys:
            old_sub = old_props[key]
            new_sub = new_props[key]
            if not isinstance(old_sub, dict) or not isinstance(new_sub, dict):
                continue

            old_type = old_sub.get("type")
            new_type = new_sub.get("type")
            if old_type != new_type:
                # 嵌套层 type 变化 → 调用 _classify_type_change 复用顶层逻辑(break / non_break)
                if old_type is not None and new_type is not None:
                    nested_breaking: list = []
                    nested_non_breaking: list = []
                    JsonSchemaValidatorImpl._classify_type_change(
                        key,
                        old_type,
                        new_type,
                        nested_breaking,
                        nested_non_breaking,
                    )
                    # 将顶层 BreakingChange 转 NESTED_SCHEMA_TIGHTENED 标记(嵌套层语义)
                    for bc in nested_breaking:
                        breaking_changes.append(
                            BreakingChange(
                                change_type=ChangeType.NESTED_SCHEMA_TIGHTENED,
                                path=f"{_path_prefix}/{key}/type",
                                old_value=old_type,
                                new_value=new_type,
                                description=f"嵌套字段 {key} type 收窄:{bc.description}",
                                severity=bc.severity,
                                remediation=bc.remediation,
                            ),
                        )
                    # 非破坏性变更(类型放宽)→ 直接加入 non_breaking_changes
                    for nbc in nested_non_breaking:
                        non_breaking_changes.append(
                            NonBreakingChange(
                                change_type=NonBreakingChangeType.FIELD_TYPE_WIDENED,
                                path=f"{_path_prefix}/{key}/type",
                                old_value=old_type,
                                new_value=new_type,
                                description=f"嵌套字段 {key} type 放宽:{nbc.description}",
                            ),
                        )

            # 嵌套 enum 缩小
            old_enum = old_sub.get("enum")
            new_enum = new_sub.get("enum")
            if old_enum and new_enum:
                removed = set(old_enum) - set(new_enum)
                if removed:
                    breaking_changes.append(
                        BreakingChange(
                            change_type=ChangeType.NESTED_SCHEMA_TIGHTENED,
                            path=f"{_path_prefix}/{key}/enum",
                            old_value=old_enum,
                            new_value=new_enum,
                            description=f"嵌套字段 {key} enum 删除值:{removed}",
                            severity="major",
                        ),
                    )

            # 嵌套 required 增加
            old_req = set(old_sub.get("required", []))
            new_req = set(new_sub.get("required", []))
            if new_req - old_req:
                breaking_changes.append(
                    BreakingChange(
                        change_type=ChangeType.NESTED_SCHEMA_TIGHTENED,
                        path=f"{_path_prefix}/{key}/required",
                        old_value=sorted(old_req),
                        new_value=sorted(new_req),
                        description=f"嵌套字段 {key} 新增 required:{sorted(new_req - old_req)}",
                        severity="major",
                    ),
                )

            # 嵌套 additionalProperties 收紧
            old_ap = old_sub.get("additionalProperties", True)
            new_ap = new_sub.get("additionalProperties", True)
            if old_ap is True and new_ap is False:
                breaking_changes.append(
                    BreakingChange(
                        change_type=ChangeType.NESTED_SCHEMA_TIGHTENED,
                        path=f"{_path_prefix}/{key}/additionalProperties",
                        old_value=True,
                        new_value=False,
                        description=f"嵌套字段 {key} additionalProperties 由 true 收紧到 false",
                        severity="major",
                    ),
                )

            # 递归到嵌套 properties
            nested_old_props = old_sub.get("properties")
            nested_new_props = new_sub.get("properties")
            if isinstance(nested_old_props, dict) and isinstance(nested_new_props, dict):
                JsonSchemaValidatorImpl._check_nested_schema_changes(
                    nested_old_props,
                    nested_new_props,
                    breaking_changes,
                    non_breaking_changes,
                    _path_prefix=f"{_path_prefix}/{key}/properties",
                )

    @staticmethod
    def _classify_type_severity(old_type: str, new_type: str) -> str:
        """分类 type 变化的破坏性程度(breaking / non_breaking)"""
        # 类型完全变更(数字家族外):breaking
        if {old_type, new_type} <= {"integer", "number"}:
            return "non_breaking"  # 数字家族互转:放宽
        return "breaking"

    @staticmethod
    def _classify_type_change(
        key: str,
        old_type: str | None,
        new_type: str | None,
        breaking_changes: list[BreakingChange],
        non_breaking_changes: list[NonBreakingChange],
    ) -> None:
        """分类 type 字段变化(BREAKING / NON_BREAKING)

        规则：
        - 类型完全变更(string → object/array/boolean) → BREAKING FIELD_TYPE_CHANGED
        - 类型收窄(integer → string / number → integer) → BREAKING FIELD_TYPE_NARROWED
        - 类型放宽(integer → number) → NON_BREAKING FIELD_TYPE_WIDENED
        """
        if old_type is None or new_type is None:
            return
        # 类型放宽(integer → number):非破坏性
        if old_type == "integer" and new_type == "number":
            non_breaking_changes.append(
                NonBreakingChange(
                    change_type=NonBreakingChangeType.FIELD_TYPE_WIDENED,
                    path=f"/properties/{key}/type",
                    old_value=old_type,
                    new_value=new_type,
                    description=f"Type widened from {old_type} to {new_type}",
                )
            )
            return
        # 类型收窄(integer → string / number → integer):破坏性
        narrowing_pairs = {
            ("integer", "string"),
            ("number", "integer"),
            ("integer", "boolean"),
        }
        if (old_type, new_type) in narrowing_pairs:
            breaking_changes.append(
                BreakingChange(
                    change_type=ChangeType.FIELD_TYPE_NARROWED,
                    path=f"/properties/{key}/type",
                    old_value=old_type,
                    new_value=new_type,
                    description=f"Type narrowed from {old_type} to {new_type}",
                    severity="major",
                )
            )
            return
        # 类型完全变更(string → object/array/boolean 等)
        breaking_changes.append(
            BreakingChange(
                change_type=ChangeType.FIELD_TYPE_CHANGED,
                path=f"/properties/{key}/type",
                old_value=old_type,
                new_value=new_type,
                description=f"Type changed from {old_type} to {new_type}",
                severity="critical",
            )
        )


__all__ = ["JsonSchemaValidatorImpl"]
