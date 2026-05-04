"""GraphManager and GraphStorage interface tests."""

from __future__ import annotations

import pytest

from src.domain.ports.graph_storage import GraphManager, GraphStorage


class TestGraphManagerInterface:
    """GraphManager 接口测试。"""

    def test_graph_manager_is_abstract(self):
        """GraphManager 是抽象类。"""
        from abc import ABC

        assert issubclass(GraphManager, ABC), "GraphManager must inherit from ABC"

    def test_graph_manager_has_abstract_methods(self):
        """GraphManager 定义了所有抽象方法。"""
        expected_methods = {"create_node", "delete_node", "get_node", "create_relationship", "delete_relationship"}
        abstract_methods = {
            name for name, method in GraphManager.__dict__.items() if getattr(method, "__isabstractmethod__", False)
        }
        assert expected_methods == abstract_methods, f"Expected abstract methods {expected_methods}, found {abstract_methods}"

    def test_cannot_instantiate_graph_manager(self):
        """无法直接实例化 GraphManager。"""
        with pytest.raises(TypeError):
            GraphManager()


class TestGraphStorageInterface:
    """GraphStorage 接口测试。"""

    def test_graph_storage_is_abstract(self):
        """GraphStorage 是抽象类。"""
        from abc import ABC

        assert issubclass(GraphStorage, ABC), "GraphStorage must inherit from ABC"

    def test_graph_storage_has_abstract_methods(self):
        """GraphStorage 定义了所有抽象方法。"""
        expected_methods = {"execute_query", "execute_write_query", "find_path", "get_neighbors"}
        abstract_methods = {
            name for name, method in GraphStorage.__dict__.items() if getattr(method, "__isabstractmethod__", False)
        }
        assert expected_methods == abstract_methods, f"Expected abstract methods {expected_methods}, found {abstract_methods}"

    def test_cannot_instantiate_graph_storage(self):
        """无法直接实例化 GraphStorage。"""
        with pytest.raises(TypeError):
            GraphStorage()
