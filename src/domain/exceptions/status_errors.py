"""
sisys - Status Related Errors.

状态相关错误定义。
"""

from src.domain.exceptions.base import DomainError


class InvalidStatusError(DomainError):
    """
    无效状态错误。

    当尝试执行无效的状态转换时抛出此异常。
    """

    def __init__(self, message: str):
        """
        初始化无效状态错误。

        Args:
            message: 错误消息
        """
        super().__init__(message, code="INVALID_STATUS")
