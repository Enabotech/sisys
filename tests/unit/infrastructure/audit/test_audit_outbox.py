"""Test AuditOutboxModel - Red Phase (Test First).

TDD Cycle: Red -> Green -> Refactor
Reference: Story 1.10 Task 2 - Transaction Outbox Pattern
"""

from __future__ import annotations

import uuid


class TestAuditOutboxModelCreation:
    """Test AuditOutboxModel creation."""

    def test_create_outbox_entry(self):
        """Can create outbox entry with required fields."""
        from src.infrastructure.storage.postgresql.models.audit_outbox import AuditOutboxModel

        event_id = uuid.uuid4()
        payload = {"log_id": str(uuid.uuid4()), "action": "test"}

        model = AuditOutboxModel(
            event_id=event_id,
            payload=payload,
        )

        assert model.event_id == event_id
        assert model.payload == payload
        assert model.status == "pending"
        assert model.retry_count == 0

    def test_create_outbox_with_custom_status(self):
        """Can create outbox entry with custom status."""
        from src.infrastructure.storage.postgresql.models.audit_outbox import AuditOutboxModel

        model = AuditOutboxModel(
            event_id=uuid.uuid4(),
            payload={"test": "data"},
            status="published",
        )

        assert model.status == "published"

    def test_create_outbox_with_max_retries(self):
        """Can configure max_retries."""
        from src.infrastructure.storage.postgresql.models.audit_outbox import AuditOutboxModel

        model = AuditOutboxModel(
            event_id=uuid.uuid4(),
            payload={"test": "data"},
            max_retries=5,
        )

        assert model.max_retries == 5


class TestAuditOutboxModelStateTransitions:
    """Test outbox entry state transitions."""

    def test_mark_published(self):
        """mark_published() updates status and sets processed_at."""
        from src.infrastructure.storage.postgresql.models.audit_outbox import AuditOutboxModel

        model = AuditOutboxModel(
            event_id=uuid.uuid4(),
            payload={"test": "data"},
        )

        model.mark_published()

        assert model.status == "published"
        assert model.processed_at is not None

    def test_mark_failed(self):
        """mark_failed() updates status, increments retry_count, sets error."""
        from src.infrastructure.storage.postgresql.models.audit_outbox import AuditOutboxModel

        model = AuditOutboxModel(
            event_id=uuid.uuid4(),
            payload={"test": "data"},
        )

        model.mark_failed("Connection timeout")

        assert model.status == "failed"
        assert model.error_message == "Connection timeout"
        assert model.retry_count == 1

    def test_mark_failed_increments_retry_count(self):
        """mark_failed() increments retry_count each call."""
        from src.infrastructure.storage.postgresql.models.audit_outbox import AuditOutboxModel

        model = AuditOutboxModel(
            event_id=uuid.uuid4(),
            payload={"test": "data"},
            retry_count=2,
        )

        model.mark_failed("Error 1")
        assert model.retry_count == 3

        model.mark_failed("Error 2")
        assert model.retry_count == 4

    def test_can_retry_returns_true_when_under_limit(self):
        """can_retry() returns True when retry_count < max_retries."""
        from src.infrastructure.storage.postgresql.models.audit_outbox import AuditOutboxModel

        model = AuditOutboxModel(
            event_id=uuid.uuid4(),
            payload={"test": "data"},
            retry_count=2,
            max_retries=3,
        )

        assert model.can_retry() is True

    def test_can_retry_returns_false_when_at_limit(self):
        """can_retry() returns False when retry_count >= max_retries."""
        from src.infrastructure.storage.postgresql.models.audit_outbox import AuditOutboxModel

        model = AuditOutboxModel(
            event_id=uuid.uuid4(),
            payload={"test": "data"},
            retry_count=3,
            max_retries=3,
        )

        assert model.can_retry() is False

    def test_can_retry_returns_false_when_over_limit(self):
        """can_retry() returns False when retry_count > max_retries."""
        from src.infrastructure.storage.postgresql.models.audit_outbox import AuditOutboxModel

        model = AuditOutboxModel(
            event_id=uuid.uuid4(),
            payload={"test": "data"},
            retry_count=5,
            max_retries=3,
        )

        assert model.can_retry() is False


class TestAuditOutboxModelSerialization:
    """Test AuditOutboxModel serialization."""

    def test_to_dict_returns_all_fields(self):
        """to_dict() returns complete representation."""
        from src.infrastructure.storage.postgresql.models.audit_outbox import AuditOutboxModel

        event_id = uuid.uuid4()
        payload = {"action": "test"}

        model = AuditOutboxModel(
            event_id=event_id,
            payload=payload,
            status="pending",
        )

        d = model.to_dict()

        assert d["event_id"] == str(event_id)
        assert d["payload"] == payload
        assert d["status"] == "pending"
        assert d["retry_count"] == 0
        assert d["max_retries"] == 3
        assert d["error_message"] is None
