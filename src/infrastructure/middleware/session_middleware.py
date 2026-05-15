"""SessionMiddleware — ASGI middleware that manages AsyncSession per request.

Automatically creates an AsyncSession via ContextVar at request start,
commits on success, rolls back on exception, and closes on finish.

Architecture: architecture.md §11 — DI manages static deps; middleware + ContextVar manage dynamic session scope.
"""

from __future__ import annotations

from typing import Any, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.infrastructure.storage.postgresql.session_context import (
    reset_session,
    set_session,
)


class SessionMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that manages AsyncSession per request."""

    def __init__(self, app: Any, session_factory: Callable) -> None:
        super().__init__(app)
        self._factory = session_factory

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        session = self._factory()
        token = set_session(session)
        try:
            response: Response = await call_next(request)
            await session.commit()
            return response
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
            reset_session(token)
