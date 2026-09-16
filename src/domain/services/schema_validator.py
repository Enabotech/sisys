"""领域层 JSON Schema 验证器模块

定义 SchemaValidator(领域层纯函数服务,无状态、无外部依赖),
实现 JSON Schema 核心子集校验。

设计依据：Story 4.3 AC-1
- 6 项校验规则：type / required / additionalProperties / enum / items / properties
- 空 schema 向后兼容 4.1a 既有 Tool(input_schema={} → is_valid=True)
- 嵌套对象递归校验
- SchemaViolation 序列化脱敏(datetime/UUID/Decimal/bytes/嵌套 dict/NaN/Inf)

不实现（留给应用层端口的可选 jsonschema 库实现扩展）：
- $ref / allOf / anyOf / oneOf / format / const

算法复杂度：O(N)（N = 数据节点数,递归遍历）
业界参考：JSON Schema Draft 7 核心子集 + Instructor Pydantic extra="forbid"
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from src.domain.entities.tool import Tool
from src.domain.exceptions import EntityValidationError

# Round 2 P0-2:PII 敏感字段名黑名单(脱敏)
# 对标 OWASP Top 10 + GDPR 个人信息 + 业界通用敏感字段命名
_SENSITIVE_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "secret",
        "api_key",
        "apikey",
        "api-key",
        "token",
        "access_token",
        "refresh_token",
        "bearer_token",
        "authorization",
        "auth",
        "private_key",
        "privatekey",
        "credential",
        "credentials",
        "ssn",
        "social_security_number",
        "credit_card",
        "creditcard",
        "credit_card_number",
        "cvv",
        "pin",
    }
)


class JsonType(str, Enum):
    """JSON Schema 7 个基础类型（与 Draft 7 type keyword 对齐）"""

    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    NULL = "null"


@dataclass(frozen=True)
class SchemaViolation:
    """Schema 验证违规值对象（不可变,供下游重试/调试消费）

    Attributes:
        path: JSON Pointer (RFC 6901),如 "/items/2/name"。
        expected: 期望类型或值,如 "string"。
        actual: 实际值（已脱敏,datetime/UUID/Decimal/bytes/NaN/Inf 已安全化）。
        message: 人类可读错误描述。
    """

    path: str
    expected: str
    actual: Any
    message: str

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict（前置脱敏,避免 PostgreSQL JSONB 写入失败）

        Returns:
            包含 path/expected/actual/message 四字段的字典
        """
        return {
            "path": self.path,
            "expected": self.expected,
            "actual": SchemaViolation._sanitize_actual(self.actual),
            "message": self.message,
        }

    @staticmethod
    def _sanitize_actual(value: Any) -> Any:
        """脱敏不可 JSON 序列化的值（NaN/Inf/datetime/UUID/Decimal/bytes/嵌套）

        处理规则：
        - NaN / Inf → None(JSON 标准不支持）
        - datetime / date → ISO 字符串
        - UUID → str
        - Decimal → str
        - bytes → hex 字符串
        - 嵌套 dict / list → 递归处理
        - set / frozenset → list(Round 2 P0-2:补漏,避免 JSON 序列化失败)
        - PII 敏感字段值(密码/token/api_key 等) → "***REDACTED***"
          (Round 2 P0-2:防止 LLM 输出含凭证字段直接落地 PG JSONB)
        - 其他类型 → 保持原样

        Args:
            value: 待脱敏的实际值

        Returns:
            JSON 安全的值
        """
        # NaN/Inf 兜底为 None（JSON 标准不支持）
        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                return None
            return value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, uuid.UUID):
            return str(value)
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, bytes):
            return value.hex()
        # Round 2 P0-2:补 set / frozenset 处理(原 list/tuple 不会命中)
        if isinstance(value, (set, frozenset)):
            return [SchemaViolation._sanitize_actual(item) for item in value]
        if isinstance(value, dict):
            return {
                # 敏感字段值直接脱敏(不递归查看内容)
                k: ("***REDACTED***" if k.lower() in _SENSITIVE_FIELD_NAMES else SchemaViolation._sanitize_actual(v))
                for k, v in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [SchemaViolation._sanitize_actual(item) for item in value]
        if isinstance(value, Enum):
            return value.value
        return value


@dataclass(frozen=True)
class SchemaValidationResult:
    """Schema 验证结果值对象（不可变）

    Attributes:
        is_valid: 校验是否通过
        violations: 违规列表(空 tuple 表示通过)
        validated_at: 校验时间戳
    """

    is_valid: bool
    violations: tuple[SchemaViolation, ...] = ()
    validated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict（含 validated_at ISO 字符串）"""
        return {
            "is_valid": self.is_valid,
            "violations": [v.to_dict() for v in self.violations],
            "validated_at": self.validated_at.isoformat(),
        }


class SchemaValidator:
    """JSON Schema 核心子集校验器(领域层纯函数服务,**无状态、无依赖**)

    实现 6 项校验规则(type / required / additionalProperties / enum / items / properties),
    完整 Draft 7+ 验证能力委托 SchemaValidatorPort(应用层)。

    使用 Python 标准库实现,领域层零外部依赖。
    默认对所有 properties 子 schema 注入 additionalProperties=false
    (P0 风险防御 — 防 LLM 模型漂移注入未声明字段,Anthropic/GPT-4 实测 2-8% 概率)。
    """

    @staticmethod
    def validate_arguments(tool: Tool, arguments: dict) -> SchemaValidationResult:
        """校验 Tool 输入参数(arguments)是否符合 Tool.input_schema 契约

        Args:
            tool: 工具实体
            arguments: 待校验的入参字典

        Returns:
            SchemaValidationResult（is_valid/violations/validated_at）
        """
        if not isinstance(arguments, dict):
            raise EntityValidationError(
                message="arguments must be a dict",
                context={"field": "arguments", "type": type(arguments).__name__},
            )
        return SchemaValidator._validate(tool.input_schema, arguments, schema_owner=tool)

    @staticmethod
    def validate_output(tool: Tool, output: dict) -> SchemaValidationResult:
        """校验 Tool 输出(output)是否符合 Tool.output_schema 契约

        Args:
            tool: 工具实体
            output: 待校验的输出字典

        Returns:
            SchemaValidationResult
        """
        if not isinstance(output, dict):
            raise EntityValidationError(
                message="output must be a dict",
                context={"field": "output", "type": type(output).__name__},
            )
        return SchemaValidator._validate(tool.output_schema, output, schema_owner=tool)

    @staticmethod
    def _validate(
        schema: dict,
        instance: dict,
        schema_owner: Tool | None = None,
    ) -> SchemaValidationResult:
        """统一校验入口(空 schema 视为通过,向后兼容 4.1a)

        Args:
            schema: JSON Schema dict(可为空 dict,视为通配)
            instance: 待校验的数据实例

        Returns:
            SchemaValidationResult
        """
        # 空 schema → 视为通配,直接通过(向后兼容 4.1a 既有 Tool)
        if not schema:
            return SchemaValidationResult(is_valid=True)

        violations: list[SchemaViolation] = []
        # Round 2 P1-3:递归深度防御 + 循环引用检测,防止 LLM 模型漂移输出
        # 5000 层嵌套 dict 导致 RecursionError
        seen_ids: set[int] = set()
        SchemaValidator._validate_node(
            schema,
            instance,
            path="",
            violations=violations,
            _depth=0,
            _seen_ids=seen_ids,
        )

        return SchemaValidationResult(
            is_valid=len(violations) == 0,
            violations=tuple(violations),
        )

    # Round 2 P1-3:递归深度上限(Python 默认 1000,业务上限 32 防御 LLM 模型漂移)
    _MAX_RECURSION_DEPTH = 32

    @staticmethod
    def _validate_node(
        schema: dict,
        instance: Any,
        path: str,
        violations: list[SchemaViolation],
        *,
        _depth: int = 0,
        _seen_ids: set[int] | None = None,
    ) -> None:
        """递归校验单个节点(type/required/additionalProperties/enum/items/properties)

        Args:
            schema: 当前节点的 JSON Schema
            instance: 当前节点的数据实例
            path: 当前节点的 JSON Pointer
            violations: 违规列表(就地修改)
            _depth: 当前递归深度(内部参数,Round 2 P1-3 防御)
            _seen_ids: 已访问对象 id 集合(内部参数,循环引用检测)
        """
        # Round 2 P1-3:递归深度限制 + 循环引用检测
        if _seen_ids is None:
            _seen_ids = set()
        instance_id = id(instance)
        if instance_id in _seen_ids:
            violations.append(
                SchemaViolation(
                    path=path or "/",
                    expected="non-cyclic object",
                    actual="<circular reference>",
                    message=f"检测到循环引用:{path} 节点已被访问过,疑似恶意 schema",
                ),
            )
            return
        _seen_ids = _seen_ids | {instance_id}  # 不可变集合避免污染调用方

        if _depth > SchemaValidator._MAX_RECURSION_DEPTH:
            violations.append(
                SchemaViolation(
                    path=path or "/",
                    expected=f"depth <= {SchemaValidator._MAX_RECURSION_DEPTH}",
                    actual=f"depth={_depth}",
                    message=f"嵌套深度超过 {SchemaValidator._MAX_RECURSION_DEPTH},疑似恶意 schema 或 LLM 模型漂移",
                ),
            )
            return
        # 规则 1: type 校验
        expected_type = schema.get("type")
        if expected_type is not None:
            if not SchemaValidator._check_type(instance, expected_type):
                violations.append(
                    SchemaViolation(
                        path=path or "/",
                        expected=str(expected_type),
                        actual=instance,
                        message=f"Expected type '{expected_type}', got '{type(instance).__name__}'",
                    )
                )
                return  # 类型失败则不再深入校验

        # 规则 2-4 + 6: 仅对 object 类型有意义
        if isinstance(instance, dict):
            properties = schema.get("properties", {})
            # 默认对所有 properties 子 schema 注入 additionalProperties=false(防 LLM 模型漂移)
            effective_additional = schema.get("additionalProperties", False)
            if effective_additional is False:
                for key in instance:
                    if key not in properties:
                        violations.append(
                            SchemaViolation(
                                path=f"{path}/{key}" if path else f"/{key}",
                                expected="declared property",
                                actual=key,
                                message=f"Additional property '{key}' is not allowed (additionalProperties=false)",
                            )
                        )

            # 规则 2: required 字段缺失
            required = schema.get("required", [])
            for req_key in required:
                if req_key not in instance:
                    violations.append(
                        SchemaViolation(
                            path=f"{path}/{req_key}" if path else f"/{req_key}",
                            expected="required property",
                            actual=None,
                            message=f"Required property '{req_key}' is missing",
                        )
                    )

            # 规则 6: 嵌套对象 properties 递归
            for prop_key, prop_schema in properties.items():
                if prop_key in instance:
                    SchemaValidator._validate_node(
                        schema=prop_schema,
                        instance=instance[prop_key],
                        path=f"{path}/{prop_key}" if path else f"/{prop_key}",
                        violations=violations,
                        _depth=_depth + 1,
                        _seen_ids=_seen_ids,
                    )

        # 规则 4: enum 校验
        if "enum" in schema:
            allowed = schema["enum"]
            if instance not in allowed:
                violations.append(
                    SchemaViolation(
                        path=path or "/",
                        expected=f"one of {allowed}",
                        actual=instance,
                        message=f"Value '{instance}' is not in enum {allowed}",
                    )
                )

        # 规则 5: 数组 items 类型约束
        if isinstance(instance, list) and "items" in schema:
            items_schema = schema["items"]
            for idx, item in enumerate(instance):
                SchemaValidator._validate_node(
                    schema=items_schema,
                    instance=item,
                    path=f"{path}/{idx}" if path else f"/{idx}",
                    violations=violations,
                    _depth=_depth + 1,
                    _seen_ids=_seen_ids,
                )

    @staticmethod
    def _check_type(instance: Any, expected_type: str | list[str]) -> bool:
        """检查实例是否符合 JSON Schema type 关键字

        Args:
            instance: 待校验实例
            expected_type: 期望类型(str 或 list[str],Draft 7 支持类型并集)

        Returns:
            类型匹配返回 True
        """
        types = [expected_type] if isinstance(expected_type, str) else expected_type
        for t in types:
            if SchemaValidator._matches_single_type(instance, t):
                return True
        return False

    @staticmethod
    def _matches_single_type(instance: Any, json_type: str) -> bool:
        """检查实例是否符合单个 JSON Schema 类型

        Args:
            instance: 待校验实例
            json_type: 单一类型字符串

        Returns:
            类型匹配返回 True
        """
        if json_type == "null":
            return instance is None
        if json_type == "boolean":
            return isinstance(instance, bool)
        if json_type == "string":
            return isinstance(instance, str)
        if json_type == "integer":
            # JSON Schema:integer 必须排除 bool(Python bool 是 int 子类)
            return isinstance(instance, int) and not isinstance(instance, bool)
        if json_type == "number":
            return isinstance(instance, (int, float)) and not isinstance(instance, bool)
        if json_type == "array":
            return isinstance(instance, list)
        if json_type == "object":
            return isinstance(instance, dict)
        return True


__all__ = [
    "SchemaValidator",
    "SchemaValidationResult",
    "SchemaViolation",
    "JsonType",
]
