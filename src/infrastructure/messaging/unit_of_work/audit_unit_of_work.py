"""基础设施层审计工作单元模块

提供 SERIALIZABLE 隔离级别的工作单元，用于审计日志等需要高隔离级别的场景

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from src.domain.exceptions import InvalidStateError
from src.domain.ports.unit_of_work import UnitOfWork

if TYPE_CHECKING:
    from types import TracebackType

    from sqlalchemy.ext.asyncio import AsyncSession

    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager


class AuditUnitOfWork(UnitOfWork):
    """审计工作单元

    使用 SERIALIZABLE 隔离级别确保审计日志的强一致性
    适用于审计日志写入等需要高隔离级别的场景
    实现 UnitOfWork Protocol 接口

    Attributes:
        session: 当前事务的 session 对象
    """

    def __init__(self, manager: PostgreSQLManager) -> None:
        """初始化审计工作单元

        Args:
            manager: PostgreSQLManager 实例，用于创建 SERIALIZABLE 隔离级别的 session
        """
        self._manager = manager
        self._session: AsyncSession | None = None
        self._committed = False
        self._rolled_back = False

    @property
    def session(self) -> AsyncSession:
        """获取当前事务的 session

        Returns:
            当前的 AsyncSession 实例

        Raises:
            RuntimeError: 如果 session 未初始化（未调用 __aenter__ 或 begin）
        """
        if self._session is None:
            raise RuntimeError("Session not initialized. Use 'async with' or call begin() first.")
        return self._session

    async def begin(self) -> None:
        """开始事务

        通过 PostgreSQLManager.get_session_with_isolation 创建 SERIALIZABLE 隔离级别的 session，
        然后调用 session.begin() 开始事务

        Raises:
            InvalidStateError: 当已提交或已回滚时
        """
        if self._committed:
            raise InvalidStateError("Already committed")
        if self._rolled_back:
            raise InvalidStateError("Already rolled back")
        self._session_ctx = self._manager.get_session_with_isolation("SERIALIZABLE")
        self._session = await self._session_ctx.__aenter__()
        await self._session.begin()

    async def commit(self) -> None:
        """提交事务

        Raises:
            InvalidStateError: 当已提交或已回滚时
        """
        if self._committed:
            raise InvalidStateError("Already committed")
        if self._rolled_back:
            raise InvalidStateError("Already rolled back")
        if self._session is None:
            raise RuntimeError("Session not initialized")
        await self._session.commit()
        self._committed = True

    async def rollback(self) -> None:
        """回滚事务

        Raises:
            InvalidStateError: 当已提交或已回滚时
        """
        if self._committed:
            raise InvalidStateError("Already committed")
        if self._rolled_back:
            raise InvalidStateError("Already rolled back")
        if self._session is None:
            raise RuntimeError("Session not initialized")
        await self._session.rollback()
        self._rolled_back = True

    async def begin_nested(self) -> None:
        """创建 savepoint（嵌套事务）

        使用 SQLAlchemy 的 begin_nested() 创建未命名 savepoint
        """
        if self._session is None:
            raise RuntimeError("Session not initialized")
        await self._session.begin_nested()

    async def __aenter__(self) -> Self:
        """异步上下文管理器入口"""
        await self.begin()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """异步上下文管理器出口

        规则：
        - 异常：rollback
        - 正常：仅在未手动 commit/rollback 时才 commit
        - 关闭 session 并退出隔离级别上下文
        - 返回 False：不吞没异常

        Args:
            exc_type: 异常类型
            exc_val: 异常值
            exc_tb: 异常追踪

        Returns:
            False（不吞没异常）
        """
        try:
            if exc_type is not None:
                if not self._rolled_back:
                    await self.rollback()
            elif not self._committed and not self._rolled_back:
                await self.commit()
        finally:
            if self._session is not None and hasattr(self, "_session_ctx"):
                await self._session_ctx.__aexit__(exc_type, exc_val, exc_tb)
        return False
