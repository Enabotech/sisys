"""领域层工具异常模块

定义工具相关领域异常：ToolNotFoundError、ToolAlreadyExistsError，
以及 Story 4.1a 工具执行/技能加载相关的 7 个新异常。
异常是领域契约的一部分，遵循异常编码范围约束。

tool 子域（380-389）共 9 个异常：
- EXCEPTION_380 ToolNotFoundError (Story 4.1)
- EXCEPTION_381 ToolAlreadyExistsError (Story 4.1)
- EXCEPTION_382 ToolExecutionFailedError (Story 4.1a)
- EXCEPTION_383 ToolExecutionRetryExhaustedError (Story 4.1a)
- EXCEPTION_384 保留未占用
- EXCEPTION_385 ToolExecutionTimeoutError (Story 4.1a)
- EXCEPTION_386 EvidenceValidationFailedError (Story 4.1a)
- EXCEPTION_387 SkillNotFoundError (Story 4.1a)
- EXCEPTION_388 SkillLoadError (Story 4.1a)
- EXCEPTION_389 ToolResultValidationError (Story 4.1a)
"""

from __future__ import annotations

from src.domain.exceptions.business_exceptions import (
    BusinessException,
    ConflictError,
    NotFoundError,
    ValidationError,
)


class ToolNotFoundError(NotFoundError):
    """按 ID/名称/slug 查询工具不存在

    继承自 NotFoundError（EXCEPTION_202），保持 HTTP 404 映射。
    通过 code 属性覆写为 EXCEPTION_380 以纳入 tool 子域（380-389）。

    Attributes:
        code: 错误码 EXCEPTION_380
        message: 默认消息
    """

    code = "EXCEPTION_380"
    message = "Tool not found"

    def __init__(
        self,
        message: str | None = None,
        tool_id: str | None = None,
        tool_name: str | None = None,
        slug: str | None = None,
    ) -> None:
        context: dict = {}
        if tool_id is not None:
            context["tool_id"] = tool_id
        if tool_name is not None:
            context["tool_name"] = tool_name
        if slug is not None:
            context["slug"] = slug
        super().__init__(message=message, context=context)


class ToolAlreadyExistsError(ConflictError):
    """注册已存在的工具（同 ID 或同名）

    Attributes:
        code: 错误码 EXCEPTION_381
        message: 默认消息
    """

    code = "EXCEPTION_381"
    message = "Tool already exists"

    def __init__(
        self,
        message: str | None = None,
        tool_id: str | None = None,
        tool_name: str | None = None,
    ) -> None:
        context: dict = {}
        if tool_id is not None:
            context["tool_id"] = tool_id
        if tool_name is not None:
            context["tool_name"] = tool_name
        super().__init__(message=message, context=context)


