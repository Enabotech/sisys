"""Tests for L2RdbPort (formerly BaseRepository) interface."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

from src.domain.ports.l2_rdb import L2RdbPort


class TestL2RdbPortSignature:
    """Structural signature tests — verify method contract."""

    def test_get_by_id_exists(self) -> None:
        """get_by_id method must exist."""
        assert hasattr(L2RdbPort, "get_by_id")

    def test_save_exists(self) -> None:
        """save method must exist."""
        assert hasattr(L2RdbPort, "save")

    def test_delete_exists(self) -> None:
        """delete method must exist."""
        assert hasattr(L2RdbPort, "delete")

    def test_list_all_exists(self) -> None:
        """list_all method must exist."""
        assert hasattr(L2RdbPort, "list_all")


class TestL2RdbPortMockBehavior:
    """Mock behavior tests — verify Protocol contract via spec constraint."""

    async def test_mock_get_by_id_verified(self) -> None:
        """Mock get_by_id should be verifiable (async)."""
        mock = AsyncMock(spec=L2RdbPort)
        mock.get_by_id.return_value = {"id": "user-1", "name": "Alice"}

        result = await mock.get_by_id(uuid.uuid4())
        assert result["id"] == "user-1"
        mock.get_by_id.assert_called_once()

    async def test_mock_save_verified(self) -> None:
        """Mock save should be verifiable (async)."""
        mock = AsyncMock(spec=L2RdbPort)

        entity = MagicMock()
        entity.id = uuid.uuid4()
        await mock.save(entity)
        mock.save.assert_called_once_with(entity)

    async def test_mock_delete_verified(self) -> None:
        """Mock delete should be verifiable (async)."""
        mock = AsyncMock(spec=L2RdbPort)

        test_id = uuid.uuid4()
        await mock.delete(test_id)
        mock.delete.assert_called_once_with(test_id)

    async def test_mock_list_all_verified(self) -> None:
        """Mock list_all should be verifiable (async)."""
        mock = AsyncMock(spec=L2RdbPort)
        mock.list_all.return_value = [{"id": "user-1"}, {"id": "user-2"}]

        result = await mock.list_all()
        assert len(result) == 2
        mock.list_all.assert_called_once()
