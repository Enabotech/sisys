"""领域层 异常层次结构根类模块

定义领域异常层次结构根类 DomainError，仅使用 Python 标准库，
HTTP 状态码等 Web 层关注点由接口层异常处理器负责映射。
为避免与 Python 内置 Exception 命名冲突并遵循 pep8-naming 规范，根类命名为 DomainError。
"""

from __future__ import annotations


class DomainError(Exception):
    """异常层次结构根类

    此基类定义在领域层，仅使用 Python 标准库。
    HTTP 状态码等 Web 层关注点不在此定义，由接口层异常处理器负责映射。

    注意：为避免遮蔽 Python 内置类型触发 Ruff N818 告警，
    领域根类命名为 DomainError。外部代码可通过以下两种方式引用：
    - from src.domain.exceptions.base_exceptions import DomainError（推荐）
    - from src.domain.exceptions.base_exceptions import BaseException（向后兼容别名）
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
        """转换为字典格式，便于序列化和日志记录。

        异常链路解析顺序（优先级递减）：
        1. self.cause — 显式 cause 参数（如 ToolChainExecutionFailedError(cause=e)）
        2. self.__cause__ — `raise X from Y` 设置的隐式 cause（PEP 3134）
        3. self.__context__ — 异常处理期间自动捕获的隐式 context

        升级原因：原实现仅读 self.cause，导致仅 `raise X from Y` 的异常链路
        在 to_dict() 输出中丢失，SRE 监控系统看不到根因编码。
        """
        result = {
            "code": self.code,
            "message": self.message,
            "context": self.context,
        }
        # 优先取显式 cause，降级到 __cause__（raise X from Y），最后 __context__
        cause_chain = self.cause or self.__cause__ or self.__context__
        if cause_chain:
            if isinstance(cause_chain, DomainError):
                result["cause"] = cause_chain.to_dict()
            else:
                result["cause"] = {
                    "type": type(cause_chain).__name__,
                    "message": str(cause_chain),
                }
        return result


# 向后兼容别名：旧代码可使用 BaseException 引用 DomainError
BaseException = DomainError

__all__ = ["DomainError", "BaseException"]
