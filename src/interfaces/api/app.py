"""接口层 FastAPI 应用工厂模块

提供 FastAPI 应用实例创建，包含 lifecycle 管理，
在 startup/shutdown 事件中管理后台轮询器生命周期
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.composition_root import session_middleware_wiring
from src.interfaces.api.exception_handlers import register_exception_handlers
from src.interfaces.api.middleware.exception_context import ExceptionContextMiddleware
from src.interfaces.api.middleware.session import SessionMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """应用生命周期管理，启动/停止后台轮询器"""
    from src.composition_root import bootstrap, shutdown
    from src.domain.ports.resolver import get_resolver

    bootstrap()
    resolver = get_resolver()
    rabbitmq_publisher = resolver.resolve("rabbitmq_publisher")
    await rabbitmq_publisher.connect()
    poller = resolver.resolve("outbox_poller")
    poller_task = asyncio.create_task(poller.run())

    logger.info("Application started with outbox poller")

    yield

    poller.stop()
    try:
        await poller_task
    except asyncio.CancelledError:
        pass
    await shutdown()
    logger.info("Application shut down")


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例

    Returns:
        带 lifespan 管理的 FastAPI 实例
    """
    app = FastAPI(lifespan=_lifespan)
    # 注册中间件（Starlette add_middleware 为 insert(0)——user_middleware 列表序
    # = 外层优先；ExceptionContextMiddleware 后添加保持最外层，SessionMiddleware
    # 处于其内层管理请求事务边界：成功 commit / 异常 rollback / finally
    # close+reset（与 UoW 经 in_transaction() 共存）——infra 依赖绑定经组合根
    # session_middleware_wiring 注入（interfaces→infrastructure 零直接依赖）
    app.add_middleware(SessionMiddleware, **session_middleware_wiring())
    app.add_middleware(ExceptionContextMiddleware)
    # 注册统一异常处理器
    register_exception_handlers(app)
    # 注册路由
    from src.interfaces.api.document_upload import document_upload_router
    from src.interfaces.api.domain_dictionary import document_dictionary_router
    from src.interfaces.api.relevance_evaluation import evaluate_router
    from src.interfaces.api.strategic_archive import archive_router
    from src.interfaces.api.summary import summary_router
    from src.interfaces.api.tools import tools_router
    from src.interfaces.api.traceability import trace_router

    app.include_router(archive_router)
    app.include_router(summary_router)
    app.include_router(evaluate_router)
    app.include_router(trace_router)
    app.include_router(document_dictionary_router)
    app.include_router(document_upload_router)
    app.include_router(tools_router)
    return app
