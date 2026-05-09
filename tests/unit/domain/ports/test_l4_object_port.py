"""L4ObjectPort Protocol Interface Tests."""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock

from src.domain.ports.l4_object import L4ObjectPort


class TestL4ObjectPortSignature:
    """Structural signature tests — verify async/sync contract."""

    def test_all_crud_methods_are_async_except_retrieve(self) -> None:
        """store, delete, get_metadata, archive should be async; retrieve is sync."""
        for method_name in ["store", "delete", "get_metadata", "archive"]:
            method = getattr(L4ObjectPort, method_name)
            assert inspect.iscoroutinefunction(method), f"{method_name} should be async"

        method = getattr(L4ObjectPort, "retrieve")
        assert not inspect.iscoroutinefunction(method), "retrieve should NOT be async"


class TestL4ObjectPortMockBehavior:
    """Mock behavior tests — verify Protocol contract via spec约束."""

    async def test_mock_store_verified(self):
        """Mock store should be verifiable."""
        mock = AsyncMock(spec=L4ObjectPort)
        mock.store.return_value = "etag-123"

        result = await mock.store("bucket", "key", "/path/file", "application/pdf", {"tag": "value"})
        assert result == "etag-123"
        mock.store.assert_called_once()

    async def test_mock_delete_verified(self):
        """Mock delete should be verifiable."""
        mock = AsyncMock(spec=L4ObjectPort)
        mock.delete.return_value = True

        result = await mock.delete("bucket", "key", "v1")
        assert result is True
        mock.delete.assert_called_once_with("bucket", "key", "v1")

    async def test_mock_get_metadata_verified(self):
        """Mock get_metadata should be verifiable."""
        mock = AsyncMock(spec=L4ObjectPort)
        mock.get_metadata.return_value = {"Content-Length": 1024}

        result = await mock.get_metadata("bucket", "key", "v1")
        assert result["Content-Length"] == 1024
        mock.get_metadata.assert_called_once()

    async def test_mock_archive_verified(self):
        """Mock archive should be verifiable."""
        mock = AsyncMock(spec=L4ObjectPort)
        mock.archive.return_value = "archived-etag"

        result = await mock.archive("bucket", "key", b"content", 2555)
        assert result == "archived-etag"
        mock.archive.assert_called_once()

    def test_mock_retrieve_verified(self):
        """Mock retrieve should be verifiable (sync method)."""
        mock = MagicMock(spec=L4ObjectPort)
        mock.retrieve.return_value = b"file content"

        result = mock.retrieve("bucket", "key", "v1")
        assert result == b"file content"
        mock.retrieve.assert_called_once_with("bucket", "key", "v1")
