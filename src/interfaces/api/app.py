"""接口层 FastAPI 应用工厂模块

提供 FastAPI 应用实例创建，包含 lifecycle 管理，
在 startup/shutdown 事件中管理后台轮询器生命周期
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """应用生命周期管理，启动/停止后台轮询器"""
    from src.composition_root import bootstrap, shutdown
    from src.domain.ports.resolver import get_resolver

    bootstrap()
    resolver = get_resolver()
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
    return FastAPI(lifespan=_lifespan)
