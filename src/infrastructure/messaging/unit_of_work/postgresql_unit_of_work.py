"""PostgreSQL UnitOfWork 实现 — 基础设施层

基于 SQLAlchemy AsyncSession 的工作单元模式实现

Session 来源：
- Session 通过 ContextVar 由 middleware 或 test fixture 提供
- 无需构造器注入 session 参数
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

    使用 SQLAlchemy AsyncSession 管理事务
    实现领域层 UnitOfWork 接口
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
        """
        return get_session()

    async def begin(self) -> None:
        """开始事务"""
        await self._session.begin()

    async def commit(self) -> None:
        """显式提交 + 幂等标记"""
        if self._committed:
            raise InvalidStateError("Already committed")
        if self._rolled_back:
            raise InvalidStateError("Already rolled back")
        await self._session.commit()
        self._committed = True

    async def rollback(self) -> None:
        """回滚 + 标记"""
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

        注意：SQLAlchemy 无"释放 savepoint" API
        调用 commit() 会提交整个事务链（包括所有 savepoint）
        若需回滚单个 savepoint，使用 rollback()
        """
        await self._session.begin_nested()

    async def close(self) -> None:
        """关闭会话"""
        await self._session.close()

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
        - 异常：rollback（处理 rollback 失败也要 close session）
        - 正常：仅在未手动 commit/rollback 时才 commit
        - 始终 close session
        - 返回 False：不吞没异常
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
