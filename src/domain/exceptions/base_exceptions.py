"""领域层 异常层次结构根类模块

定义领域异常层次结构根类 BaseException，仅使用 Python 标准库，
HTTP 状态码等 Web 层关注点由接口层异常处理器负责映射

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations


class BaseException(Exception):  # noqa: N818
    """异常层次结构根类

    此基类定义在领域层，仅使用 Python 标准库
    HTTP 状态码等 Web 层关注点不在此定义，由接口层异常处理器负责映射
    名称故意与 Python 内置 BaseException 不同——这是领域异常层次结构根类
    """

    code: str = "EXCEPTION_000"
    message: str = "Unknown error"
    cause: Exception | None = None
    context: dict = {}

    def __init__(
        self,
        message: str | None = None,
        cause: Exception | None = None,
        context: dict | None = None,
    ) -> None:
        self.message = message or self.__class__.message
        self.cause = cause
        self.context = context or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """转换为字典格式，便于序列化和日志记录"""
        result = {
            "code": self.code,
            "message": self.message,
            "context": self.context,
        }
        if self.cause:
            if isinstance(self.cause, BaseException):
                result["cause"] = self.cause.to_dict()
            else:
                result["cause"] = {
                    "type": type(self.cause).__name__,
                    "message": str(self.cause),
                }
        return result


# 重新导出，方便 from src.domain.exceptions import BaseException
__all__ = ["BaseException"]
