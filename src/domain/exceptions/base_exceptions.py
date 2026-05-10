"""BaseException — 异常层次结构根类.

注意：此基类定义在领域层（src/domain/exceptions/），仅使用Python标准库。
HTTP状态码等Web层关注点不在此定义，由接口层异常处理器负责映射。
"""

from __future__ import annotations


class BaseException(Exception):  # noqa: N818
    """异常层次结构根类.

    注意：此基类定义在领域层（src/domain/exceptions/），仅使用Python标准库。
    HTTP状态码等Web层关注点不在此定义，由接口层异常处理器负责映射。
    名称故意与 Python 内置 BaseException 不同 - 这是领域异常层次结构根类。
    """

    code: str = "EXCEPTION_000"
    message: str = "Unknown error"

    def __init__(
        self,
        message: str | None = None,
        cause: BaseException | None = None,
        context: dict | None = None,
    ) -> None:
        self.message = message or self.__class__.message
        self.cause = cause
        self.context = context or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """转换为字典格式，便于序列化和日志记录."""
        result = {
            "code": self.code or "EXCEPTION_000",
            "message": self.message or "Unknown error",
            "context": self.context or {},
        }
        if self.cause:
            result["cause"] = {
                "type": type(self.cause).__name__,
                "message": str(self.cause),
            }
        return result


# 重新导出，方便 from src.domain.exceptions import BaseException
__all__ = ["BaseException"]
