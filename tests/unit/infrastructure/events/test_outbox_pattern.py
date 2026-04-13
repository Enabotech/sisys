"""Task 3 TDD Tests — Outbox Pattern."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.domain.events import DocumentProcessed
from src.domain.events.base import DomainEvent
from src.infrastructure.adapters.event_outbox_adapter import EventOutboxAdapter, EventRegistry
from src.infrastructure.entities.outbox import InvalidStateTransitionError, OutboxEntity
from src.infrastructure.repositories.outbox import InMemoryOutboxRepository


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
# TDD Cycle C: InMemoryOutboxRepository
# ============================================================================


class TestInMemoryOutboxRepository:
    """InMemoryOutboxRepository tests."""

    @pytest.mark.asyncio
    async def test_save_adds_event(self):
        """save should add event to memory store."""
        repo = InMemoryOutboxRepository()
        event = _make_event()
        repo.save(event)

        unpublished = repo.get_unpublished(limit=10)
        assert len(unpublished) == 1
        assert unpublished[0].event_id == event.event_id

    @pytest.mark.asyncio
    async def test_get_unpublished_returns_pending(self):
        """get_unpublished should return only pending events."""
        repo = InMemoryOutboxRepository()
        event1 = _make_event()
        event2 = DocumentProcessed(
            document_id=uuid4(),
            parse_result={"pages": 5},
            embedding=[0.2] * 1024,
        )
        repo.save(event1)
        repo.save(event2)

        unpublished = repo.get_unpublished(limit=10)
        assert len(unpublished) == 2

    @pytest.mark.asyncio
    async def test_get_unpublished_respects_limit(self):
        """get_unpublished should respect limit parameter."""
        repo = InMemoryOutboxRepository()
        for i in range(5):
            repo.save(
                DocumentProcessed(
                    document_id=uuid4(),
                    parse_result={"pages": i},
                    embedding=[float(i)] * 1024,
                )
            )

        unpublished = repo.get_unpublished(limit=3)
        assert len(unpublished) == 3

    @pytest.mark.asyncio
    async def test_mark_published(self):
        """mark_published should mark event as published."""
        repo = InMemoryOutboxRepository()
        event = _make_event()
        repo.save(event)
        repo.mark_published(event.event_id)

        unpublished = repo.get_unpublished(limit=10)
        assert len(unpublished) == 0

    @pytest.mark.asyncio
    async def test_mark_failed(self):
        """mark_failed should mark event as failed."""
        repo = InMemoryOutboxRepository()
        event = _make_event()
        repo.save(event)
        repo.mark_failed(event.event_id, "publish error")

        unpublished = repo.get_unpublished(limit=10)
        assert len(unpublished) == 0

    @pytest.mark.asyncio
    async def test_async_get_unpublished_entities(self):
        """_get_unpublished_entities should return OutboxEntity list."""
        repo = InMemoryOutboxRepository()
        event = _make_event()
        repo.save(event)

        entities = await repo._get_unpublished_entities(limit=10)
        assert len(entities) == 1
        assert isinstance(entities[0], OutboxEntity)

    @pytest.mark.asyncio
    async def test_async_mark_published_entity(self):
        """_mark_published_entity should mark entity as published."""
        repo = InMemoryOutboxRepository()
        event = _make_event()
        repo.save(event)

        entities = await repo._get_unpublished_entities(limit=10)
        await repo._mark_published_entity(entities[0])

        remaining = await repo._get_unpublished_entities(limit=10)
        assert len(remaining) == 0

    @pytest.mark.asyncio
    async def test_async_mark_failed_entity(self):
        """_mark_failed_entity should mark entity as failed."""
        repo = InMemoryOutboxRepository()
        event = _make_event()
        repo.save(event)

        entities = await repo._get_unpublished_entities(limit=10)
        await repo._mark_failed_entity(entities[0], "error")

        remaining = await repo._get_unpublished_entities(limit=10)
        assert len(remaining) == 0

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
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.ImportFrom):
                        if node.module and "outbox" in node.module.lower() and "entities" in node.module.lower():
                            pytest.fail(f"Domain file {py_file} imports from infrastructure.entities")


# ============================================================================
# TDD Cycle D: AsyncOutboxPoller
# ============================================================================


class TestAsyncOutboxPoller:
    """AsyncOutboxPoller tests."""

    @pytest.mark.asyncio
    async def test_poll_once_publishes_pending_events(self):
        """poll_once should publish pending events."""
        from src.infrastructure.events.async_outbox_poller import AsyncOutboxPoller

        repo = InMemoryOutboxRepository()
        mock_publisher = AsyncMock()

        poller = AsyncOutboxPoller(
            outbox_repository=repo,
            publisher=mock_publisher,
            poll_interval=0.1,
        )

        event = _make_event()
        repo.save(event)

        await poller.poll_once()

        mock_publisher.async_publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_poll_once_marks_published(self):
        """poll_once should mark events as published after successful publish."""
        from src.infrastructure.events.async_outbox_poller import AsyncOutboxPoller

        repo = InMemoryOutboxRepository()
        mock_publisher = AsyncMock()

        poller = AsyncOutboxPoller(
            outbox_repository=repo,
            publisher=mock_publisher,
            poll_interval=0.1,
        )

        event = _make_event()
        repo.save(event)

        await poller.poll_once()

        unpublished = repo.get_unpublished(limit=10)
        assert len(unpublished) == 0

    @pytest.mark.asyncio
    async def test_poll_once_marks_failed_on_error(self):
        """poll_once should mark events as failed on publish error."""
        from src.infrastructure.events.async_outbox_poller import AsyncOutboxPoller

        repo = InMemoryOutboxRepository()
        mock_publisher = AsyncMock()
        mock_publisher.async_publish.side_effect = RuntimeError("publish failed")

        poller = AsyncOutboxPoller(
            outbox_repository=repo,
            publisher=mock_publisher,
            poll_interval=0.1,
        )

        event = _make_event()
        repo.save(event)

        await poller.poll_once()

        unpublished = repo.get_unpublished(limit=10)
        assert len(unpublished) == 0  # Marked as failed, not pending

    @pytest.mark.asyncio
    async def test_poller_runs_loop(self):
        """run should execute poll_once at least once before stopped."""
        from src.infrastructure.events.async_outbox_poller import AsyncOutboxPoller

        repo = InMemoryOutboxRepository()
        mock_publisher = AsyncMock()

        poller = AsyncOutboxPoller(
            outbox_repository=repo,
            publisher=mock_publisher,
            poll_interval=0.05,
        )

        # Add an event so poll_once has something to do
        event = _make_event()
        repo.save(event)

        # Run poll_once directly to verify it works
        await poller.poll_once()
        assert mock_publisher.async_publish.call_count == 1

    @pytest.mark.asyncio
    async def test_poller_graceful_stop(self):
        """stop should gracefully stop the polling loop."""
        from src.infrastructure.events.async_outbox_poller import AsyncOutboxPoller

        repo = InMemoryOutboxRepository()
        mock_publisher = AsyncMock()

        poller = AsyncOutboxPoller(
            outbox_repository=repo,
            publisher=mock_publisher,
            poll_interval=0.1,
        )

        poller.stop()  # Should not raise
        assert not poller._running
