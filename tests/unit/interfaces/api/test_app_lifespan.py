"""App Lifespan 上下文管理器测试

测试 _lifespan 启动/关闭行为
注意：bootstrap/shutdown/get_resolver 在 _lifespan 内部导入，需 patch composition_root

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.
"""

from __future__ import annotations

import asyncio
import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.entrypoints.api_app import _lifespan, create_app


@pytest.fixture(autouse=True)
def _heal_frozen_mock_bindings():
    """治愈 patch 窗口内首次导入固化的 from-import mock 绑定。

    根因: create_app() 在 patch 窗口内经函数内 import 首次导入路由模块（如
    traceability），其模块级 ``from src.domain.ports.resolver import get_resolver``
    把 mock 固化进路由模块命名空间——patch 退出只还原源模块属性，不追踪
    from-import 绑定 → 后续同进程测试（如契约 test_api_contract_traceability
    的 401 认证场景）经路由模块拿到 mock → KeyError('auth_service') → 500。

    治愈机制（通用，不维护受害者清单）: 测试后扫描 sys.modules 的 src.* 模块，
    凡 get_resolver 绑定是 MagicMock（被固化）的一律重置为源模块当前真值。
    """
    yield
    import src.domain.ports.resolver as resolver_module

    true_get_resolver = resolver_module.get_resolver  # patch 已退出——此为真函数
    for module in [m for m in list(sys.modules.values()) if isinstance(m, ModuleType)]:
        if not module.__name__.startswith("src."):
            continue
        bound = getattr(module, "get_resolver", None)
        if isinstance(bound, MagicMock):
            module.get_resolver = true_get_resolver


class TestLifespanStartup:
    """Lifespan 启动路径测试"""

    def test_lifespan_starts_with_bootstrap(self) -> None:
        """启动时 bootstrap() 应被调用"""
        with patch("src.composition_root.bootstrap") as mock_bootstrap:
            mock_bootstrap.return_value = None

            with patch("src.domain.ports.resolver.get_resolver") as mock_get_resolver:
                mock_resolver = MagicMock()
                mock_poller = MagicMock()
                mock_poller.run = AsyncMock(return_value=None)
                mock_rabbitmq_publisher = MagicMock()
                mock_rabbitmq_publisher.connect = AsyncMock(return_value=None)
                mock_resolver.resolve.side_effect = lambda name: {
                    "rabbitmq_publisher": mock_rabbitmq_publisher,
                    "outbox_poller": mock_poller,
                }[name]
                mock_get_resolver.return_value = mock_resolver

                app = FastAPI()

                async def run_test():
                    async with _lifespan(app):
                        pass

                asyncio.run(run_test())

                mock_bootstrap.assert_called_once()


class TestLifespanShutdown:
    """Lifespan 关闭路径测试"""

    def test_lifespan_calls_shutdown_on_exit(self) -> None:
        """关闭时 shutdown() 应被调用"""
        with patch("src.composition_root.bootstrap"):
            with patch("src.composition_root.shutdown") as mock_shutdown:
                with patch("src.domain.ports.resolver.get_resolver") as mock_get_resolver:
                    mock_resolver = MagicMock()
                    mock_poller = MagicMock()
                    mock_poller.run = AsyncMock(return_value=None)
                    mock_poller.stop = MagicMock()
                    mock_rabbitmq_publisher = MagicMock()
                    mock_rabbitmq_publisher.connect = AsyncMock(return_value=None)
                    mock_resolver.resolve.side_effect = lambda name: {
                        "rabbitmq_publisher": mock_rabbitmq_publisher,
                        "outbox_poller": mock_poller,
                    }[name]
                    mock_get_resolver.return_value = mock_resolver

                    app = FastAPI()

                    async def run_test():
                        async with _lifespan(app):
                            pass  # yield

                    asyncio.run(run_test())

                    mock_shutdown.assert_called_once()


