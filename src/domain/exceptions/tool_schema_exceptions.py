"""领域层工具 Schema 验证异常模块

定义工具输入/输出 Schema 验证相关的领域异常（Story 4.3）。
异常是领域契约的一部分，遵循异常编码范围约束。

toolchain 子域（390-399）共 9 个异常：
- EXCEPTION_390 ToolChainCycleDetectedError (Story 4.2)
- EXCEPTION_391 ToolChainDuplicateNodeError (Story 4.2)
- EXCEPTION_392 ToolChainNodeNotFoundError (Story 4.2)
- EXCEPTION_393 ToolChainExecutionFailedError (Story 4.2)
- EXCEPTION_394 ToolChainNotFoundError (Story 4.2)
- EXCEPTION_395 ToolInputSchemaValidationError (Story 4.3,本模块新增)
- EXCEPTION_396 ToolOutputSchemaValidationError (Story 4.3,本模块新增)
- EXCEPTION_397 ToolSchemaCompatibilityError (Story 4.3,本模块新增)
- EXCEPTION_398 ToolSchemaMissingError (Story 4.3,本模块新增)

子域嵌套说明：
- toolchain (390-399) ⊂ external (301-399)，物理上嵌套但语义独立
- 与 tool (380-389) 子域同处理方式：flat CODE_RANGES + 测试 fixture 注册嵌套

HTTP 状态码映射（由 ExceptionHandlers 自动处理）：
- EXCEPTION_395 → 400（入参校验失败）
- EXCEPTION_396 → 422（出参校验失败，语义错误）
- EXCEPTION_397 → 409（兼容性冲突）
- EXCEPTION_398 → 500（Schema 缺失配置错误）
"""

from __future__ import annotations

from src.domain.exceptions.business_exceptions import (
    BusinessException,
    ValidationError,
)
from src.domain.exceptions.system_exceptions import ConfigurationError


class ToolInputSchemaValidationError(ValidationError):
    """工具输入参数违反 Tool.input_schema 契约

    继承自 ValidationError（EXCEPTION_201）→ HTTP 400。
    触发场景：
    - 入参类型不匹配（如期望 string 实际传 number）
    - required 字段缺失
    - 枚举值越界（不在 enum 集合内）
    - 未声明字段（additionalProperties=false 拦截 LLM 漂移字段）
    - 数组 items 类型错误
    - 嵌套对象 properties 不匹配

    Attributes:
        code: 错误码 EXCEPTION_395
        message: 默认消息
    """

    code = "EXCEPTION_395"
    message = "Tool input schema validation error"

    def __init__(
        self,
        message: str | None = None,
        tool_id: str | None = None,
        execution_id: str | None = None,
        tool_call_id: str | None = None,
        violations: list[dict] | None = None,
    ) -> None:
        context: dict = {}
        if tool_id is not None:
            context["tool_id"] = tool_id
        if execution_id is not None:
            context["execution_id"] = execution_id
        if tool_call_id is not None:
            context["tool_call_id"] = tool_call_id
        if violations is not None:
            context["violations"] = violations
        super().__init__(message=message, context=context)


class ToolOutputSchemaValidationError(ValidationError):
    """工具输出结果违反 Tool.output_schema 契约

    继承自 ValidationError（EXCEPTION_201）→ HTTP 422（语义错误）。
    触发场景：LLM 模型漂移（model drift）导致输出不符合契约。

    Round 2 P0-3 修正:Story 4.3 AC-3 当前实现路径下,OUTPUT 校验失败重试耗尽
    抛 ToolResultValidationError (EXCEPTION_389, 含 schema_violations 上下文)。
    EXCEPTION_396 保留作为工具调用边界异常契约(若未来工具直接抛出或
    OUTPUT 校验在更细粒度失败时使用),当前 Story 4.3 dev 阶段未直接 raise。

    Attributes:
        code: 错误码 EXCEPTION_396
        message: 默认消息
    """

    code = "EXCEPTION_396"
    message = "Tool output schema validation error"

    def __init__(
        self,
        message: str | None = None,
        tool_id: str | None = None,
        execution_id: str | None = None,
        retry_attempt: int | None = None,
        violations: list[dict] | None = None,
    ) -> None:
        context: dict = {}
        if tool_id is not None:
            context["tool_id"] = tool_id
        if execution_id is not None:
            context["execution_id"] = execution_id
        if retry_attempt is not None:
            context["retry_attempt"] = retry_attempt
        if violations is not None:
            context["violations"] = violations
        super().__init__(message=message, context=context)


class ToolSchemaCompatibilityError(BusinessException):
    """Tool.output_schema 版本演进后与旧 execution 不兼容

    父类 BusinessException → HTTP 409（资源冲突，版本不兼容）。
    触发场景：
    - Tool.output_schema 变更（版本号升级）后,旧 in-flight execution 结果与新 schema 不兼容
    - 用于 Story 4.6 灰度发布拦截破坏性发布

    Attributes:
        code: 错误码 EXCEPTION_397
        message: 默认消息
    """

    code = "EXCEPTION_397"
    message = "Tool schema compatibility error"

    def __init__(
        self,
        message: str | None = None,
        tool_id: str | None = None,
        old_version: str | None = None,
        new_version: str | None = None,
        breaking_changes: list[dict] | None = None,
    ) -> None:
        context: dict = {}
        if tool_id is not None:
            context["tool_id"] = tool_id
        if old_version is not None:
            context["old_version"] = old_version
        if new_version is not None:
            context["new_version"] = new_version
        if breaking_changes is not None:
            context["breaking_changes"] = breaking_changes
        super().__init__(message=message, context=context)


class ToolSchemaMissingError(ConfigurationError):
    """Tool 缺失 input_schema / output_schema 且无 default_schema fallback

    继承自 ConfigurationError（EXCEPTION_101）→ HTTP 500（系统配置错误）。
    触发场景：工具注册时未声明 schema 且无系统级默认值,
    SchemaValidator 无法执行校验时抛出。

    Attributes:
        code: 错误码 EXCEPTION_398
        message: 默认消息
    """

    code = "EXCEPTION_398"
    message = "Tool schema missing error"

    def __init__(
        self,
        message: str | None = None,
        tool_id: str | None = None,
        missing_schema_type: str | None = None,
    ) -> None:
        context: dict = {}
        if tool_id is not None:
            context["tool_id"] = tool_id
        if missing_schema_type is not None:
            context["missing_schema_type"] = missing_schema_type
        super().__init__(message=message, context=context)


__all__ = [
    "ToolInputSchemaValidationError",
    "ToolOutputSchemaValidationError",
    "ToolSchemaCompatibilityError",
    "ToolSchemaMissingError",
]
