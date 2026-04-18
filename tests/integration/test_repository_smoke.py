"""Smoke tests for repository pattern (interface → in-memory implementation).

Verifies Story 1.1 BaseRepository[T] interface with Story 1.3
InMemoryOutboxRepository implementation.
Does NOT test real database CRUD (deferred to Story 1.4-1.8).
"""

from __future__ import annotations

from uuid import uuid4

from src.domain.events.base import DomainEvent
from src.domain.repositories.outbox import OutboxRepository
from src.infrastructure.repositories.outbox import InMemoryOutboxRepository

# ===================================================================
# TDD Cycle A: Repository Interface → Memory Implementation
# ===================================================================


class TestRepositoryInterface:
    """Verify InMemoryOutboxRepository implements OutboxRepository interface."""

    def test_implements_outbox_repository_protocol(self, outbox_repo: InMemoryOutboxRepository) -> None:
        """InMemoryOutboxRepository should be an instance of OutboxRepository."""
        assert isinstance(outbox_repo, OutboxRepository)

    def test_save_method_exists(self, outbox_repo: InMemoryOutboxRepository) -> None:
        """Repository should have a save method."""
        assert hasattr(outbox_repo, "save")
        assert callable(getattr(outbox_repo, "save"))

    def test_get_unpublished_method_exists(self, outbox_repo: InMemoryOutboxRepository) -> None:
        """Repository should have a get_unpublished method."""
        assert hasattr(outbox_repo, "get_unpublished")
        assert callable(getattr(outbox_repo, "get_unpublished"))

    def test_mark_published_method_exists(self, outbox_repo: InMemoryOutboxRepository) -> None:
        """Repository should have a mark_published method."""
        assert hasattr(outbox_repo, "mark_published")
        assert callable(getattr(outbox_repo, "mark_published"))

    def test_mark_failed_method_exists(self, outbox_repo: InMemoryOutboxRepository) -> None:
        """Repository should have a mark_failed method."""
        assert hasattr(outbox_repo, "mark_failed")
        assert callable(getattr(outbox_repo, "mark_failed"))


