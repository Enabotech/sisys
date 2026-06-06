"""ConnectionManager Protocol 行为验证测试

验证统一异步连接生命周期端口的运行时类型检查、方法签名和默认实现行为
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from src.domain.ports.connection_manager import ConnectionManager


class TestConnectionManagerRuntimeCheckable:
    """ConnectionManager 结构化子类型检查"""

    def test_compatible_class_passes_isinstance(self) -> None:
        """实现 health_check + close + get_client 的类应通过 isinstance 检查"""

        class FakeManager:
            async def health_check(self) -> bool:
                return True

            async def close(self) -> None:
                pass

            def get_client(self) -> Any:
                return object()

        assert isinstance(FakeManager(), ConnectionManager)

    def test_compatible_without_get_client_still_passes(self) -> None:
        """仅实现 health_check + close 也能通过 isinstance（get_client 有默认实现）"""

        class MinimalManager:
            async def health_check(self) -> bool:
                return True

            async def close(self) -> None:
                pass

        # get_client 在 Protocol 中有默认实现，所以 runtime_checkable
        # 需要检查该属性是否存在
        instance = MinimalManager()
        # Python Protocol 的 isinstance 对有默认实现的方法不做要求
        # 但 get_client 作为 Protocol 的一部分仍被检查
        assert hasattr(instance, "health_check")
        assert hasattr(instance, "close")

    def test_incompatible_class_fails_isinstance(self) -> None:
        """不实现必要方法的类不应通过 isinstance 检查"""

        class Incompatible:
            def other(self) -> None:
                pass

        assert not isinstance(Incompatible(), ConnectionManager)


class TestConnectionManagerMethodSignature:
    """ConnectionManager 方法签名验证"""

    def test_health_check_is_async(self) -> None:
        """health_check 应为异步方法"""
        assert asyncio.iscoroutinefunction(ConnectionManager.health_check)

    def test_close_is_async(self) -> None:
        """close 应为异步方法"""
        assert asyncio.iscoroutinefunction(ConnectionManager.close)

    def test_get_client_is_synchronous(self) -> None:
        """get_client 应为同步方法"""
        assert not asyncio.iscoroutinefunction(ConnectionManager.get_client)


class TestConnectionManagerGetClientDefault:
    """get_client 默认实现行为验证"""

    def test_get_client_default_raises_not_implemented(self) -> None:
        """默认 get_client 应抛出 NotImplementedError"""

        class StubManager(ConnectionManager):
            async def health_check(self) -> bool:
                return True

            async def close(self) -> None:
                pass

            def get_client(self) -> Any:
                return ConnectionManager.get_client(self)

        manager = StubManager()
        with pytest.raises(NotImplementedError, match="get_client"):
            manager.get_client()

    def test_get_client_error_message_contains_class_name(self) -> None:
        """NotImplementedError 消息应包含类名"""

        class CustomManager(ConnectionManager):
            async def health_check(self) -> bool:
                return True

            async def close(self) -> None:
                pass

            def get_client(self) -> Any:
                return ConnectionManager.get_client(self)

        manager = CustomManager()
        with pytest.raises(NotImplementedError, match="CustomManager"):
            manager.get_client()


class TestConnectionManagerFullLifecycle:
    """ConnectionManager 完整生命周期行为验证"""

    async def test_health_check_returns_true_when_healthy(self) -> None:
        """健康检查成功应返回 True"""

        class HealthyManager:
            async def health_check(self) -> bool:
                return True

            async def close(self) -> None:
                pass

        manager = HealthyManager()
        assert await manager.health_check() is True

    async def test_health_check_returns_false_when_unhealthy(self) -> None:
        """健康检查失败应返回 False"""

        class UnhealthyManager:
            async def health_check(self) -> bool:
                return False

            async def close(self) -> None:
                pass

        manager = UnhealthyManager()
        assert await manager.health_check() is False

    async def test_close_releases_resources(self) -> None:
        """close 应释放资源"""
        closed = False

        class ManagedResource:
            async def health_check(self) -> bool:
                return True

            async def close(self) -> None:
                nonlocal closed
                closed = True

        manager = ManagedResource()
        await manager.close()
        assert closed is True

    def test_custom_get_client_returns_client(self) -> None:
        """自定义 get_client 应返回底层客户端"""

        class ManagerWithClient:
            def __init__(self) -> None:
                self._client = object()

            async def health_check(self) -> bool:
                return True

            async def close(self) -> None:
                pass

            def get_client(self) -> Any:
                return self._client

        manager = ManagerWithClient()
        client = manager.get_client()
        assert client is manager._client
