"""L1CachePort Protocol Interface Tests."""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock

from src.domain.ports.l1_cache import L1CachePort


class TestL1CachePortSignature:
    """Structural signature tests — verify async contract."""

    def test_all_methods_are_async(self) -> None:
        """All methods should be async."""
        for method_name in ["get", "set", "delete", "exists", "delete_pattern", "set_with_ttl"]:
            method = getattr(L1CachePort, method_name)
            assert inspect.iscoroutinefunction(method), f"{method_name} must be async"


class TestL1CachePortMockBehavior:
    """Mock behavior tests — verify Protocol contract via spec."""

    async def test_mock_get_verified(self):
        """Mock get should be verifiable."""
        mock = AsyncMock(spec=L1CachePort)
        mock.get.return_value = "cached_value"

        result = await mock.get("some:key")
        assert result == "cached_value"
        mock.get.assert_called_once_with("some:key")

    async def test_mock_set_verified(self):
        """Mock set should be verifiable."""
        mock = AsyncMock(spec=L1CachePort)
        mock.set.return_value = True

        result = await mock.set("some:key", "value", 3600)
        assert result is True
        mock.set.assert_called_once_with("some:key", "value", 3600)

    async def test_mock_delete_verified(self):
        """Mock delete should be verifiable."""
        mock = AsyncMock(spec=L1CachePort)
        mock.delete.return_value = True

        await mock.delete("some:key")
        mock.delete.assert_called_once_with("some:key")

    async def test_mock_exists_verified(self):
        """Mock exists should be verifiable."""
        mock = AsyncMock(spec=L1CachePort)
        mock.exists.return_value = True

        result = await mock.exists("some:key")
        assert result is True
        mock.exists.assert_called_once_with("some:key")

    async def test_mock_delete_pattern_verified(self):
        """Mock delete_pattern should be verifiable."""
        mock = AsyncMock(spec=L1CachePort)
        mock.delete_pattern.return_value = 5

        result = await mock.delete_pattern("memory:user:123:*")
        assert result == 5
        mock.delete_pattern.assert_called_once_with("memory:user:123:*")

    async def test_mock_set_with_ttl_verified(self):
        """Mock set_with_ttl should be verifiable."""
        mock = AsyncMock(spec=L1CachePort)
        mock.set_with_ttl.return_value = True

        result = await mock.set_with_ttl("some:key", "value", 3600)
        assert result is True
        mock.set_with_ttl.assert_called_once_with("some:key", "value", 3600)
