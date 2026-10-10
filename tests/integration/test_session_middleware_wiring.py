"""SessionMiddleware 生产接线冒烟（技术债清偿 A 类——接线回归防线）

接线前生产全路径无请求 session（outbox/仓储 save 恒走 RuntimeError fallback）；
接线后每请求经 SessionMiddleware 创建 AsyncSession 注入 ContextVar。

真实服务纪律：conftest 会话级 bootstrap 的真实 resolver + 真实 session_factory
（async_sessionmaker 绑 postgres_async_engine）+ TestClient 走完整中间件链
（SessionMiddleware 内层 / ExceptionContextMiddleware 外层）。

覆盖：
1. 请求过中间件链成功（200——factory 解析 + session 创建/关闭全程正常）
2. 请求后 ContextVar 无泄漏（finally reset 生效）
3. 中间件层序：ExceptionContextMiddleware 在外层（异常上下文先于会话收口）
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.domain.ports.resolver import get_resolver


@pytest.fixture
def app() -> Any:
    """真实 create_app 产物（conftest 会话级 bootstrap 已就绪 resolver）."""
    from src.interfaces.api.app import create_app

    return create_app()


class TestSessionMiddlewareWiring:
    """接线冒烟：请求经中间件链且会话生命周期完整."""

    def test_request_through_middleware_chain_succeeds(self, app: Any) -> None:
        """GET /openapi.json 过完整中间件链——session factory 解析 + 会话
        创建/关闭全程正常（PG 不可达时 sessionmaker 构建在 bootstrap 期，
        此处验证的是请求路径零异常）."""
        client = TestClient(app)
        response = client.get("/openapi.json")
        assert response.status_code == 200, "请求应经 SessionMiddleware 链成功返回"

    def test_session_contextvar_reset_after_request(self, app: Any) -> None:
        """请求结束后 ContextVar session 已 reset（中间件 finally 生效——
        无跨请求会话泄漏；get_session 无会话时抛 RuntimeError）."""
        from src.infrastructure.storage.postgresql.session_context import get_session

        client = TestClient(app)
        client.get("/openapi.json")
        with pytest.raises(RuntimeError):
            get_session()

    def test_middleware_ordering_exception_outermost(self, app: Any) -> None:
        """中间件层序：ExceptionContextMiddleware 在 SessionMiddleware 外层.

        Starlette `add_middleware` 为 insert(0)——user_middleware 列表序 =
        外层优先（先出现者更外层）；app.py 中 SessionMiddleware 先添加、
        ExceptionContextMiddleware 后添加 → 列表中 ExceptionContext 在前（外层）。
        """
        from src.interfaces.api.middleware.session import SessionMiddleware

        assert any(m.cls is SessionMiddleware for m in app.user_middleware), "SessionMiddleware 应已注册"
        names = [m.cls.__name__ for m in app.user_middleware]
        assert names.index("ExceptionContextMiddleware") < names.index("SessionMiddleware"), (
            f"ExceptionContextMiddleware 应在外层（列表序外层优先），实际: {names}"
        )

    def test_session_factory_resolvable_from_production_resolver(self) -> None:
        """组合根 session_factory（SINGLETON async_sessionmaker）可解析且调用
        返回 AsyncSession——接线 lazy factory 的解析路径实证."""
        from sqlalchemy.ext.asyncio import AsyncSession

        factory = get_resolver().resolve("session_factory")
        session = factory()
        assert isinstance(session, AsyncSession), "factory() 应产出 AsyncSession"
