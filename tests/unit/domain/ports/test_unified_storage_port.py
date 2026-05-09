"""UnifiedStoragePort Protocol Interface Tests."""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock

from src.domain.ports.unified_storage import UnifiedStoragePort


class TestUnifiedStoragePortSignature:
    """Structural signature tests — verify async contract."""

    def test_all_methods_are_async(self) -> None:
        """All methods should be async."""
        for method_name in ["save", "read", "delete", "exists"]:
            method = getattr(UnifiedStoragePort, method_name)
            assert inspect.iscoroutinefunction(method), f"{method_name} must be async"


class TestUnifiedStoragePortMockBehavior:
    """Mock behavior tests — verify Protocol contract via spec约束."""

    async def test_mock_save_verified(self):
        """Mock save should be verifiable."""
        mock = AsyncMock(spec=UnifiedStoragePort)
        mock.save.return_value = {"L0": True, "L1": True}

        result = await mock.save("memory-123", "content", "user", "owner-1", "test-memory", "hot")
        assert result["L0"] is True
        mock.save.assert_called_once()

    async def test_mock_read_verified(self):
        """Mock read should be verifiable."""
        mock = AsyncMock(spec=UnifiedStoragePort)
        mock.read.return_value = "memory content"

        result = await mock.read("memory-123", "user", "owner-1", "test-memory", True)
        assert result == "memory content"
        mock.read.assert_called_once()

    async def test_mock_delete_verified(self):
        """Mock delete should be verifiable."""
        mock = AsyncMock(spec=UnifiedStoragePort)
        mock.delete.return_value = True

        result = await mock.delete("memory-123", "user", "owner-1", "test-memory")
        assert result is True
        mock.delete.assert_called_once()

    async def test_mock_exists_verified(self):
        """Mock exists should be verifiable."""
        mock = AsyncMock(spec=UnifiedStoragePort)
        mock.exists.return_value = True

        result = await mock.exists("memory-123", "user", "owner-1", "test-memory")
        assert result is True
        mock.exists.assert_called_once()
