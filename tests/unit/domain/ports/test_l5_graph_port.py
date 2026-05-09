"""L5GraphPort Protocol Interface Tests."""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock

from src.domain.ports.l5_graph import L5GraphPort


class TestL5GraphPortSignature:
    """Structural signature tests — verify async contract."""

    def test_all_methods_are_async(self) -> None:
        """All methods should be async."""
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
            assert inspect.iscoroutinefunction(method), f"{method_name} must be async"


class TestL5GraphPortMockBehavior:
    """Mock behavior tests — verify Protocol contract via spec约束."""

    async def test_mock_create_entity_verified(self):
        """Mock create_entity should be verifiable."""
        mock = AsyncMock(spec=L5GraphPort)
        mock.create_entity.return_value = {"memory_id": "id-1", "type": "user"}

        result = await mock.create_entity("id-1", "user", {"name": "test"})
        assert result["memory_id"] == "id-1"
        mock.create_entity.assert_called_once()

    async def test_mock_get_entity_verified(self):
        """Mock get_entity should be verifiable."""
        mock = AsyncMock(spec=L5GraphPort)
        mock.get_entity.return_value = {"memory_id": "id-1", "type": "user"}

        result = await mock.get_entity("id-1")
        assert result["memory_id"] == "id-1"
        mock.get_entity.assert_called_once_with("id-1")

    async def test_mock_delete_entity_verified(self):
        """Mock delete_entity should be verifiable."""
        mock = AsyncMock(spec=L5GraphPort)
        mock.delete_entity.return_value = True

        result = await mock.delete_entity("id-1")
        assert result is True
        mock.delete_entity.assert_called_once_with("id-1")

    async def test_mock_create_relationship_verified(self):
        """Mock create_relationship should be verifiable."""
        mock = AsyncMock(spec=L5GraphPort)
        mock.create_relationship.return_value = {"source": "id-1", "target": "id-2", "type": "RELATES_TO"}

        result = await mock.create_relationship("id-1", "id-2", "RELATES_TO", {})
        assert result["source"] == "id-1"
        mock.create_relationship.assert_called_once()

    async def test_mock_delete_relationship_verified(self):
        """Mock delete_relationship should be verifiable."""
        mock = AsyncMock(spec=L5GraphPort)
        mock.delete_relationship.return_value = True

        result = await mock.delete_relationship("id-1", "id-2", "RELATES_TO")
        assert result is True
        mock.delete_relationship.assert_called_once_with("id-1", "id-2", "RELATES_TO")

    async def test_mock_find_related_verified(self):
        """Mock find_related should be verifiable."""
        mock = AsyncMock(spec=L5GraphPort)
        mock.find_related.return_value = [{"memory_id": "id-2"}]

        result = await mock.find_related("id-1", 2, "RELATES_TO")
        assert len(result) == 1
        mock.find_related.assert_called_once_with("id-1", 2, "RELATES_TO")

    async def test_mock_execute_query_verified(self):
        """Mock execute_query should be verifiable."""
        mock = AsyncMock(spec=L5GraphPort)
        mock.execute_query.return_value = [{"n": {"id": "id-1"}}]

        result = await mock.execute_query("MATCH (n) RETURN n", {"limit": 10})
        assert len(result) == 1
        mock.execute_query.assert_called_once()

    async def test_mock_execute_write_query_verified(self):
        """Mock execute_write_query should be verifiable."""
        mock = AsyncMock(spec=L5GraphPort)
        mock.execute_write_query.return_value = [{"created": True}]

        result = await mock.execute_write_query("CREATE (n:Memory {id: $id})", {"id": "id-1"})
        assert result[0]["created"] is True
        mock.execute_write_query.assert_called_once()
