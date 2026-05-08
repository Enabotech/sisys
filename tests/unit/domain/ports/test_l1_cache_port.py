"""L1CachePort ABC 接口测试。

验证 L1CachePort ABC 定义了正确的抽象方法签名。
"""

from __future__ import annotations

import inspect

from src.domain.ports.l1_cache import L1CachePort


class TestL1CachePortInterface:
    """L1CachePort 接口测试。"""

    def test_port_is_abc(self) -> None:
        """L1CachePort 应为 ABC 类。"""
        assert inspect.isclass(L1CachePort)
        # ABC classes have _is_protocol or __abstractmethods__
        assert hasattr(L1CachePort, "__abstractmethods__")

    def test_protocol_has_required_methods(self) -> None:
        """L1CachePort 应定义所有必需的抽象方法。"""
        assert hasattr(L1CachePort, "get")
        assert hasattr(L1CachePort, "set")
        assert hasattr(L1CachePort, "delete")
        assert hasattr(L1CachePort, "invalidate_pattern")

    def test_methods_are_abstract(self) -> None:
        """方法应标记为抽象。"""
        assert getattr(L1CachePort.get, "__isabstractmethod__", False) is True
        assert getattr(L1CachePort.set, "__isabstractmethod__", False) is True
        assert getattr(L1CachePort.delete, "__isabstractmethod__", False) is True
        assert getattr(L1CachePort.invalidate_pattern, "__isabstractmethod__", False) is True

    def test_get_signature(self) -> None:
        """get 方法应有正确的签名。"""
        sig = inspect.signature(L1CachePort.get)
        params = list(sig.parameters.keys())
        assert "memory_type" in params
        assert "owner_id" in params
        assert "name" in params

    def test_set_signature(self) -> None:
        """set 方法应有正确的签名。"""
        sig = inspect.signature(L1CachePort.set)
        params = list(sig.parameters.keys())
        assert "memory_type" in params
        assert "owner_id" in params
        assert "name" in params
        assert "content" in params
        assert "ttl" in params

    def test_delete_signature(self) -> None:
        """delete 方法应有正确的签名。"""
        sig = inspect.signature(L1CachePort.delete)
        params = list(sig.parameters.keys())
        assert "memory_type" in params
        assert "owner_id" in params
        assert "name" in params

    def test_invalidate_pattern_signature(self) -> None:
        """invalidate_pattern 方法应有正确的签名。"""
        sig = inspect.signature(L1CachePort.invalidate_pattern)
        params = list(sig.parameters.keys())
        assert "memory_type" in params
        assert "owner_id" in params

    def test_port_is_not_instantiable(self) -> None:
        """L1CachePort 是 ABC，不应能直接实例化。"""
        # 尝试实例化应该失败（因为是 ABC）
        try:
            L1CachePort()  # type: ignore[abstract]
            assert False, "Should not be able to instantiate ABC"
        except TypeError:
            pass  # Expected

    def test_all_methods_are_async(self) -> None:
        """所有方法应为 async def。"""
        # 检查方法是否是协程函数
        import asyncio

        for method_name in ["get", "set", "delete", "invalidate_pattern"]:
            method = getattr(L1CachePort, method_name)
            assert asyncio.iscoroutinefunction(method), f"{method_name} should be async"
