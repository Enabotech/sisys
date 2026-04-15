"""Task 3 TDD Tests — OutboxRepository interface (domain layer)."""

from __future__ import annotations

import pytest

from src.domain.repositories.outbox import OutboxRepository


class TestOutboxRepositoryInterface:
    """OutboxRepository interface tests (domain layer)."""

    def test_interface_has_save_method(self):
        """OutboxRepository should define save method."""
        assert hasattr(OutboxRepository, "save")

    def test_interface_has_get_unpublished_method(self):
        """OutboxRepository should define get_unpublished method."""
        assert hasattr(OutboxRepository, "get_unpublished")

    def test_interface_has_mark_published_method(self):
        """OutboxRepository should define mark_published method."""
        assert hasattr(OutboxRepository, "mark_published")

    def test_interface_has_mark_failed_method(self):
        """OutboxRepository should define mark_failed method."""
        assert hasattr(OutboxRepository, "mark_failed")

    def test_cannot_instantiate_abstract(self):
        """Should not be able to instantiate abstract interface."""
        with pytest.raises(TypeError):
            OutboxRepository()

    def test_concrete_implementation_required(self):
        """Concrete class must implement all abstract methods."""

        class ConcreteOutboxRepository(OutboxRepository):
            def save(self, event):
                pass

            def get_unpublished(self, limit):
                return []

            def mark_published(self, event_id):
                pass

            def mark_failed(self, event_id, error):
                pass

        repo = ConcreteOutboxRepository()
        assert repo is not None
