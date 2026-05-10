"""InvalidStateError — 事务状态异常。

当操作违反事务状态约束时抛出（如重复 commit/rollback）。
"""

from __future__ import annotations


class InvalidStateError(Exception):
    """无效的事务状态异常。

    当在已提交或已回滚的事务上再次进行 commit/rollback 时抛出。
    """

    def __init__(self, message: str) -> None:
        """初始化 InvalidStateError。

        Args:
            message: 错误信息
        """
        self.message = message
        super().__init__(message)
