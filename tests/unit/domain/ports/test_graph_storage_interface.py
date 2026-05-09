"""GraphManager and GraphStorage Protocol Interface Tests."""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock

from src.domain.ports.graph_storage import GraphManager, GraphStorage


class TestGraphManagerSignature:
    """Structural signature tests — verify async contract."""

    def test_all_methods_are_async(self) -> None:
        """All methods should be async."""
        for method_name in ["create_node", "delete_node", "get_node", "create_relationship", "delete_relationship"]:
            method = getattr(GraphManager, method_name)
            assert inspect.iscoroutinefunction(method), f"{method_name} must be async"


class TestGraphManagerMockBehavior:
    """Mock behavior tests — verify Protocol contract via spec约束."""

    async def test_mock_create_node_verified(self):
        """Mock create_node should be verifiable."""
        mock = AsyncMock(spec=GraphManager)
        mock.create_node.return_value = {"id": "node-1", "type": "person"}

        result = await mock.create_node("node-1", "person", {"Name": "Alice"})
        assert result["id"] == "node-1"
        mock.create_node.assert_called_once()

    async def test_mock_get_node_verified(self):
        """Mock get_node should be verifiable."""
        mock = AsyncMock(spec=GraphManager)
        mock.get_node.return_value = {"id": "node-1", "type": "person", "properties": {"Name": "Alice"}}

        result = await mock.get_node("node-1")
        assert result["id"] == "node-1"
        mock.get_node.assert_called_once_with("node-1")

    async def test_mock_delete_node_verified(self):
        """Mock delete_node should be verifiable."""
        mock = AsyncMock(spec=GraphManager)
        mock.delete_node.return_value = True

        result = await mock.delete_node("node-1")
        assert result is True
        mock.delete_node.assert_called_once_with("node-1")

    async def test_mock_create_relationship_verified(self):
        """Mock create_relationship should be verifiable."""
        mock = AsyncMock(spec=GraphManager)
        mock.create_relationship.return_value = {"source": "node-1", "target": "node-2", "type": "KNOWS"}

        result = await mock.create_relationship("node-1", "node-2", "KNOWS", {"since": 2020})
        assert result["source"] == "node-1"
        mock.create_relationship.assert_called_once()

    async def test_mock_delete_relationship_verified(self):
        """Mock delete_relationship should be verifiable."""
        mock = AsyncMock(spec=GraphManager)
        mock.delete_relationship.return_value = True

        result = await mock.delete_relationship("node-1", "node-2", "KNOWS")
        assert result is True
        mock.delete_relationship.assert_called_once_with("node-1", "node-2", "KNOWS")


class TestGraphStorageSignature:
    """Structural signature tests — verify async contract."""

    def test_all_methods_are_async(self) -> None:
        """All methods should be async."""
        for method_name in ["execute_query", "execute_write_query", "find_path", "get_neighbors"]:
            method = getattr(GraphStorage, method_name)
            assert inspect.iscoroutinefunction(method), f"{method_name} must be async"


class TestGraphStorageMockBehavior:
    """Mock behavior tests — verify Protocol contract via spec约束."""

    async def test_mock_execute_query_verified(self):
        """Mock execute_query should be verifiable."""
        mock = AsyncMock(spec=GraphStorage)
        mock.execute_query.return_value = [{"n": {"id": "node-1"}}]

        result = await mock.execute_query("MATCH (n) RETURN n", {"limit": 10})
        assert len(result) == 1
        mock.execute_query.assert_called_once()

    async def test_mock_execute_write_query_verified(self):
        """Mock execute_write_query should be verifiable."""
        mock = AsyncMock(spec=GraphStorage)
        mock.execute_write_query.return_value = [{"created": True}]

        result = await mock.execute_write_query("CREATE (n:Person {id: $id})", {"id": "node-1"})
        assert result[0]["created"] is True
        mock.execute_write_query.assert_called_once()

    async def test_mock_find_path_verified(self):
        """Mock find_path should be verifiable."""
        mock = AsyncMock(spec=GraphStorage)
        mock.find_path.return_value = [{"nodes": ["node-1", "node-2"], "relationships": ["KNOWS"]}]

        result = await mock.find_path("node-1", "node-2", {"max_depth": 3})
        assert len(result) == 1
        mock.find_path.assert_called_once()

    async def test_mock_get_neighbors_verified(self):
        """Mock get_neighbors should be verifiable."""
        mock = AsyncMock(spec=GraphStorage)
        mock.get_neighbors.return_value = [{"id": "node-2", "type": "person", "relationship": "KNOWS"}]

        result = await mock.get_neighbors("node-1", "KNOWS", {"limit": 10})
        assert len(result) == 1
        mock.get_neighbors.assert_called_once()
