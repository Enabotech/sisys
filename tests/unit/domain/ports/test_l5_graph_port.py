"""L5GraphPort ABC 接口测试。

验证 L5GraphPort ABC 定义了正确的抽象方法签名。
"""

from __future__ import annotations

import inspect

from src.domain.ports.l5_graph import L5GraphPort


class TestL5GraphPortInterface:
    """L5GraphPort 接口测试。"""

    def test_port_is_abc(self) -> None:
        """L5GraphPort 应为 ABC 类。"""
        assert inspect.isclass(L5GraphPort)
        assert hasattr(L5GraphPort, "__abstractmethods__")

    def test_protocol_has_required_methods(self) -> None:
        """L5GraphPort 应定义所有必需的抽象方法。"""
        assert hasattr(L5GraphPort, "create_entity")
        assert hasattr(L5GraphPort, "get_entity")
        assert hasattr(L5GraphPort, "delete_entity")
        assert hasattr(L5GraphPort, "create_relationship")
        assert hasattr(L5GraphPort, "delete_relationship")
        assert hasattr(L5GraphPort, "find_related")
        assert hasattr(L5GraphPort, "execute_query")
        assert hasattr(L5GraphPort, "execute_write_query")

    def test_methods_are_abstract(self) -> None:
        """方法应标记为抽象。"""
        for method_name in [
            "create_entity",
            "get_entity",
            "delete_entity",
            "create_relationship",
            "delete_relationship",
            "find_related",
            "execute_query",
            "execute_write_query",
        ]:
            method = getattr(L5GraphPort, method_name)
            assert getattr(method, "__isabstractmethod__", False) is True, f"{method_name} should be abstract"

    def test_create_entity_signature(self) -> None:
        """create_entity 方法应有正确的签名。"""
        sig = inspect.signature(L5GraphPort.create_entity)
        params = list(sig.parameters.keys())
        assert "memory_id" in params
        assert "entity_type" in params
        assert "properties" in params

    def test_get_entity_signature(self) -> None:
        """get_entity 方法应有正确的签名。"""
        sig = inspect.signature(L5GraphPort.get_entity)
        params = list(sig.parameters.keys())
        assert "memory_id" in params

    def test_delete_entity_signature(self) -> None:
        """delete_entity 方法应有正确的签名。"""
        sig = inspect.signature(L5GraphPort.delete_entity)
        params = list(sig.parameters.keys())
        assert "memory_id" in params

    def test_create_relationship_signature(self) -> None:
        """create_relationship 方法应有正确的签名。"""
        sig = inspect.signature(L5GraphPort.create_relationship)
        params = list(sig.parameters.keys())
        assert "source_memory_id" in params
        assert "target_memory_id" in params
        assert "relationship_type" in params
        assert "properties" in params

    def test_delete_relationship_signature(self) -> None:
        """delete_relationship 方法应有正确的签名。"""
        sig = inspect.signature(L5GraphPort.delete_relationship)
        params = list(sig.parameters.keys())
        assert "source_memory_id" in params
        assert "target_memory_id" in params
        assert "relationship_type" in params

    def test_find_related_signature(self) -> None:
        """find_related 方法应有正确的签名。"""
        sig = inspect.signature(L5GraphPort.find_related)
        params = list(sig.parameters.keys())
        assert "memory_id" in params
        assert "max_depth" in params
        assert "relationship_type" in params

    def test_execute_query_signature(self) -> None:
        """execute_query 方法应有正确的签名。"""
        sig = inspect.signature(L5GraphPort.execute_query)
        params = list(sig.parameters.keys())
        assert "cypher" in params
        assert "params" in params

    def test_execute_write_query_signature(self) -> None:
        """execute_write_query 方法应有正确的签名。"""
        sig = inspect.signature(L5GraphPort.execute_write_query)
        params = list(sig.parameters.keys())
        assert "cypher" in params
        assert "params" in params

    def test_port_is_not_instantiable(self) -> None:
        """L5GraphPort 是 ABC，不应能直接实例化。"""
        try:
            L5GraphPort()  # type: ignore[abstract]
            assert False, "Should not be able to instantiate ABC"
        except TypeError:
            pass  # Expected

    def test_all_methods_are_async(self) -> None:
        """所有方法应为 async def。"""
        import asyncio

        for method_name in [
            "create_entity",
            "get_entity",
            "delete_entity",
            "create_relationship",
            "delete_relationship",
            "find_related",
            "execute_query",
            "execute_write_query",
        ]:
            method = getattr(L5GraphPort, method_name)
            assert asyncio.iscoroutinefunction(method), f"{method_name} should be async"
