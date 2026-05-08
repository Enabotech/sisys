"""L4ObjectPort ABC 接口测试。

验证 L4ObjectPort ABC 定义了正确的抽象方法签名。
"""

from __future__ import annotations

import inspect

from src.domain.ports.l4_object import L4ObjectPort


class TestL4ObjectPortInterface:
    """L4ObjectPort 接口测试。"""

    def test_port_is_abc(self) -> None:
        """L4ObjectPort 应为 ABC 类。"""
        assert inspect.isclass(L4ObjectPort)
        assert hasattr(L4ObjectPort, "__abstractmethods__")

    def test_protocol_has_required_methods(self) -> None:
        """L4ObjectPort 应定义所有必需的抽象方法。"""
        assert hasattr(L4ObjectPort, "store")
        assert hasattr(L4ObjectPort, "retrieve")
        assert hasattr(L4ObjectPort, "delete")
        assert hasattr(L4ObjectPort, "get_metadata")
        assert hasattr(L4ObjectPort, "archive")

    def test_methods_are_abstract(self) -> None:
        """方法应标记为抽象。"""
        assert getattr(L4ObjectPort.store, "__isabstractmethod__", False) is True
        assert getattr(L4ObjectPort.retrieve, "__isabstractmethod__", False) is True
        assert getattr(L4ObjectPort.delete, "__isabstractmethod__", False) is True
        assert getattr(L4ObjectPort.get_metadata, "__isabstractmethod__", False) is True
        assert getattr(L4ObjectPort.archive, "__isabstractmethod__", False) is True

    def test_store_signature(self) -> None:
        """store 方法应有正确的签名。"""
        sig = inspect.signature(L4ObjectPort.store)
        params = list(sig.parameters.keys())
        assert "bucket_type" in params
        assert "object_key" in params
        assert "file_path" in params
        assert "content_type" in params
        assert "tags" in params

    def test_retrieve_signature(self) -> None:
        """retrieve 方法应有正确的签名。"""
        sig = inspect.signature(L4ObjectPort.retrieve)
        params = list(sig.parameters.keys())
        assert "bucket_type" in params
        assert "object_key" in params
        assert "version_id" in params

    def test_delete_signature(self) -> None:
        """delete 方法应有正确的签名。"""
        sig = inspect.signature(L4ObjectPort.delete)
        params = list(sig.parameters.keys())
        assert "bucket_type" in params
        assert "object_key" in params
        assert "version_id" in params

    def test_get_metadata_signature(self) -> None:
        """get_metadata 方法应有正确的签名。"""
        sig = inspect.signature(L4ObjectPort.get_metadata)
        params = list(sig.parameters.keys())
        assert "bucket_type" in params
        assert "object_key" in params
        assert "version_id" in params

    def test_archive_signature(self) -> None:
        """archive 方法应有正确的签名。"""
        sig = inspect.signature(L4ObjectPort.archive)
        params = list(sig.parameters.keys())
        assert "bucket_type" in params
        assert "object_key" in params
        assert "content" in params
        assert "retention_days" in params

    def test_port_is_not_instantiable(self) -> None:
        """L4ObjectPort 是 ABC，不应能直接实例化。"""
        try:
            L4ObjectPort()  # type: ignore[abstract]
            assert False, "Should not be able to instantiate ABC"
        except TypeError:
            pass  # Expected

    def test_all_crud_methods_are_async_except_retrieve(self) -> None:
        """除 retrieve 外所有方法应为 async def。"""
        import asyncio

        # store, delete, get_metadata, archive 应是异步
        for method_name in ["store", "delete", "get_metadata", "archive"]:
            method = getattr(L4ObjectPort, method_name)
            assert asyncio.iscoroutinefunction(method), f"{method_name} should be async"

        # retrieve 是同步迭代器
        method = getattr(L4ObjectPort, "retrieve")
        assert not asyncio.iscoroutinefunction(method), "retrieve should not be async"
