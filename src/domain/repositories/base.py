"""Base repository interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from uuid import UUID

T = TypeVar("T")


class BaseRepository(Generic[T], ABC):
    """Generic repository interface for domain entities.

    This interface is defined in the domain layer and implemented
    in the infrastructure layer (Dependency Inversion Principle).

    P1-07 Fix: Use ABC + @abstractmethod to prevent instantiation of
    subclasses that haven't implemented all methods.
    """

    @abstractmethod
    def get_by_id(self, id: UUID) -> T | None:
        """Retrieve an entity by its ID.

        Args:
            id: The unique identifier of the entity.

        Returns:
            The entity if found, None otherwise.
        """

    @abstractmethod
    def save(self, entity: T) -> None:
        """Save an entity.

        Args:
            entity: The entity to save or update.
        """

    @abstractmethod
    def delete(self, id: UUID) -> None:
        """Delete an entity by its ID.

        Args:
            id: The unique identifier of the entity to delete.
        """

    @abstractmethod
    def list_all(self) -> list[T]:
        """List all entities.

        Returns:
            A list of all entities.
        """
