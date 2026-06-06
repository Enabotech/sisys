"""领域层跨境传输异常模块

将 TransferNotFoundError/TransferNotApprovedError 从基础设施层迁移到领域层，
纳入统一异常层次结构。遵循 R1（领域层统一抽象基础异常）。
"""

from __future__ import annotations

from src.domain.exceptions.business_exceptions import InvalidStateError, NotFoundError


class TransferNotFoundError(NotFoundError):
    """跨境传输请求未找到异常

    Attributes:
        code: 异常编码
        message: 异常消息
    """

    code = "EXCEPTION_261"
    message = "Transfer request not found"


class TransferNotApprovedError(InvalidStateError):
    """跨境传输请求未审批通过时执行操作异常

    Attributes:
        code: 异常编码
        message: 异常消息
    """

    code = "EXCEPTION_262"
    message = "Transfer request not approved"


__all__ = [
    "TransferNotFoundError",
    "TransferNotApprovedError",
]
