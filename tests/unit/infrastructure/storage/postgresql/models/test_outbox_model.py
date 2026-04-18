"""OutboxModel TDD tests — Red phase."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase

from src.infrastructure.storage.postgresql.models.outbox import OutboxModel


class TestOutboxModel:
    """OutboxModel tests (TDD red-green-refactor)."""

    def test_table_name(self):
        """Table name should be 'event_outbox'."""
        assert OutboxModel.__tablename__ == "event_outbox"

    def test_has_id_column(self):
        """Should have id column as UUID primary key."""
        columns = {c.name: c for c in OutboxModel.__table__.columns}
        assert "id" in columns
        assert columns["id"].primary_key

    def test_has_event_id_column(self):
        """Should have event_id column as UUID, unique, not nullable."""
        columns = {c.name: c for c in OutboxModel.__table__.columns}
        assert "event_id" in columns
        assert columns["event_id"].unique
        assert not columns["event_id"].nullable

    def test_has_event_type_column(self):
        """Should have event_type column as String(100), not nullable."""
        columns = {c.name: c for c in OutboxModel.__table__.columns}
        assert "event_type" in columns
        assert not columns["event_type"].nullable

    def test_has_payload_column(self):
        """Should have payload column as JSONB, not nullable."""
        columns = {c.name: c for c in OutboxModel.__table__.columns}
        assert "payload" in columns
        assert not columns["payload"].nullable

    def test_has_status_column(self):
        """Should have status column as String(20), not nullable."""
        columns = {c.name: c for c in OutboxModel.__table__.columns}
        assert "status" in columns
        assert not columns["status"].nullable

    def test_has_created_at_column(self):
        """Should have created_at column as DateTime, not nullable."""
        columns = {c.name: c for c in OutboxModel.__table__.columns}
        assert "created_at" in columns
        assert not columns["created_at"].nullable

    def test_has_published_at_column(self):
        """Should have published_at column as DateTime, nullable."""
        columns = {c.name: c for c in OutboxModel.__table__.columns}
        assert "published_at" in columns
        assert columns["published_at"].nullable

    def test_has_retry_count_column(self):
        """Should have retry_count column as Integer, not nullable."""
        columns = {c.name: c for c in OutboxModel.__table__.columns}
        assert "retry_count" in columns
        assert not columns["retry_count"].nullable

    def test_has_max_retries_column(self):
        """Should have max_retries column as Integer, not nullable."""
        columns = {c.name: c for c in OutboxModel.__table__.columns}
        assert "max_retries" in columns
        assert not columns["max_retries"].nullable

    def test_has_error_message_column(self):
        """Should have error_message column as String(1000), nullable."""
        columns = {c.name: c for c in OutboxModel.__table__.columns}
        assert "error_message" in columns
        assert columns["error_message"].nullable

    def test_check_constraint_status_values(self):
        """Should have CHECK constraint for valid status values."""
        constraints = OutboxModel.__table__.constraints
        status_constraints = [c for c in constraints if hasattr(c, "sqltext") and "status" in str(c.sqltext)]
        assert len(status_constraints) > 0

    def test_check_constraint_retry_count_positive(self):
        """Should have CHECK constraint for retry_count >= 0."""
        constraints = OutboxModel.__table__.constraints
        retry_constraints = [
            c for c in constraints if hasattr(c, "sqltext") and "retry_count" in str(c.sqltext) and ">=" in str(c.sqltext)
        ]
        assert len(retry_constraints) > 0

    def test_check_constraint_max_retries_positive(self):
        """Should have CHECK constraint for max_retries >= 0."""
        constraints = OutboxModel.__table__.constraints
        max_retry_constraints = [
            c for c in constraints if hasattr(c, "sqltext") and "max_retries" in str(c.sqltext) and ">=" in str(c.sqltext)
        ]
        assert len(max_retry_constraints) > 0

    def test_can_instantiate_with_minimal_fields(self):
        """Should be able to create an instance with required fields."""
        from datetime import datetime
        from uuid import uuid4

        instance = OutboxModel(
            event_id=uuid4(),
            event_type="TestEvent",
            payload={"key": "value"},
            created_at=datetime.now(),
        )
        assert instance.event_type == "TestEvent"
        assert instance.status == "pending"
        assert instance.retry_count == 0
        assert instance.max_retries == 3

    def test_inherits_from_declarative_base(self):
        """OutboxModel should inherit from a DeclarativeBase."""
        assert issubclass(OutboxModel, DeclarativeBase) or hasattr(OutboxModel, "__mapper__")
