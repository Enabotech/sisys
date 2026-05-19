"""Layer collaboration tests (Application → Domain → Infrastructure).

Verifies that the hexagonal architecture layers collaborate correctly:
- Application layer use cases call domain layer services
- Domain layer accesses infrastructure through interfaces
- Error propagation works correctly across layers

CLI/API integration deferred to Story 7.x.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.application.use_cases.document_processing import DocumentProcessingUseCase
from src.domain.events.base import DomainEvent
from src.domain.ports.outbox import OutboxRepository

# ===================================================================
# TDD Cycle A: Application → Domain → Infrastructure Collaboration
# ===================================================================


class TestLayerCollaboration:
    """Verify application layer orchestrates domain and infrastructure."""

    @pytest.mark.asyncio
    async def test_use_case_can_be_constructed(self, outbox_repo: AsyncMock) -> None:
        """DocumentProcessingUseCase should accept OutboxRepository."""
        use_case = DocumentProcessingUseCase(outbox_repo=outbox_repo)
        assert use_case is not None

    @pytest.mark.asyncio
    async def test_use_case_calls_domain_interface(self, outbox_repo: AsyncMock) -> None:
        """Use case should call domain layer's OutboxRepository interface."""
        use_case = DocumentProcessingUseCase(outbox_repo=outbox_repo)
        result = await use_case.process_document(document_id="test-doc-1")

        assert result["status"] == "success"
        assert result["document_id"] == "test-doc-1"

    @pytest.mark.asyncio
    async def test_use_case_publishes_event_to_outbox(self, outbox_repo: AsyncMock) -> None:
        """Use case processing should result in event being saved to outbox."""
        use_case = DocumentProcessingUseCase(outbox_repo=outbox_repo)
        await use_case.process_document(document_id="test-doc-1")

        outbox_repo.save.assert_called_once()
        call_args = outbox_repo.save.call_args
        saved_event = call_args[0][0]
        assert isinstance(saved_event, DomainEvent)
        assert saved_event.event_type == "DocumentProcessed"
        assert saved_event.payload["document_id"] == "test-doc-1"

    @pytest.mark.asyncio
    async def test_use_case_with_custom_metadata(self, outbox_repo: AsyncMock) -> None:
        """Use case should accept optional metadata."""
        use_case = DocumentProcessingUseCase(outbox_repo=outbox_repo)
        result = await use_case.process_document(
            document_id="test-doc-2",
            metadata={"source": "test", "format": "pdf"},
        )

        assert result["status"] == "success"
        outbox_repo.save.assert_called()


# ===================================================================
# TDD Cycle B: Error Propagation
# ===================================================================


class TestErrorPropagation:
    """Verify errors propagate correctly from infrastructure → application."""

    @pytest.mark.asyncio
    async def test_use_case_raises_on_infrastructure_failure(self) -> None:
        """When infrastructure layer fails, use case should raise RuntimeError."""

        class FailingOutboxRepository(OutboxRepository):
            """Mock outbox that always fails."""

            async def save(self, event: DomainEvent) -> None:
                raise ConnectionError("Simulated infrastructure failure")

            async def get_unpublished(self, limit: int) -> list[DomainEvent]:
                return []

            async def mark_published(self, event_id) -> None:
                pass

            async def mark_failed(self, event_id, error: str) -> None:
                pass

            async def cleanup_old_published_records(self, older_than_days: int = 30) -> int:
                return 0

        failing_repo = FailingOutboxRepository()
        use_case = DocumentProcessingUseCase(outbox_repo=failing_repo)

        with pytest.raises(RuntimeError) as exc_info:
            await use_case.process_document(document_id="fail-doc")

        assert "Failed to process document fail-doc" in str(exc_info.value)
        assert "Simulated infrastructure failure" in str(exc_info.value.__cause__)

    @pytest.mark.asyncio
    async def test_error_preserves_original_exception(
        self,
    ) -> None:
        """RuntimeError should preserve the original exception as __cause__."""

        class FailingOutboxRepository(OutboxRepository):
            async def save(self, event: DomainEvent) -> None:
                raise ValueError("Original infrastructure error")

            async def get_unpublished(self, limit: int) -> list[DomainEvent]:
                return []

            async def mark_published(self, event_id) -> None:
                pass

            async def mark_failed(self, event_id, error: str) -> None:
                pass

            async def cleanup_old_published_records(self, older_than_days: int = 30) -> int:
                return 0

        failing_repo = FailingOutboxRepository()
        use_case = DocumentProcessingUseCase(outbox_repo=failing_repo)

        with pytest.raises(RuntimeError) as exc_info:
            await use_case.process_document(document_id="fail-doc")

        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, ValueError)

    @pytest.mark.asyncio
    async def test_layer_data_integrity_across_layers(self, outbox_repo: AsyncMock) -> None:
        """DomainEvent objects should maintain integrity across layers."""
        use_case = DocumentProcessingUseCase(outbox_repo=outbox_repo)
        await use_case.process_document(document_id="integrity-test")

        # Verify save was called with correct event
        outbox_repo.save.assert_called_once()
        call_args = outbox_repo.save.call_args
        saved_event = call_args[0][0]
        assert isinstance(saved_event, DomainEvent)
        assert saved_event.event_type == "DocumentProcessed"
        assert saved_event.payload["document_id"] == "integrity-test"
        assert saved_event.source == "DocumentProcessingUseCase"
