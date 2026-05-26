"""基础设施层会话中间件模块

提供 ASGI 中间件，在每个请求中管理 AsyncSession 的生命周期
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
    """ASGI 中间件，在每个请求中管理 AsyncSession

    请求开始时通过 ContextVar 创建 AsyncSession，成功时提交，异常时回滚，结束时关闭

    Attributes:
        _factory: 会话工厂函数
    """

    def __init__(self, app: Any, session_factory: Callable) -> None:
        """初始化会话中间件

        Args:
            app: ASGI 应用实例
            session_factory: 会话工厂函数
        """
        super().__init__(app)
        self._factory = session_factory

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并管理会话生命周期

        通过 session.in_transaction() 检查事务状态：
        - UoW 已 commit/rollback 后 in_transaction() 为 False，跳过操作
        - UoW 未使用时 in_transaction() 为 True，由 Middleware commit/rollback
        finally 块始终负责 close + reset

        注意：使用 session.in_transaction() 而非 ContextVar 标记，
        因为 BaseHTTPMiddleware 的 call_next 在独立任务上下文中运行，
        ContextVar.set() 不会传播回父上下文，而 session 对象跨上下文共享

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
            if session.in_transaction():
                await session.commit()
            return response
        except Exception:
            if session.in_transaction():
                await session.rollback()
            raise
        finally:
            await session.close()
            reset_session(token)
