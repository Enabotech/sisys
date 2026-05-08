"""L3VectorPort ABC 接口测试。

验证 L3VectorPort ABC 定义了正确的抽象方法签名。
"""

from __future__ import annotations

import inspect

from src.domain.ports.l3_vector import L3VectorPort


class TestL3VectorPortInterface:
    """L3VectorPort 接口测试。"""

    def test_port_is_abc(self) -> None:
        """L3VectorPort 应为 ABC 类。"""
        assert inspect.isclass(L3VectorPort)
        assert hasattr(L3VectorPort, "__abstractmethods__")

    def test_protocol_has_required_methods(self) -> None:
        """L3VectorPort 应定义所有必需的抽象方法。"""
        assert hasattr(L3VectorPort, "upsert_points")
        assert hasattr(L3VectorPort, "delete_points")
        assert hasattr(L3VectorPort, "get_point")
        assert hasattr(L3VectorPort, "search")
        assert hasattr(L3VectorPort, "search_sparse")

    def test_methods_are_abstract(self) -> None:
        """方法应标记为抽象。"""
        assert getattr(L3VectorPort.upsert_points, "__isabstractmethod__", False) is True
        assert getattr(L3VectorPort.delete_points, "__isabstractmethod__", False) is True
        assert getattr(L3VectorPort.get_point, "__isabstractmethod__", False) is True
        assert getattr(L3VectorPort.search, "__isabstractmethod__", False) is True
        assert getattr(L3VectorPort.search_sparse, "__isabstractmethod__", False) is True

    def test_upsert_points_signature(self) -> None:
        """upsert_points 方法应有正确的签名。"""
        sig = inspect.signature(L3VectorPort.upsert_points)
        params = list(sig.parameters.keys())
        assert "collection" in params
        assert "points" in params

    def test_delete_points_signature(self) -> None:
        """delete_points 方法应有正确的签名。"""
        sig = inspect.signature(L3VectorPort.delete_points)
        params = list(sig.parameters.keys())
        assert "collection" in params
        assert "point_ids" in params

    def test_get_point_signature(self) -> None:
        """get_point 方法应有正确的签名。"""
        sig = inspect.signature(L3VectorPort.get_point)
        params = list(sig.parameters.keys())
        assert "collection" in params
        assert "point_id" in params

    def test_search_signature(self) -> None:
        """search 方法应有正确的签名。"""
        sig = inspect.signature(L3VectorPort.search)
        params = list(sig.parameters.keys())
        assert "collection" in params
        assert "query_vector" in params
        assert "limit" in params
        assert "filter_payload" in params

    def test_search_sparse_signature(self) -> None:
        """search_sparse 方法应有正确的签名。"""
        sig = inspect.signature(L3VectorPort.search_sparse)
        params = list(sig.parameters.keys())
        assert "collection" in params
        assert "sparse_vector" in params
        assert "limit" in params
        assert "filter_payload" in params

    def test_port_is_not_instantiable(self) -> None:
        """L3VectorPort 是 ABC，不应能直接实例化。"""
        try:
            L3VectorPort()  # type: ignore[abstract]
            assert False, "Should not be able to instantiate ABC"
        except TypeError:
            pass  # Expected

    def test_all_methods_are_async(self) -> None:
        """所有方法应为 async def。"""
        import asyncio

        for method_name in ["upsert_points", "delete_points", "get_point", "search", "search_sparse"]:
            method = getattr(L3VectorPort, method_name)
            assert asyncio.iscoroutinefunction(method), f"{method_name} should be async"
