"""领域层工具异常模块

定义工具相关领域异常：ToolNotFoundError、ToolAlreadyExistsError。
异常是领域契约的一部分，遵循异常编码范围约束。
"""

from __future__ import annotations

from src.domain.exceptions.business_exceptions import ConflictError, NotFoundError


class ToolNotFoundError(NotFoundError):
    """按 ID/名称查询工具不存在

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
    ) -> None:
        context: dict = {}
        if tool_id is not None:
            context["tool_id"] = tool_id
        if tool_name is not None:
            context["tool_name"] = tool_name
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


__all__ = ["ToolNotFoundError", "ToolAlreadyExistsError"]
