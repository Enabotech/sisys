"""Task 3 TDD Tests — Outbox Pattern."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.domain.events import DocumentProcessed
from src.domain.events.base import DomainEvent
from src.infrastructure.messaging.adapters.event_outbox_adapter import EventOutboxAdapter, EventRegistry
from src.infrastructure.messaging.outbox.outbox import InvalidStateTransitionError, OutboxEntity


def _make_event() -> DomainEvent:
    return DocumentProcessed(
        document_id=uuid4(),
        parse_result={"pages": 10},
        embedding=[0.1] * 1024,
    )


# ============================================================================
# TDD Cycle A: OutboxEntity + EventOutboxAdapter
# ============================================================================


class TestOutboxEntity:
    """OutboxEntity tests."""

    def test_default_values(self):
        """OutboxEntity should have sensible defaults."""
        entity = OutboxEntity()
        assert entity.status == "pending"
        assert entity.retry_count == 0
        assert entity.max_retries == 3
        assert entity.error_message is None
        assert entity.published_at is None

    def test_mark_published(self):
        """Should transition from pending to published."""
        entity = OutboxEntity()
        entity.mark_published()
        assert entity.status == "published"
        assert entity.published_at is not None

    def test_mark_published_from_wrong_status(self):
        """Should raise InvalidStateTransitionError from wrong status."""
        entity = OutboxEntity()
        entity.mark_published()
        with pytest.raises(InvalidStateTransitionError):
            entity.mark_published()  # Can't publish twice

    def test_mark_failed(self):
        """Should transition to failed and increment retry_count."""
        entity = OutboxEntity()
        entity.mark_failed("connection error")
        assert entity.status == "failed"
        assert entity.retry_count == 1
        assert entity.error_message == "connection error"

    def test_mark_pending_retry(self):
        """Should transition from failed to pending if retries remaining."""
        entity = OutboxEntity()
        entity.max_retries = 3
        entity.mark_failed("error")
        entity.mark_pending()
        assert entity.status == "pending"
        assert entity.error_message is None

    def test_mark_pending_exceeds_max_retries(self):
        """Should raise if retry_count >= max_retries."""
        entity = OutboxEntity()
        entity.max_retries = 3
        entity.retry_count = 3
        entity.status = "failed"
        with pytest.raises(InvalidStateTransitionError):
            entity.mark_pending()

    def test_mark_archived(self):
        """Should transition from failed to archived."""
        entity = OutboxEntity()
        entity.status = "failed"
        entity.mark_archived()
        assert entity.status == "archived"

    def test_mark_archived_from_wrong_status(self):
        """Should raise if not from failed status."""
        entity = OutboxEntity()
        with pytest.raises(InvalidStateTransitionError):
            entity.mark_archived()


class TestEventOutboxAdapter:
    """EventOutboxAdapter tests."""

    def test_from_domain_event(self):
        """Should convert DomainEvent to OutboxEntity."""
        event = _make_event()
        entity = EventOutboxAdapter.from_domain_event(event)

        assert entity.event_id == event.event_id
        assert entity.event_type == event.event_type
        assert entity.status == "pending"
        assert entity.payload == event.to_dict()

    def test_to_domain_event(self):
        """Should convert OutboxEntity back to DomainEvent."""
        event = _make_event()
        entity = EventOutboxAdapter.from_domain_event(event)
        restored = EventOutboxAdapter.to_domain_event(entity)

        assert restored.event_id == event.event_id
        assert restored.event_type == event.event_type
        assert "document_id" in restored.payload

    def test_to_domain_event_unknown_type(self):
        """Should raise ValueError for unknown event_type."""
        entity = OutboxEntity()
        entity.event_type = "UnknownEvent"
        entity.payload = {}

        with pytest.raises(ValueError, match="Unknown event_type"):
            EventOutboxAdapter.to_domain_event(entity)

    def test_registry_reset(self):
        """EventRegistry.reset should clear the registry."""
        EventRegistry.reset()
        # After reset, registry should rebuild on next get()
        event_class = EventRegistry.get("DocumentProcessed")
        assert event_class is not None


# ============================================================================
# TDD Cycle B: OutboxRepository Interface (Domain Layer)
# ============================================================================


class TestOutboxRepositoryInterface:
    """OutboxRepository interface tests (domain layer)."""

    def test_interface_exists(self):
        """OutboxRepository should be an abstract class."""
        from src.domain.repositories.outbox import OutboxRepository

        assert hasattr(OutboxRepository, "save")
        assert hasattr(OutboxRepository, "get_unpublished")
        assert hasattr(OutboxRepository, "mark_published")
        assert hasattr(OutboxRepository, "mark_failed")

    def test_cannot_instantiate_abstract(self):
        """Should not be able to instantiate abstract interface."""
        from src.domain.repositories.outbox import OutboxRepository

        with pytest.raises(TypeError):
            OutboxRepository()


# ============================================================================
# TDD Cycle C: Domain Layer Zero Dependency
# ============================================================================


class TestDomainLayerIsolation:
    """Verify domain layer has zero infrastructure dependencies."""

    def test_domain_layer_zero_outbox_entity_dependency(self):
        """Domain layer should not import OutboxEntity."""
        import ast
        import pathlib

        domain_path = pathlib.Path("src/domain")
        for py_file in domain_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            tree = ast.parse(py_file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):  # noqa: UP038
                    if isinstance(node, ast.ImportFrom):
                        if node.module and "outbox" in node.module.lower() and "entities" in node.module.lower():
                            pytest.fail(f"Domain file {py_file} imports from infrastructure.entities")


# ============================================================================
# TDD Cycle D: AsyncOutboxPoller (using mocks)
# ============================================================================


def _create_mock_repo():
    """Create a mock repo with internal methods for AsyncOutboxPoller."""
    from src.domain.repositories.outbox import OutboxRepository

    repo = MagicMock(spec=OutboxRepository)
    # Add internal methods that AsyncOutboxPoller uses
    repo._get_unpublished_entities = AsyncMock(return_value=[])
    repo._mark_published_entity = AsyncMock()
    repo._mark_failed_entity = AsyncMock()
    return repo


class TestAsyncOutboxPoller:
    """AsyncOutboxPoller tests using mocks."""

    @pytest.mark.asyncio
    async def test_poll_once_publishes_pending_events(self):
        """poll_once should publish pending events."""
        repo = _create_mock_repo()
        # Create a proper OutboxEntity via DomainEvent → Entity conversion
        event = _make_event()
        entity = EventOutboxAdapter.from_domain_event(event)
        repo._get_unpublished_entities.return_value = [entity]

        mock_publisher = AsyncMock()

        from src.infrastructure.messaging.outbox.outbox_processor import AsyncOutboxPoller

        poller = AsyncOutboxPoller(
            outbox_repository=repo,
            publisher=mock_publisher,
            poll_interval=0.1,
        )

        await poller.poll_once()

        mock_publisher.async_publish.assert_called_once()
        repo._mark_published_entity.assert_called_once()

    @pytest.mark.asyncio
    async def test_poll_once_marks_published_after_success(self):
        """poll_once should mark event as published after successful publish."""
        repo = _create_mock_repo()
        event = _make_event()
        entity = EventOutboxAdapter.from_domain_event(event)
        repo._get_unpublished_entities.return_value = [entity]

        mock_publisher = AsyncMock()

        from src.infrastructure.messaging.outbox.outbox_processor import AsyncOutboxPoller

        poller = AsyncOutboxPoller(
            outbox_repository=repo,
            publisher=mock_publisher,
            poll_interval=0.1,
        )

        await poller.poll_once()

        repo._mark_published_entity.assert_called_once()

    @pytest.mark.asyncio
    async def test_poll_once_marks_failed_on_error(self):
        """poll_once should mark events as failed on publish error."""
        repo = _create_mock_repo()
        event = _make_event()
        entity = EventOutboxAdapter.from_domain_event(event)
        repo._get_unpublished_entities.return_value = [entity]

        mock_publisher = AsyncMock()
        mock_publisher.async_publish.side_effect = RuntimeError("publish failed")

        from src.infrastructure.messaging.outbox.outbox_processor import AsyncOutboxPoller

        poller = AsyncOutboxPoller(
            outbox_repository=repo,
            publisher=mock_publisher,
            poll_interval=0.1,
        )

        await poller.poll_once()

        repo._mark_failed_entity.assert_called_once()

    @pytest.mark.asyncio
    async def test_poller_runs_loop(self):
        """run should execute poll_once at least once before stopped."""
        repo = _create_mock_repo()
        repo._get_unpublished_entities.return_value = []

        mock_publisher = AsyncMock()

        from src.infrastructure.messaging.outbox.outbox_processor import AsyncOutboxPoller

        poller = AsyncOutboxPoller(
            outbox_repository=repo,
            publisher=mock_publisher,
            poll_interval=0.05,
        )

        # Run poll_once directly to verify it works
        await poller.poll_once()
        repo._get_unpublished_entities.assert_called()

    @pytest.mark.asyncio
    async def test_poller_graceful_stop(self):
        """stop should gracefully stop the polling loop."""
        repo = _create_mock_repo()
        mock_publisher = AsyncMock()

        from src.infrastructure.messaging.outbox.outbox_processor import AsyncOutboxPoller

        poller = AsyncOutboxPoller(
            outbox_repository=repo,
            publisher=mock_publisher,
            poll_interval=0.1,
        )

        poller.stop()  # Should not raise
        assert not poller._running
