"""基础设施层审计工作单元模块

提供 SERIALIZABLE 隔离级别的工作单元，用于审计日志等需要高隔离级别的场景

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import Self

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class AuditUnitOfWork:
    """审计工作单元

    使用 SERIALIZABLE 隔离级别确保审计日志的强一致性
    适用于审计日志写入等需要高隔离级别的场景

    Attributes:
        session: 当前事务的 session 对象
        _isolation_level: 隔离级别（固定为 SERIALIZABLE）
    """

    def __init__(self, session: AsyncSession) -> None:
        """初始化审计工作单元

        Args:
            session: AsyncSession 实例
        """
        self._session = session
        self._isolation_level = "SERIALIZABLE"
        self._committed = False
        self._rolled_back = False

    @property
    def session(self) -> AsyncSession:
        """获取当前事务的 session"""
        return self._session

    async def begin(self) -> None:
        """开始事务并设置 SERIALIZABLE 隔离级别"""
        await self._session.execute(text(f"SET TRANSACTION ISOLATION LEVEL {self._isolation_level}"))
        await self._session.begin()

    async def commit(self) -> None:
        """提交事务"""
        if self._committed:
            raise RuntimeError("Already committed")
        if self._rolled_back:
            raise RuntimeError("Already rolled back")
        await self._session.commit()
        self._committed = True

    async def rollback(self) -> None:
        """回滚事务"""
        if self._committed:
            raise RuntimeError("Already committed")
        if self._rolled_back:
            raise RuntimeError("Already rolled back")
        await self._session.rollback()
        self._rolled_back = True

    async def __aenter__(self) -> Self:
        """异步上下文管理器入口"""
        await self.begin()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """异步上下文管理器出口"""
        if exc_type is not None:
            if not self._rolled_back:
                await self.rollback()
        elif not self._committed and not self._rolled_back:
            await self.commit()
        return False
