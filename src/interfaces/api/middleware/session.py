"""接口层请求会话中间件（SessionMiddleware 生产接线——技术债清偿 A 类）

ASGI 中间件属接口层组件（与 ExceptionContextMiddleware 同层）；对存储层
ContextVar（set_session/reset_session）与会话工厂的依赖经**构造注入**（依赖
倒置——具体绑定由组合根 `session_middleware_wiring` 提供，本层零 infrastructure
import，六边形 interfaces→infrastructure 禁依赖合规）。

请求开始时经工厂创建 AsyncSession 注入 ContextVar，成功 commit、异常 rollback、
finally close + reset。
"""

from __future__ import annotations

from typing import Any, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SessionMiddleware(BaseHTTPMiddleware):
    """ASGI 中间件：每请求管理 AsyncSession 生命周期（依赖全注入）.

    Attributes:
        _factory: 会话工厂（零参调用返回 AsyncSession）
        _setter: ContextVar 会话设置函数（注入形态——infra 具体绑定在组合根）
        _resetter: ContextVar 会话还原函数（接受 setter 返回的 token）
    """

    def __init__(
        self,
        app: Any,
        session_factory: Callable,
        session_setter: Callable,
        session_resetter: Callable,
    ) -> None:
        """初始化会话中间件.

        Args:
            app: ASGI 应用实例
            session_factory: 会话工厂函数
            session_setter: set_session 形态函数（返回 token）
            session_resetter: reset_session 形态函数（接受 token）
        """
        super().__init__(app)
        self._factory = session_factory
        self._setter = session_setter
        self._resetter = session_resetter

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并管理会话生命周期.

        通过 session.in_transaction() 检查事务状态：
        - UoW 已 commit/rollback 后 in_transaction() 为 False，跳过操作
        - UoW 未使用时 in_transaction() 为 True，由 Middleware commit/rollback
        finally 块始终负责 close + reset.

        注意：使用 session.in_transaction() 而非 ContextVar 标记，
        因为 BaseHTTPMiddleware 的 call_next 在独立任务上下文中运行，
        ContextVar.set() 不会传播回父上下文，而 session 对象跨上下文共享.

        Args:
            request: HTTP 请求对象
            call_next: 下一个中间件或路由处理器

        Returns:
            HTTP 响应对象
        """
        session = self._factory()
        token = self._setter(session)
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
            self._resetter(token)
