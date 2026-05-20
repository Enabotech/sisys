"""基础设施层 PostgreSQL 会话上下文模块

基于 ContextVar 提供异步会话访问，支持中间件和测试夹具管理会话生命周期

ContextVar 传递规则（详见 docs/developer/session-management.md）：
- R1: 标准 CRUD 仓储和 UoW 通过 get_session() 获取 session
- R2: 需要特殊隔离级别时使用构造函数注入 PostgreSQLManager（如 AuditUnitOfWork）
- R3: 后台任务使用 session_context() 创建独立 scope

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from contextlib import asynccontextmanager
from contextvars import ContextVar, Token
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_session_ctx: ContextVar[AsyncSession | None] = ContextVar(
    "pg_session",
    default=None,
)


def get_session() -> AsyncSession:
    """从当前上下文获取 AsyncSession

    Repository 和 UoW 通过此函数获取 session，无需构造器注入

    Usage::

        # 在 Repository 中
        @property
        def _session(self) -> AsyncSession:
            return get_session()

    Returns:
        当前上下文中的 AsyncSession 实例

    Raises:
        RuntimeError: 如果上下文中未设置会话
    """
    session = _session_ctx.get()
    if session is None:
        raise RuntimeError("No AsyncSession in context. Call set_session() within a middleware or test fixture first.")
    return session


def get_session_optional() -> AsyncSession | None:
    """从当前上下文获取 AsyncSession，未设置时返回 None

    Returns:
        AsyncSession 实例或 None
    """
    return _session_ctx.get()


def set_session(session: AsyncSession) -> Token:
    """在当前上下文中设置 AsyncSession

    通常由 SessionMiddleware 或测试夹具调用，Repository 不应直接调用

    Usage::

        token = set_session(my_session)
        try:
            # ... 使用 Repository/UoW ...
        finally:
            reset_session(token)

    Args:
        session: 要设置的 AsyncSession 实例

    Returns:
        用于重置上下文的 Token
    """
    return _session_ctx.set(session)


def reset_session(token: Token) -> None:
    """使用 Token 重置 AsyncSession 上下文

    必须在 finally 块中调用，确保 ContextVar 正确清理

    Usage::

        token = set_session(session)
        try:
            # ... 业务操作 ...
        finally:
            reset_session(token)

    Args:
        token: set_session 返回的 Token
    """
    _session_ctx.reset(token)


@asynccontextmanager
async def session_context(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """AsyncSession 生命周期上下文管理器，自动提交或回滚事务

    后台任务（Poller/Saga）使用此函数创建独立 session scope，
    HTTP 请求场景由 SessionMiddleware 管理，不需要此函数

    Usage::

        factory = resolver.resolve("session_factory")
        async with session_context(factory):
            repo = SomeRepository()
            await repo.save(entity)
        # 自动 commit + close + reset ContextVar

    Args:
        session_factory: 绑定到 AsyncEngine 的异步会话工厂

    Yields:
        带事务管理的 AsyncSession 实例
    """
    session = session_factory()
    token = set_session(session)
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
        reset_session(token)


@asynccontextmanager
async def with_session(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    """测试辅助上下文管理器，为已有的 session 设置 ContextVar

    在测试中替代手动 set_session()/reset_session() 管理

    Usage::

        @pytest.mark.asyncio
        async def test_repo():
            mock_session = AsyncMock(spec=AsyncSession)
            async with with_session(mock_session):
                repo = UserRepository()
                await repo.save(entity)
            # 自动 reset ContextVar

    Args:
        session: AsyncSession 实例（通常为 mock）

    Yields:
        The provided session instance.
    """
    token = set_session(session)
    try:
        yield session
    finally:
        reset_session(token)