class TestRepositorySmokeOperations:
    """Basic repository CRUD smoke tests."""

    def test_save_and_retrieve_single_event(self, outbox_repo: InMemoryOutboxRepository) -> None:
        """Save a single event and retrieve it via get_unpublished."""
        event = DomainEvent(
            event_id=uuid4(),
            event_type="DocumentProcessed",
            source="test",
            aggregate_id=uuid4(),
            aggregate_type="Document",
            version=1,
            payload={"doc_id": "test-1"},
        )
        outbox_repo.save(event)

        unpublished = outbox_repo.get_unpublished(limit=10)
        assert len(unpublished) == 1
        assert unpublished[0].event_id == event.event_id
        assert unpublished[0].event_type == "DocumentProcessed"

    def test_save_multiple_events(self, outbox_repo: InMemoryOutboxRepository) -> None:
        """Save multiple events and verify count."""

        events_data = [
            ("DocumentProcessed", {"doc_id": "doc-0"}),
            ("ToolExecuted", {"tool_id": "tool-1"}),
            ("AgentDecided", {"agent_id": "agent-2"}),
        ]
        for event_type, payload in events_data:
            event = DomainEvent(
                event_id=uuid4(),
                event_type=event_type,
                source="test",
                aggregate_id=uuid4(),
                aggregate_type="Test",
                version=1,
                payload=payload,
            )
            outbox_repo.save(event)

        unpublished = outbox_repo.get_unpublished(limit=10)
        assert len(unpublished) == 3

    def test_get_unpublished_respects_limit(self, outbox_repo: InMemoryOutboxRepository) -> None:
        """get_unpublished should respect the limit parameter."""
        for i in range(10):
            outbox_repo.save(
                DomainEvent(
                    event_id=uuid4(),
                    event_type="DocumentProcessed",
                    source="test",
                    aggregate_id=uuid4(),
                    aggregate_type="Document",
                    version=i,
                    payload={"doc_id": f"doc-{i}"},
                )
            )

        unpublished = outbox_repo.get_unpublished(limit=3)
        assert len(unpublished) == 3

    def test_get_unpublished_limit_zero_returns_empty(self) -> None:
        """get_unpublished with limit=0 should return empty list."""
        from src.infrastructure.repositories.outbox import InMemoryOutboxRepository

        repo = InMemoryOutboxRepository()
        repo.save(
            DomainEvent(
                event_id=uuid4(),
                event_type="DocumentProcessed",
                source="test",
                aggregate_id=uuid4(),
                aggregate_type="Document",
                version=1,
                payload={},
            )
        )
        assert repo.get_unpublished(limit=0) == []

    def test_get_unpublished_fifo_ordering_by_created_at(self) -> None:
        """get_unpublished should return events in FIFO order (by created_at)."""
        import time

        repo = InMemoryOutboxRepository()

        # Save 3 events with small delays to ensure different created_at
        for i, doc_id in enumerate(["doc-first", "doc-second", "doc-third"]):
            repo.save(
                DomainEvent(
                    event_id=uuid4(),
                    event_type="DocumentProcessed",
                    source="test",
                    aggregate_id=uuid4(),
                    aggregate_type="Document",
                    version=1,
                    payload={"doc_id": doc_id},
                )
            )
            if i < 2:
                time.sleep(0.01)  # Ensure different created_at timestamps

        # Now manually reorder the entities to simulate out-of-order creation
        # Swap first and last entity's created_at
        entities = repo._entities
        if len(entities) == 3:
            entities[0].created_at, entities[2].created_at = (
                entities[2].created_at,
                entities[0].created_at,
            )

        unpublished = repo.get_unpublished(limit=10)
        assert len(unpublished) == 3
        # After swapping created_at[0] <-> created_at[2]:
        # doc-first has T2 (latest), doc-second has T1, doc-third has T0 (earliest)
        # Sorted by created_at ascending: doc-third, doc-second, doc-first
        assert unpublished[0].payload["doc_id"] == "doc-third"  # Now earliest (T0)
        assert unpublished[1].payload["doc_id"] == "doc-second"  # Middle (T1)
        assert unpublished[2].payload["doc_id"] == "doc-first"  # Now latest (T2)

    def test_mark_published_removes_from_unpublished(self, outbox_repo: InMemoryOutboxRepository) -> None:
        """After marking published, event should not appear in unpublished list."""
        event_id = uuid4()
        outbox_repo.save(
            DomainEvent(
                event_id=event_id,
                event_type="TestEvent",
                source="test",
                aggregate_id=uuid4(),
                aggregate_type="Test",
                version=1,
                payload={},
            )
        )
        outbox_repo.mark_published(event_id)

        unpublished = outbox_repo.get_unpublished(limit=10)
        assert len(unpublished) == 0

    def test_mark_failed_increments_retry_count(self, outbox_repo: InMemoryOutboxRepository) -> None:
        """Marking failed should increment retry_count and set error message."""
        event_id = uuid4()
        outbox_repo.save(
            DomainEvent(
                event_id=event_id,
                event_type="DocumentProcessed",
                source="test",
                aggregate_id=uuid4(),
                aggregate_type="Document",
                version=1,
                payload={"doc_id": "test-1"},
            )
        )
        outbox_repo.mark_failed(event_id, "Connection timeout")

        # Event should now be in "failed" status, not in unpublished
        unpublished = outbox_repo.get_unpublished(limit=10)
        assert len(unpublished) == 0

        # Verify retry_count by checking internal entity state
        # (Access to _entities is acceptable in tests for verifying internal state)
        failed_entity = next(e for e in outbox_repo._entities if e.event_id == event_id)
        assert failed_entity.retry_count == 1
        assert failed_entity.error_message == "Connection timeout"

    def test_mark_failed_multiple_calls_increments_retry_count(self, outbox_repo: InMemoryOutboxRepository) -> None:
        """Multiple mark_failed calls should increment retry_count each time."""
        event_id = uuid4()
        outbox_repo.save(
            DomainEvent(
                event_id=event_id,
                event_type="DocumentProcessed",
                source="test",
                aggregate_id=uuid4(),
                aggregate_type="Document",
                version=1,
                payload={},
            )
        )
        outbox_repo.mark_failed(event_id, "Error 1")
        outbox_repo.mark_failed(event_id, "Error 2")
        outbox_repo.mark_failed(event_id, "Error 3")

        failed_entity = next(e for e in outbox_repo._entities if e.event_id == event_id)
        assert failed_entity.retry_count == 3
        assert failed_entity.error_message == "Error 3"  # Last error message

    def test_mark_published_non_existent_event_id_is_noop(self, outbox_repo: InMemoryOutboxRepository) -> None:
        """mark_published with non-existent event_id should silently do nothing."""
        non_existent_id = uuid4()
        # Should not raise any exception
        outbox_repo.mark_published(non_existent_id)
        unpublished = outbox_repo.get_unpublished(limit=10)
        assert len(unpublished) == 0  # Still empty

    def test_mark_failed_non_existent_event_id_is_noop(self, outbox_repo: InMemoryOutboxRepository) -> None:
        """mark_failed with non-existent event_id should silently do nothing."""
        non_existent_id = uuid4()
        # Should not raise any exception
        outbox_repo.mark_failed(non_existent_id, "Some error")
        unpublished = outbox_repo.get_unpublished(limit=10)
        assert len(unpublished) == 0  # Still empty


# ===================================================================
# TDD Cycle B: Test Data Lifecycle Management
# ===================================================================


class TestDataLifecycleManagement:
    """Verify test isolation: each test gets independent repo state."""

    def test_first_test_sees_empty_repo(self, outbox_repo: InMemoryOutboxRepository) -> None:
        """This test verifies it starts with a clean repo."""
        unpublished = outbox_repo.get_unpublished(limit=10)
        assert len(unpublished) == 0

    def test_second_test_also_sees_empty_repo(self, outbox_repo: InMemoryOutboxRepository) -> None:
        """Proves fixture isolation — each test gets fresh instance."""
        # Add some data (should not affect other tests)
        outbox_repo.save(
            DomainEvent(
                event_id=uuid4(),
                event_type="DocumentProcessed",
                source="test",
                aggregate_id=uuid4(),
                aggregate_type="Document",
                version=1,
                payload={"doc_id": "test"},
            )
        )
        unpublished = outbox_repo.get_unpublished(limit=10)
        assert len(unpublished) == 1

    def test_third_test_confirms_isolation(self, outbox_repo: InMemoryOutboxRepository) -> None:
        """Final confirmation that fixture isolation works."""
        unpublished = outbox_repo.get_unpublished(limit=10)
        assert len(unpublished) == 0  # Not affected by test_second_*
