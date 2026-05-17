"""基础设施层 PostgreSQL 工作单元模块

基于 SQLAlchemy AsyncSession 实现工作单元模式，管理事务的生命周期
Session 通过 ContextVar 由 middleware 或 test fixture 提供，
无需构造器注入 session 参数

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from src.domain.exceptions import InvalidStateError
from src.domain.ports.unit_of_work import UnitOfWork
from src.infrastructure.storage.postgresql.session_context import get_session

if TYPE_CHECKING:
    from types import TracebackType

    from sqlalchemy.ext.asyncio import AsyncSession


class PostgreSQLUnitOfWork(UnitOfWork):
    """PostgreSQL 工作单元实现

    使用 SQLAlchemy AsyncSession 管理事务，实现领域层 UnitOfWork 接口

    Attributes:
        _committed: 是否已提交
        _rolled_back: 是否已回滚
    """

    _committed: bool = False
    _rolled_back: bool = False

    @property
    def _session(self) -> AsyncSession:
        return get_session()

    @property
    def session(self) -> AsyncSession:
        """获取当前事务的 session

        EventHandler 使用此属性提取 session 传入各 Repository

        Returns:
            当前的 AsyncSession 实例
        """
        return get_session()

    async def begin(self) -> None:
        """开始事务。"""
        await self._session.begin()

    async def commit(self) -> None:
        """显式提交事务并标记为已提交（幂等保护）

        Raises:
            InvalidStateError: 当已提交或已回滚时
        """
        if self._committed:
            raise InvalidStateError("Already committed")
        if self._rolled_back:
            raise InvalidStateError("Already rolled back")
        await self._session.commit()
        self._committed = True

    async def rollback(self) -> None:
        """回滚事务并标记为已回滚

        Raises:
            InvalidStateError: 当已提交或已回滚时
        """
        if self._committed:
            raise InvalidStateError("Already committed")
        if self._rolled_back:
            raise InvalidStateError("Already rolled back")
        await self._session.rollback()
        self._rolled_back = True

    async def begin_nested(self) -> None:
        """创建 savepoint（嵌套事务）

        使用 SQLAlchemy 的 begin_nested() 创建未命名 savepoint
        savepoint 内的操作可通过 rollback() 回滚到 savepoint 点，
        或通过外层 commit() 一起提交

        注意：SQLAlchemy 无"释放 savepoint" API，
        调用 commit() 会提交整个事务链（包括所有 savepoint），
        若需回滚单个 savepoint，使用 rollback()
        """
        await self._session.begin_nested()

    async def close(self) -> None:
        """关闭会话。"""
        await self._session.close()

    async def __aenter__(self) -> Self:
        """异步上下文管理器入口。"""
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
        - 异常：rollback（处理 rollback 失败也要 close session）
        - 正常：仅在未手动 commit/rollback 时才 commit
        - 始终 close session
        - 返回 False：不吞没异常

        Args:
            exc_type: 异常类型
            exc_val: 异常值
            exc_tb: 异常追踪

        Returns:
            False（不吞没异常）
        """
        if exc_type is not None:
            if not self._rolled_back:
                try:
                    await self.rollback()
                except Exception:
                    await self.close()
                    raise
        elif not self._committed and not self._rolled_back:
            await self.commit()
        await self.close()
        return False
