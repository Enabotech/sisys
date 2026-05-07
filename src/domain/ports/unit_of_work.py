"""UnitOfWork — 工作单元模式接口。

用于统一事务边界，保证业务操作与 Outbox 写入原子性。
仅定义抽象接口，无外部依赖。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Self


class UnitOfWork(ABC):
    """抽象工作单元接口。

    定义事务边界：begin(), commit(), rollback(), close()。
    支持异步上下文管理器协议。
    """

    @abstractmethod
    async def begin(self) -> None:
        """开始事务。"""
        raise NotImplementedError

    @abstractmethod
    async def commit(self) -> None:
        """提交事务。"""
        raise NotImplementedError

    @abstractmethod
    async def rollback(self) -> None:
        """回滚事务。"""
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """关闭会话。"""
        raise NotImplementedError

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
