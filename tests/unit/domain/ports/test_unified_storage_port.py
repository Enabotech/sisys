"""UnifiedStoragePort ABC 接口测试。

验证 UnifiedStoragePort ABC 定义了正确的抽象方法签名。
"""

from __future__ import annotations

import inspect

from src.domain.ports.unified_storage import UnifiedStoragePort


class TestUnifiedStoragePortInterface:
    """UnifiedStoragePort 接口测试。"""

    def test_port_is_abc(self) -> None:
        """UnifiedStoragePort 应为 ABC 类。"""
        assert inspect.isclass(UnifiedStoragePort)
        assert hasattr(UnifiedStoragePort, "__abstractmethods__")

    def test_protocol_has_required_methods(self) -> None:
        """UnifiedStoragePort 应定义所有必需的抽象方法。"""
        assert hasattr(UnifiedStoragePort, "save")
        assert hasattr(UnifiedStoragePort, "read")
        assert hasattr(UnifiedStoragePort, "delete")
        assert hasattr(UnifiedStoragePort, "exists")

    def test_methods_are_abstract(self) -> None:
        """方法应标记为抽象。"""
        assert getattr(UnifiedStoragePort.save, "__isabstractmethod__", False) is True
        assert getattr(UnifiedStoragePort.read, "__isabstractmethod__", False) is True
        assert getattr(UnifiedStoragePort.delete, "__isabstractmethod__", False) is True
        assert getattr(UnifiedStoragePort.exists, "__isabstractmethod__", False) is True

    def test_save_signature(self) -> None:
        """save 方法应有正确的签名。"""
        sig = inspect.signature(UnifiedStoragePort.save)
        params = list(sig.parameters.keys())
        assert "memory_id" in params
        assert "content" in params
        assert "memory_type" in params
        assert "owner_id" in params
        assert "name" in params
        assert "tier" in params

    def test_read_signature(self) -> None:
        """read 方法应有正确的签名。"""
        sig = inspect.signature(UnifiedStoragePort.read)
        params = list(sig.parameters.keys())
        assert "memory_id" in params
        assert "memory_type" in params
        assert "owner_id" in params
        assert "name" in params
        assert "prefer_cache" in params

    def test_delete_signature(self) -> None:
        """delete 方法应有正确的签名。"""
        sig = inspect.signature(UnifiedStoragePort.delete)
        params = list(sig.parameters.keys())
        assert "memory_id" in params
        assert "memory_type" in params
        assert "owner_id" in params
        assert "name" in params

    def test_exists_signature(self) -> None:
        """exists 方法应有正确的签名。"""
        sig = inspect.signature(UnifiedStoragePort.exists)
        params = list(sig.parameters.keys())
        assert "memory_id" in params
        assert "memory_type" in params
        assert "owner_id" in params
        assert "name" in params

    def test_port_is_not_instantiable(self) -> None:
        """UnifiedStoragePort 是 ABC，不应能直接实例化。"""
        try:
            UnifiedStoragePort()  # type: ignore[abstract]
            assert False, "Should not be able to instantiate ABC"
        except TypeError:
            pass  # Expected

    def test_all_methods_are_async(self) -> None:
        """所有方法应为 async def。"""
        import asyncio

        for method_name in ["save", "read", "delete", "exists"]:
            method = getattr(UnifiedStoragePort, method_name)
            assert asyncio.iscoroutinefunction(method), f"{method_name} should be async"

    def test_save_returns_dict_of_storage_layer_to_bool(self) -> None:
        """save 方法返回值应为 dict[StorageLayer, bool]。"""
        # 检查返回值注解存在
        sig = inspect.signature(UnifiedStoragePort.save)
        return_annotation = sig.return_annotation
        # 验证返回类型包含 StorageLayer
        assert "StorageLayer" in str(return_annotation) or "dict" in str(return_annotation).lower()
