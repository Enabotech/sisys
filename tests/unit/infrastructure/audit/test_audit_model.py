"""Test AuditLogModel - Red Phase (Test First).

TDD Cycle: Red -> Green -> Refactor
This test file contains failing tests that define the expected behavior
of AuditLogModel. Run these tests to confirm they fail before implementation.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime


class TestAuditLogModelCreation:
    """Test AuditLogModel creation with required fields."""

    def test_create_audit_log_with_required_fields(self):
        """Can create audit log with required FR-SC-02 fields."""
        from src.infrastructure.storage.postgresql.models.audit import AuditLogModel

        log_id = uuid.uuid4()
        timestamp = datetime.now(UTC)
        actor = "user-123"
        action_type = "document:upload"
        target_resource = "document/doc-456"
        old_value = {"status": "draft"}
        new_value = {"status": "published"}

        model = AuditLogModel(
            log_id=log_id,
            timestamp=timestamp,
            actor=actor,
            action_type=action_type,
            target_resource=target_resource,
            old_value=old_value,
            new_value=new_value,
        )

        assert model.log_id == log_id
        assert model.timestamp == timestamp
        assert model.actor == actor
        assert model.action_type == action_type
        assert model.target_resource == target_resource
        assert model.old_value == old_value
        assert model.new_value == new_value

    def test_create_audit_log_with_correction_level(self):
        """Can create audit log with correction_level for FR-SC-04."""
        from src.infrastructure.storage.postgresql.models.audit import AuditLogModel

        model = AuditLogModel(
            log_id=uuid.uuid4(),
            timestamp=datetime.now(UTC),
            actor="user-123",
            action_type="correction:apply",
            target_resource="document/doc-456",
            old_value={"content": "old"},
            new_value={"content": "new"},
            correction_level=1,
        )

        assert model.correction_level == 1

    def test_create_audit_log_with_correlation_id(self):
        """Can create audit log with correlation_id for tracing."""
        from src.infrastructure.storage.postgresql.models.audit import AuditLogModel

        correlation_id = "corr-789"
        model = AuditLogModel(
            log_id=uuid.uuid4(),
            timestamp=datetime.now(UTC),
            actor="user-123",
            action_type="document:process",
            target_resource="document/doc-456",
            old_value={},
            new_value={"result": "processed"},
            correlation_id=correlation_id,
        )

        assert model.correlation_id == correlation_id

    def test_audit_log_auto_computes_checksum(self):
        """AuditLogModel auto-computes SHA256 checksum on creation."""
        from src.infrastructure.storage.postgresql.models.audit import AuditLogModel

        model = AuditLogModel(
            log_id=uuid.uuid4(),
            timestamp=datetime.now(UTC),
            actor="user-123",
            action_type="document:upload",
            target_resource="document/doc-456",
            old_value={},
            new_value={},
        )

        assert model.checksum is not None
        assert len(model.checksum) == 64  # SHA256 hex digest length

    def test_audit_log_correction_level_constraint(self):
        """Correction level must be 0-3 or NULL."""
        from src.infrastructure.storage.postgresql.models.audit import AuditLogModel

        # Valid correction levels
        for level in [0, 1, 2, 3, None]:
            model = AuditLogModel(
                log_id=uuid.uuid4(),
                timestamp=datetime.now(UTC),
                actor="user",
                action_type="test",
                target_resource="test",
                old_value={},
                new_value={},
                correction_level=level,
            )
            assert model.correction_level == level


class TestAuditLogModelChecksum:
    """Test checksum computation and verification."""

    def test_checksum_changes_when_data_changes(self):
        """Checksum changes when any field value changes."""
        from src.infrastructure.storage.postgresql.models.audit import AuditLogModel

        model1 = AuditLogModel(
            log_id=uuid.uuid4(),
            timestamp=datetime.now(UTC),
            actor="user-123",
            action_type="document:upload",
            target_resource="document/doc-456",
            old_value={},
            new_value={},
        )

        model2 = AuditLogModel(
            log_id=uuid.uuid4(),  # Different log_id
            timestamp=datetime.now(UTC),
            actor="user-123",
            action_type="document:upload",
            target_resource="document/doc-456",
            old_value={},
            new_value={},
        )

        assert model1.checksum != model2.checksum

    def test_verify_checksum_returns_true_for_intact_record(self):
        """verify_checksum() returns True when record is intact."""
        from src.infrastructure.storage.postgresql.models.audit import AuditLogModel

        model = AuditLogModel(
            log_id=uuid.uuid4(),
            timestamp=datetime.now(UTC),
            actor="user-123",
            action_type="document:upload",
            target_resource="document/doc-456",
            old_value={},
            new_value={},
        )

        assert model.verify_checksum() is True

    def test_verify_checksum_returns_false_when_tampered(self):
        """verify_checksum() returns False when record is tampered."""
        from src.infrastructure.storage.postgresql.models.audit import AuditLogModel

        model = AuditLogModel(
            log_id=uuid.uuid4(),
            timestamp=datetime.now(UTC),
            actor="user-123",
            action_type="document:upload",
            target_resource="document/doc-456",
            old_value={},
            new_value={},
        )

        # Tamper with the data
        model.actor = "hacker"

        assert model.verify_checksum() is False


class TestAuditLogModelSerialization:
    """Test AuditLogModel serialization."""

    def test_to_dict_returns_complete_representation(self):
        """to_dict() returns all fields including metadata."""
        from src.infrastructure.storage.postgresql.models.audit import AuditLogModel

        log_id = uuid.uuid4()
        timestamp = datetime.now(UTC)
        actor = "user-123"
        action_type = "document:upload"
        target_resource = "document/doc-456"

        model = AuditLogModel(
            log_id=log_id,
            timestamp=timestamp,
            actor=actor,
            action_type=action_type,
            target_resource=target_resource,
            old_value={"status": "draft"},
            new_value={"status": "published"},
            correction_level=0,
        )

        d = model.to_dict()

        assert d["log_id"] == str(log_id)
        assert d["actor"] == actor
        assert d["action_type"] == action_type
        assert d["target_resource"] == target_resource
        assert d["old_value"] == {"status": "draft"}
        assert d["new_value"] == {"status": "published"}
        assert d["correction_level"] == 0
        assert "checksum" in d
        assert "integrity_verified" in d
        assert d["integrity_verified"] is True

    def test_to_dict_includes_optional_fields(self):
        """to_dict() includes correlation_id and archive fields when set."""
        from src.infrastructure.storage.postgresql.models.audit import AuditLogModel

        model = AuditLogModel(
            log_id=uuid.uuid4(),
            timestamp=datetime.now(UTC),
            actor="user-123",
            action_type="document:upload",
            target_resource="document/doc-456",
            old_value={},
            new_value={},
            correlation_id="corr-123",
        )

        d = model.to_dict()

        assert d["correlation_id"] == "corr-123"
        assert d["archived"] is False
        assert d["archived_at"] is None
