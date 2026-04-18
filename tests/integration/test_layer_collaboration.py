"""Layer collaboration tests (Application → Domain → Infrastructure).

Verifies that the hexagonal architecture layers collaborate correctly:
- Application layer use cases call domain layer services
- Domain layer accesses infrastructure through interfaces
- Error propagation works correctly across layers

CLI/API integration deferred to Story 7.x.
"""

from __future__ import annotations

import pytest

from src.application.use_cases.document_processing import DocumentProcessingUseCase
from src.domain.events.base import DomainEvent
from src.domain.repositories.outbox import OutboxRepository
from src.infrastructure.repositories.outbox import InMemoryOutboxRepository

# ===================================================================
# TDD Cycle A: Application → Domain → Infrastructure Collaboration
# ===================================================================


class TestLayerCollaboration:
    """Verify application layer orchestrates domain and infrastructure."""

    def test_use_case_can_be_constructed(self, outbox_repo: InMemoryOutboxRepository) -> None:
        """DocumentProcessingUseCase should accept OutboxRepository."""
        use_case = DocumentProcessingUseCase(outbox_repo=outbox_repo)
        assert use_case is not None

    def test_use_case_calls_domain_interface(self, outbox_repo: InMemoryOutboxRepository) -> None:
        """Use case should call domain layer's OutboxRepository interface."""
        use_case = DocumentProcessingUseCase(outbox_repo=outbox_repo)
        result = use_case.process_document(document_id="test-doc-1")

        assert result["status"] == "success"
        assert result["document_id"] == "test-doc-1"

    def test_use_case_publishes_event_to_outbox(self, outbox_repo: InMemoryOutboxRepository) -> None:
        """Use case processing should result in event being saved to outbox."""
        use_case = DocumentProcessingUseCase(outbox_repo=outbox_repo)
        use_case.process_document(document_id="test-doc-1")

        unpublished = outbox_repo.get_unpublished(limit=10)
        assert len(unpublished) == 1
        assert unpublished[0].event_type == "DocumentProcessed"
        assert unpublished[0].payload["document_id"] == "test-doc-1"

    def test_use_case_with_custom_metadata(self, outbox_repo: InMemoryOutboxRepository) -> None:
        """Use case should accept optional metadata."""
        use_case = DocumentProcessingUseCase(outbox_repo=outbox_repo)
        result = use_case.process_document(
            document_id="test-doc-2",
            metadata={"source": "test", "format": "pdf"},
        )

        assert result["status"] == "success"
        unpublished = outbox_repo.get_unpublished(limit=10)
        assert len(unpublished) == 1


# ===================================================================
# TDD Cycle B: Error Propagation
# ===================================================================


class TestErrorPropagation:
    """Verify errors propagate correctly from infrastructure → application."""

    def test_use_case_raises_on_infrastructure_failure(self) -> None:
        """When infrastructure layer fails, use case should raise RuntimeError."""

        class FailingOutboxRepository(OutboxRepository):
            """Mock outbox that always fails."""

            def save(self, event: DomainEvent) -> None:
                raise ConnectionError("Simulated infrastructure failure")

            def get_unpublished(self, limit: int) -> list[DomainEvent]:
                return []

            def mark_published(self, event_id) -> None:
                pass

            def mark_failed(self, event_id, error: str) -> None:
                pass

        failing_repo = FailingOutboxRepository()
        use_case = DocumentProcessingUseCase(outbox_repo=failing_repo)

        with pytest.raises(RuntimeError) as exc_info:
            use_case.process_document(document_id="fail-doc")

        assert "Failed to process document fail-doc" in str(exc_info.value)
        assert "Simulated infrastructure failure" in str(exc_info.value.__cause__)

    def test_error_preserves_original_exception(
        self,
    ) -> None:
        """RuntimeError should preserve the original exception as __cause__."""

        class FailingOutboxRepository(OutboxRepository):
            def save(self, event: DomainEvent) -> None:
                raise ValueError("Original infrastructure error")

            def get_unpublished(self, limit: int) -> list[DomainEvent]:
                return []

            def mark_published(self, event_id) -> None:
                pass

            def mark_failed(self, event_id, error: str) -> None:
                pass

        failing_repo = FailingOutboxRepository()
        use_case = DocumentProcessingUseCase(outbox_repo=failing_repo)

        with pytest.raises(RuntimeError) as exc_info:
            use_case.process_document(document_id="fail-doc")

        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, ValueError)

    def test_layer_data_integrity_across_layers(self, outbox_repo: InMemoryOutboxRepository) -> None:
        """DomainEvent objects should maintain integrity across layers."""
        # Create event at application layer
        use_case = DocumentProcessingUseCase(outbox_repo=outbox_repo)
        use_case.process_document(document_id="integrity-test")

        # Verify data integrity in infrastructure layer
        unpublished = outbox_repo.get_unpublished(limit=10)
        assert len(unpublished) == 1

        event = unpublished[0]
        assert isinstance(event, DomainEvent)
        assert event.event_type == "DocumentProcessed"
        assert event.payload["document_id"] == "integrity-test"
        assert event.source == "DocumentProcessingUseCase"