class TestCreateAppWithTestClient:
    """使用 TestClient 测试完整 lifespan 周期"""

    def test_test_client_triggers_lifespan(self) -> None:
        """TestClient 应触发 lifespan 上下文"""
        with patch("src.composition_root.bootstrap") as mock_bootstrap:
            with patch("src.composition_root.shutdown"):
                with patch("src.domain.ports.resolver.get_resolver") as mock_get_resolver:
                    mock_resolver = MagicMock()
                    mock_poller = MagicMock()
                    mock_poller.run = AsyncMock(return_value=None)
                    mock_poller.stop = MagicMock()
                    mock_rabbitmq_publisher = MagicMock()
                    mock_rabbitmq_publisher.connect = AsyncMock(return_value=None)
                    mock_resolver.resolve.side_effect = lambda name: {
                        "rabbitmq_publisher": mock_rabbitmq_publisher,
                        "outbox_poller": mock_poller,
                    }[name]
                    mock_get_resolver.return_value = mock_resolver

                    app = create_app()
                    with TestClient(app):
                        pass  # TestClient 进入 lifespan

                    # 验证 bootstrap 被调用
                    mock_bootstrap.assert_called_once()
                    # 验证 poller.run 被调用（通过 create_task）
                    mock_poller.run.assert_called()


class TestLifespanCancelledError:
    """Lifespan CancelledError 处理测试"""

    def test_lifespan_handles_cancelled_error(self) -> None:
        """poller_task 取消时 lifespan 应正常关闭"""
        with patch("src.composition_root.bootstrap"):
            with patch("src.composition_root.shutdown") as mock_shutdown:
                with patch("src.domain.ports.resolver.get_resolver") as mock_get_resolver:
                    mock_resolver = MagicMock()
                    mock_poller = MagicMock()

                    async def mock_run():
                        raise asyncio.CancelledError()

                    mock_poller.run = MagicMock(return_value=mock_run())
                    mock_poller.stop = MagicMock()
                    mock_rabbitmq_publisher = MagicMock()
                    mock_rabbitmq_publisher.connect = AsyncMock(return_value=None)
                    mock_resolver.resolve.side_effect = lambda name: {
                        "rabbitmq_publisher": mock_rabbitmq_publisher,
                        "outbox_poller": mock_poller,
                    }[name]
                    mock_get_resolver.return_value = mock_resolver

                    app = FastAPI()

                    async def run_test():
                        async with _lifespan(app):
                            pass

                    asyncio.run(run_test())

                    # shutdown 仍应被调用
                    mock_shutdown.assert_called_once()


class TestLifespanPollerStop:
    """poller.stop() 调用验证测试"""

    def test_lifespan_calls_poller_stop_on_shutdown(self) -> None:
        """关闭时应调用 poller.stop()"""
        with patch("src.composition_root.bootstrap"):
            with patch("src.composition_root.shutdown"):
                with patch("src.domain.ports.resolver.get_resolver") as mock_get_resolver:
                    mock_resolver = MagicMock()
                    mock_poller = MagicMock()
                    mock_poller.run = AsyncMock(return_value=None)
                    mock_poller.stop = MagicMock()
                    mock_rabbitmq_publisher = MagicMock()
                    mock_rabbitmq_publisher.connect = AsyncMock(return_value=None)
                    mock_resolver.resolve.side_effect = lambda name: {
                        "rabbitmq_publisher": mock_rabbitmq_publisher,
                        "outbox_poller": mock_poller,
                    }[name]
                    mock_get_resolver.return_value = mock_resolver

                    app = FastAPI()

                    async def run_test():
                        async with _lifespan(app):
                            pass

                    asyncio.run(run_test())

                    mock_poller.stop.assert_called_once()


class TestCreateAppFactory:
    """create_app 工厂函数测试"""

    def test_create_app_returns_fastapi_instance(self) -> None:
        """create_app 应返回 FastAPI 实例"""
        app = create_app()
        assert isinstance(app, FastAPI)

    def test_create_app_has_lifespan(self) -> None:
        """create_app 返回的 app 应有 lifespan 管理"""
        app = create_app()
        assert app.router.lifespan_context is not None
