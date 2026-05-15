"""PostgreSQL async session context management.

Provides ContextVar-based session access for repositories.
DI manages static deps; middleware + ContextVar manage dynamic session scope.
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
    """Get current AsyncSession from context.

    Raises:
        RuntimeError: If no session is set in context.
    """
    session = _session_ctx.get()
    if session is None:
        raise RuntimeError(
            "No AsyncSession in context. "
            "Call set_session() within a middleware or test fixture first."
        )
    return session


def get_session_optional() -> AsyncSession | None:
    """Get current AsyncSession from context, or None if not set."""
    return _session_ctx.get()


def set_session(session: AsyncSession) -> Token:
    """Set AsyncSession in current context, returns token for reset."""
    return _session_ctx.set(session)


def reset_session(token: Token) -> None:
    """Reset AsyncSession context using token."""
    _session_ctx.reset(token)


@asynccontextmanager
async def session_context(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Context manager for AsyncSession lifecycle with auto commit/rollback.

    Usage:
        async with session_context(session_factory) as session:
            repo = UserRepository()
            await repo.create(entity)

    Args:
        session_factory: async_sessionmaker bound to AsyncEngine.

    Yields:
        AsyncSession instance with transaction management.
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
