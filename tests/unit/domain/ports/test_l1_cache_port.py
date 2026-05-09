"""L1CachePort Protocol Interface Tests."""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock

from src.domain.ports.l1_cache import L1CachePort


class TestL1CachePortSignature:
    """Structural signature tests — verify async contract."""

    def test_all_methods_are_async(self) -> None:
        """All methods should be async."""
        for method_name in ["get", "set", "delete", "invalidate_pattern"]:
            method = getattr(L1CachePort, method_name)
            assert inspect.iscoroutinefunction(method), f"{method_name} must be async"


class TestL1CachePortMockBehavior:
    """Mock behavior tests — verify Protocol contract via spec约束."""

    async def test_mock_get_verified(self):
        """Mock get should be verifiable."""
        mock = AsyncMock(spec=L1CachePort)
        mock.get.return_value = "cached_value"

        result = await mock.get("user", "owner-123", "memory-name")
        assert result == "cached_value"
        mock.get.assert_called_once_with("user", "owner-123", "memory-name")

    async def test_mock_set_verified(self):
        """Mock set should be verifiable."""
        mock = AsyncMock(spec=L1CachePort)
        mock.set.return_value = True

        result = await mock.set("user", "owner-123", "memory-name", "content", 3600)
        assert result is True
        mock.set.assert_called_once_with("user", "owner-123", "memory-name", "content", 3600)

    async def test_mock_delete_verified(self):
        """Mock delete should be verifiable."""
        mock = AsyncMock(spec=L1CachePort)
        mock.delete.return_value = True

        await mock.delete("user", "owner-123", "memory-name")
        mock.delete.assert_called_once_with("user", "owner-123", "memory-name")

    async def test_mock_invalidate_pattern_verified(self):
        """Mock invalidate_pattern should be verifiable."""
        mock = AsyncMock(spec=L1CachePort)
        mock.invalidate_pattern.return_value = 5

        result = await mock.invalidate_pattern("user", "owner-123")
        assert result == 5
        mock.invalidate_pattern.assert_called_once_with("user", "owner-123")
