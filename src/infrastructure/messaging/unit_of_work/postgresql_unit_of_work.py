"""PostgreSQL UnitOfWork 实现 — 基础设施层。

基于 SQLAlchemy AsyncSession 的工作单元模式实现。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

from src.domain.ports.unit_of_work import UnitOfWork

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class PostgreSQLUnitOfWork(UnitOfWork):
    """PostgreSQL 工作单元实现。

    使用 SQLAlchemy AsyncSession 管理事务。
    实现领域层 UnitOfWork 接口。
    """

    def __init__(self, session: AsyncSession) -> None:
        """初始化 PostgreSQLUnitOfWork。

        Args:
            session: SQLAlchemy 异步会话
        """
        self._session = session

    async def begin(self) -> None:
        """开始事务。"""
        await self._session.begin()

    async def commit(self) -> None:
        """提交事务。"""
        await self._session.commit()

    async def rollback(self) -> None:
        """回滚事务。"""
        await self._session.rollback()

    async def close(self) -> None:
        """关闭会话。"""
        await self._session.close()

    async def __aenter__(self) -> Self:
        """异步上下文管理器入口。"""
        await self.begin()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """异步上下文管理器出口。"""
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()
        await self.close()
