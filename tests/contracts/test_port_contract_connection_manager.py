"""ConnectionManager 端口契约测试

验证 ConnectionManager Protocol 的结构化子类型合规性。
所有异步存储管理器通过此协议统一生命周期。
"""

from __future__ import annotations

import inspect

from src.domain.ports.connection_manager import ConnectionManager


class TestConnectionManagerContract:
    """测试 ConnectionManager 端口契约"""

    def test_protocol_is_runtime_checkable(self) -> None:
        """验证 Protocol 使用 @runtime_checkable 装饰器"""
        assert hasattr(ConnectionManager, "_is_runtime_protocol")
        assert ConnectionManager._is_runtime_protocol is True  # type: ignore[attr-defined]

    def test_health_check_method_exists(self) -> None:
        """验证 health_check 方法存在且为异步"""
        assert hasattr(ConnectionManager, "health_check")
        method = getattr(ConnectionManager, "health_check")
        assert callable(method)
        assert inspect.iscoroutinefunction(method)

    def test_close_method_exists(self) -> None:
        """验证 close 方法存在且为异步"""
        assert hasattr(ConnectionManager, "close")
        method = getattr(ConnectionManager, "close")
        assert callable(method)
        assert inspect.iscoroutinefunction(method)

    def test_get_client_method_exists(self) -> None:
        """验证 get_client 方法存在"""
        assert hasattr(ConnectionManager, "get_client")
        method = getattr(ConnectionManager, "get_client")
        assert callable(method)

    def test_get_client_default_raises_not_implemented_error(self) -> None:
        """验证未重写 get_client 的协议子类默认抛出 NotImplementedError"""

        class MinimalManager(ConnectionManager):
            async def health_check(self) -> bool:
                return True

            async def close(self) -> None:
                pass

            def get_client(self):
                # 不重写，调用协议默认实现（抛 NotImplementedError）
                return super().get_client()

        mgr = MinimalManager()
        try:
            mgr.get_client()
            assert False, "应该抛出 NotImplementedError"
        except NotImplementedError as e:
            assert "get_client" in str(e)

    def test_compliant_implementation(self) -> None:
        """验证合规实现可通过 isinstance 检查"""

        class MockConnectionManager:
            async def health_check(self) -> bool:
                return True

            async def close(self) -> None:
                pass

            def get_client(self):
                return None

        mgr = MockConnectionManager()
        assert isinstance(mgr, ConnectionManager)

    def test_noncompliant_implementation_fails(self) -> None:
        """验证不合规实现无法通过 isinstance 检查"""

        class BadManager:
            pass

        assert not isinstance(BadManager(), ConnectionManager)


__all__ = ["TestConnectionManagerContract"]
