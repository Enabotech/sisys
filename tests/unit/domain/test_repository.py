"""Tests for BaseRepository interface."""

import uuid
from typing import Any

import pytest

from src.domain.repositories.base import BaseRepository


class TestBaseRepositoryAbstract:
    """P1-07 Fix: Test BaseRepository uses @abstractmethod."""

    def test_cannot_instantiate_base_repository_directly(self):
        """BaseRepository is abstract and cannot be instantiated."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            BaseRepository()  # type: ignore

    def test_cannot_instantiate_unimplemented_subclass(self):
        """A subclass that doesn't implement all methods cannot be instantiated."""

        class IncompleteRepo(BaseRepository):
            pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteRepo()  # type: ignore

    def test_can_instantiate_fully_implemented_subclass(self):
        """A subclass that implements all methods can be instantiated."""

        class InMemoryRepo(BaseRepository):
            def __init__(self) -> None:
                self._store: dict = {}

            def get_by_id(self, id: uuid.UUID) -> Any:
                return self._store.get(id)

            def save(self, entity: Any) -> None:
                self._store[entity.id] = entity

            def delete(self, id: uuid.UUID) -> None:
                self._store.pop(id, None)

            def list_all(self) -> list:
                return list(self._store.values())

        # This should not raise
        repo = InMemoryRepo()
        assert repo is not None
