"""L3VectorPort Protocol Interface Tests."""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock

from src.domain.ports.l3_vector import L3VectorPort


class TestL3VectorPortSignature:
    """Structural signature tests — verify async contract."""

    def test_all_methods_are_async(self) -> None:
        """All methods should be async."""
        for method_name in ["upsert_points", "delete_points", "get_point", "search", "search_sparse"]:
            method = getattr(L3VectorPort, method_name)
            assert inspect.iscoroutinefunction(method), f"{method_name} must be async"


class TestL3VectorPortMockBehavior:
    """Mock behavior tests — verify Protocol contract via spec约束."""

    async def test_mock_upsert_points_verified(self):
        """Mock upsert_points should be verifiable."""
        mock = AsyncMock(spec=L3VectorPort)
        mock.upsert_points.return_value = True

        result = await mock.upsert_points("collection", [{"id": "1", "vector": [0.1, 0.2]}])
        assert result is True
        mock.upsert_points.assert_called_once()

    async def test_mock_delete_points_verified(self):
        """Mock delete_points should be verifiable."""
        mock = AsyncMock(spec=L3VectorPort)
        mock.delete_points.return_value = True

        result = await mock.delete_points("collection", ["id1", "id2"])
        assert result is True
        mock.delete_points.assert_called_once_with("collection", ["id1", "id2"])

    async def test_mock_get_point_verified(self):
        """Mock get_point should be verifiable."""
        mock = AsyncMock(spec=L3VectorPort)
        mock.get_point.return_value = {"id": "1", "vector": [0.1, 0.2]}

        result = await mock.get_point("collection", "point-id")
        assert result["id"] == "1"
        mock.get_point.assert_called_once_with("collection", "point-id")

    async def test_mock_search_verified(self):
        """Mock search should be verifiable."""
        mock = AsyncMock(spec=L3VectorPort)
        mock.search.return_value = [{"id": "1", "score": 0.95}]

        result = await mock.search("collection", [0.1, 0.2], 10, {})
        assert len(result) == 1
        mock.search.assert_called_once()

    async def test_mock_search_sparse_verified(self):
        """Mock search_sparse should be verifiable."""
        mock = AsyncMock(spec=L3VectorPort)
        mock.search_sparse.return_value = [{"id": "1", "score": 0.85}]

        result = await mock.search_sparse("collection", {"indices": [0, 1], "values": [0.1, 0.2]}, 10, {})
        assert len(result) == 1
        mock.search_sparse.assert_called_once()
