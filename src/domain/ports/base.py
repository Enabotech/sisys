"""Base repository interface."""

from __future__ import annotations

from typing import Generic, Protocol, TypeVar
from uuid import UUID

T = TypeVar("T")


class BaseRepository(Generic[T], Protocol):
    """Generic repository interface for domain entities.

    This interface is defined in the domain layer and implemented
    in the infrastructure layer (Dependency Inversion Principle).
    """

    def get_by_id(self, id: UUID) -> T | None:
        """Retrieve an entity by its ID.

        Args:
            id: The unique identifier of the entity.

        Returns:
            The entity if found, None otherwise.
        """

    def save(self, entity: T) -> None:
        """Save an entity.

        Args:
            entity: The entity to save or update.
        """

    def delete(self, id: UUID) -> None:
        """Delete an entity by its ID.

        Args:
            id: The unique identifier of the entity to delete.
        """

    def list_all(self) -> list[T]:
        """List all entities.

        Returns:
            A list of all entities.
        """