class ToolExecutionFailedError(BusinessException):
    """工具执行引擎五阶段任一阶段失败（不可重试）

    父类 BusinessException → HTTP 500。

    Attributes:
        code: 错误码 EXCEPTION_382
        message: 默认消息
    """

    code = "EXCEPTION_382"
    message = "Tool execution failed"

    def __init__(
        self,
        message: str | None = None,
        execution_id: str | None = None,
        tool_id: str | None = None,
        stage: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        context: dict = {}
        if execution_id is not None:
            context["execution_id"] = execution_id
        if tool_id is not None:
            context["tool_id"] = tool_id
        if stage is not None:
            context["stage"] = stage
        super().__init__(message=message, cause=cause, context=context)


class ToolExecutionRetryExhaustedError(BusinessException):
    """工具执行重试耗尽（重试 3 次后仍失败）

    父类 BusinessException → HTTP 502（网关错误，重试耗尽后端不可用）。

    Attributes:
        code: 错误码 EXCEPTION_383
        message: 默认消息
    """

    code = "EXCEPTION_383"
    message = "Tool execution retry exhausted"

    def __init__(
        self,
        message: str | None = None,
        execution_id: str | None = None,
        tool_id: str | None = None,
        retry_count: int | None = None,
        cause: Exception | None = None,
    ) -> None:
        context: dict = {}
        if execution_id is not None:
            context["execution_id"] = execution_id
        if tool_id is not None:
            context["tool_id"] = tool_id
        if retry_count is not None:
            context["retry_count"] = retry_count
        super().__init__(message=message, cause=cause, context=context)


class ToolExecutionTimeoutError(BusinessException):
    """工具执行超过 max_total_duration_sec 总时长限制

    父类 BusinessException → HTTP 504（由 ExceptionHandlers 映射，
    工具执行超时视为网关超时，区分于业务级 500 错误）。

    Attributes:
        code: 错误码 EXCEPTION_385
        message: 默认消息
    """

    code = "EXCEPTION_385"
    message = "Tool execution timeout"

    def __init__(
        self,
        message: str | None = None,
        execution_id: str | None = None,
        tool_id: str | None = None,
        elapsed_sec: float | None = None,
    ) -> None:
        context: dict = {}
        if execution_id is not None:
            context["execution_id"] = execution_id
        if tool_id is not None:
            context["tool_id"] = tool_id
        if elapsed_sec is not None:
            context["elapsed_sec"] = elapsed_sec
        super().__init__(message=message, context=context)


class EvidenceValidationFailedError(ValidationError):
    """EvidencePackage 完整性校验失败

    继承自 ValidationError（EXCEPTION_201）→ HTTP 400。
    EvidencePackage 9 字段（input_hash/rule_version/plan/code/result/observation/
    validation/confidence/citations）任一必填字段缺失或非法时抛出。

    Attributes:
        code: 错误码 EXCEPTION_386
        message: 默认消息
    """

    code = "EXCEPTION_386"
    message = "Evidence package validation failed"

    def __init__(
        self,
        message: str | None = None,
        execution_id: str | None = None,
        missing_fields: list[str] | None = None,
    ) -> None:
        context: dict = {}
        if execution_id is not None:
            context["execution_id"] = execution_id
        if missing_fields is not None:
            context["missing_fields"] = missing_fields
        super().__init__(message=message, context=context)


class SkillNotFoundError(NotFoundError):
    """通过 tool_name 查不到对应 SKILL.md（skill_manifest.py 缺失映射）

    继承自 NotFoundError（EXCEPTION_202）→ HTTP 404。

    Attributes:
        code: 错误码 EXCEPTION_387
        message: 默认消息
    """

    code = "EXCEPTION_387"
    message = "Skill not found"

    def __init__(
        self,
        message: str | None = None,
        tool_name: str | None = None,
        slug: str | None = None,
    ) -> None:
        context: dict = {}
        if tool_name is not None:
            context["tool_name"] = tool_name
        if slug is not None:
            context["slug"] = slug
        super().__init__(message=message, context=context)


class SkillLoadError(BusinessException):
    """SKILL.md 文件读取/解析失败（IO 错误、YAML frontmatter 格式错误）

    父类 BusinessException → HTTP 500（业务级 IO 错误视为内部错误）。

    Attributes:
        code: 错误码 EXCEPTION_388
        message: 默认消息
    """

    code = "EXCEPTION_388"
    message = "Skill load error"

    def __init__(
        self,
        message: str | None = None,
        slug: str | None = None,
        file_path: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        context: dict = {}
        if slug is not None:
            context["slug"] = slug
        if file_path is not None:
            context["file_path"] = file_path
        super().__init__(message=message, cause=cause, context=context)


class ToolResultValidationError(ValidationError):
    """ToolResult.status=invalid 需附加上下文（与 EntityBusinessRuleError 区分）

    继承自 ValidationError（EXCEPTION_201）→ HTTP 400。

    Attributes:
        code: 错误码 EXCEPTION_389
        message: 默认消息
    """

    code = "EXCEPTION_389"
    message = "Tool result validation error"

    def __init__(
        self,
        message: str | None = None,
        tool_id: str | None = None,
        execution_id: str | None = None,
        reason: str | None = None,
    ) -> None:
        context: dict = {}
        if tool_id is not None:
            context["tool_id"] = tool_id
        if execution_id is not None:
            context["execution_id"] = execution_id
        if reason is not None:
            context["reason"] = reason
        super().__init__(message=message, context=context)


__all__ = [
    "ToolNotFoundError",
    "ToolAlreadyExistsError",
    "ToolExecutionFailedError",
    "ToolExecutionRetryExhaustedError",
    "ToolExecutionTimeoutError",
    "EvidenceValidationFailedError",
    "SkillNotFoundError",
    "SkillLoadError",
    "ToolResultValidationError",
]
