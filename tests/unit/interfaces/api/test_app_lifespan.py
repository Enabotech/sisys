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
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.interfaces.api.app import _lifespan, create_app


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
                mock_resolver.resolve.return_value = mock_poller
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
                    mock_resolver.resolve.return_value = mock_poller
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
                    mock_resolver.resolve.return_value = mock_poller
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
                    mock_resolver.resolve.return_value = mock_poller
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
                    mock_resolver.resolve.return_value = mock_poller
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
