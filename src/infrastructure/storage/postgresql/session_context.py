"""基础设施层 PostgreSQL 会话上下文模块

基于 ContextVar 提供异步会话访问，支持中间件和测试夹具管理会话生命周期

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

_uow_managed_ctx: ContextVar[bool] = ContextVar(
    "uow_managed",
    default=False,
)


def get_session() -> AsyncSession:
    """从当前上下文获取 AsyncSession

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

    Args:
        session: 要设置的 AsyncSession 实例

    Returns:
        用于重置上下文的 Token
    """
    return _session_ctx.set(session)


def reset_session(token: Token) -> None:
    """使用 Token 重置 AsyncSession 上下文

    Args:
        token: set_session 返回的 Token
    """
    _session_ctx.reset(token)


def is_uow_managed() -> bool:
    """检查当前上下文中 UoW 是否正在管理事务

    Returns:
        True 表示 UoW 已处理事务（commit/rollback），SessionMiddleware 无需再操作
    """
    return _uow_managed_ctx.get()


def mark_uow_managed(managed: bool) -> Token:
    """标记当前上下文 UoW 是否已管理事务

    Args:
        managed: True 表示 UoW 已管理

    Returns:
        用于重置上下文的 Token
    """
    return _uow_managed_ctx.set(managed)


def reset_uow_managed(token: Token) -> None:
    """重置 UoW 管理标记

    Args:
        token: mark_uow_managed 返回的 Token
    """
    _uow_managed_ctx.reset(token)


@asynccontextmanager
async def session_context(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """AsyncSession 生命周期上下文管理器，自动提交或回滚事务

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
    """Context manager for setting a specific session (test helper).

    Usage:
        async with with_session(mock_session):
            repo = UserRepository()
            await repo.get_by_id("123")

    Args:
        session: AsyncSession instance to set in context.

    Yields:
        The provided session instance.
    """
    token = set_session(session)
    try:
        yield session
    finally:
        reset_session(token)
