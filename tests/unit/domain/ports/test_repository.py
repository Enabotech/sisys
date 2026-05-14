"""Tests for BaseRepository interface."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from src.domain.ports.l2_rdb import BaseRepository


class TestBaseRepositorySignature:
    """Structural signature tests — verify method contract."""

    def test_get_by_id_exists(self) -> None:
        """get_by_id method must exist."""
        assert hasattr(BaseRepository, "get_by_id")

    def test_save_exists(self) -> None:
        """save method must exist."""
        assert hasattr(BaseRepository, "save")

    def test_delete_exists(self) -> None:
        """delete method must exist."""
        assert hasattr(BaseRepository, "delete")

    def test_list_all_exists(self) -> None:
        """list_all method must exist."""
        assert hasattr(BaseRepository, "list_all")


class TestBaseRepositoryMockBehavior:
    """Mock behavior tests — verify Protocol contract via spec constraint."""

    def test_mock_get_by_id_verified(self) -> None:
        """Mock get_by_id should be verifiable."""
        mock = MagicMock(spec=BaseRepository)
        mock.get_by_id.return_value = {"id": "user-1", "name": "Alice"}

        result = mock.get_by_id(uuid.uuid4())
        assert result["id"] == "user-1"
        mock.get_by_id.assert_called_once()

    def test_mock_save_verified(self) -> None:
        """Mock save should be verifiable."""
        mock = MagicMock(spec=BaseRepository)
        mock.save.return_value = None

        entity = MagicMock()
        entity.id = uuid.uuid4()
        mock.save(entity)
        mock.save.assert_called_once_with(entity)

    def test_mock_delete_verified(self) -> None:
        """Mock delete should be verifiable."""
        mock = MagicMock(spec=BaseRepository)
        mock.delete.return_value = None

        test_id = uuid.uuid4()
        mock.delete(test_id)
        mock.delete.assert_called_once_with(test_id)

    def test_mock_list_all_verified(self) -> None:
        """Mock list_all should be verifiable."""
        mock = MagicMock(spec=BaseRepository)
        mock.list_all.return_value = [{"id": "user-1"}, {"id": "user-2"}]

        result = mock.list_all()
        assert len(result) == 2
        mock.list_all.assert_called_once()
