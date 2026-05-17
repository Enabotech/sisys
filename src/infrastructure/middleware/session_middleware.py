"""SISYS 基础设施层会话中间件模块。

提供 ASGI 中间件，在每个请求中管理 AsyncSession 的生命周期。

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
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
    """ASGI 中间件，在每个请求中管理 AsyncSession。

    请求开始时通过 ContextVar 创建 AsyncSession，成功时提交，异常时回滚，结束时关闭。

    Attributes:
        _factory: 会话工厂函数
    """

    def __init__(self, app: Any, session_factory: Callable) -> None:
        """初始化会话中间件。

        Args:
            app: ASGI 应用实例
            session_factory: 会话工厂函数
        """
        super().__init__(app)
        self._factory = session_factory

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并管理会话生命周期。

        Args:
            request: HTTP 请求对象
            call_next: 下一个中间件或路由处理器

        Returns:
            HTTP 响应对象
        """
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
