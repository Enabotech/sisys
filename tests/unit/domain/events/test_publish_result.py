"""Tests for PublishResult domain type."""

from __future__ import annotations

from dataclasses import is_dataclass

from src.domain.events.publish_result import PublishResult


class TestPublishResultFields:
    """Test PublishResult field definitions."""

    def test_is_a_dataclass(self) -> None:
        """PublishResult should be a frozen dataclass."""
        assert is_dataclass(PublishResult)
        # Check frozen=True
        assert getattr(PublishResult, "__dataclass_fields__", {}).get("event_id") is not None

    def test_event_id_field_exists(self) -> None:
        """PublishResult should have event_id field."""
        result = PublishResult(event_id="test-123")
        assert result.event_id == "test-123"

    def test_redis_success_default_false(self) -> None:
        """redis_success should default to False."""
        result = PublishResult(event_id="test-123")
        assert result.redis_success is False

    def test_outbox_saved_default_false(self) -> None:
        """outbox_saved should default to False."""
        result = PublishResult(event_id="test-123")
        assert result.outbox_saved is False

    def test_redis_error_default_none(self) -> None:
        """redis_error should default to None."""
        result = PublishResult(event_id="test-123")
        assert result.redis_error is None

    def test_outbox_error_default_none(self) -> None:
        """outbox_error should default to None."""
        result = PublishResult(event_id="test-123")
        assert result.outbox_error is None

    def test_all_fields_can_be_set(self) -> None:
        """All fields should be settable via constructor."""
        result = PublishResult(
            event_id="test-123",
            redis_success=True,
            redis_error="Connection refused",
            outbox_saved=True,
            outbox_error=None,
        )
        assert result.event_id == "test-123"
        assert result.redis_success is True
        assert result.redis_error == "Connection refused"
        assert result.outbox_saved is True
        assert result.outbox_error is None


class TestPublishResultProperties:
    """Test PublishResult computed properties."""

    def test_is_success_true_when_redis_success(self) -> None:
        """is_success should be True when redis_success is True."""
        result = PublishResult(event_id="test-123", redis_success=True)
        assert result.is_success is True

    def test_is_success_true_when_outbox_saved(self) -> None:
        """is_success should be True when outbox_saved is True."""
        result = PublishResult(event_id="test-123", outbox_saved=True)
        assert result.is_success is True

    def test_is_success_true_when_both_true(self) -> None:
        """is_success should be True when both channels succeed."""
        result = PublishResult(event_id="test-123", redis_success=True, outbox_saved=True)
        assert result.is_success is True

    def test_is_success_false_when_both_false(self) -> None:
        """is_success should be False when both channels fail."""
        result = PublishResult(event_id="test-123", redis_success=False, outbox_saved=False)
        assert result.is_success is False

    def test_is_full_failure_true_when_both_false(self) -> None:
        """is_full_failure should be True when all channels fail."""
        result = PublishResult(event_id="test-123", redis_success=False, outbox_saved=False)
        assert result.is_full_failure is True

    def test_is_full_failure_false_when_redis_success(self) -> None:
        """is_full_failure should be False when redis_success is True."""
        result = PublishResult(event_id="test-123", redis_success=True)
        assert result.is_full_failure is False

    def test_is_full_failure_false_when_outbox_saved(self) -> None:
        """is_full_failure should be False when outbox_saved is True."""
        result = PublishResult(event_id="test-123", outbox_saved=True)
        assert result.is_full_failure is False

    def test_partial_error_returns_outbox_error_first(self) -> None:
        """partial_error should return outbox_error first when both exist."""
        result = PublishResult(
            event_id="test-123",
            outbox_error="Outbox failed",
            redis_error="Redis failed",
        )
        assert result.partial_error == "Outbox failed"

    def test_partial_error_returns_redis_error_when_no_outbox_error(self) -> None:
        """partial_error should return redis_error when outbox_error is None."""
        result = PublishResult(
            event_id="test-123",
            redis_error="Redis failed",
        )
        assert result.partial_error == "Redis failed"

    def test_partial_error_returns_none_when_no_errors(self) -> None:
        """partial_error should return None when no errors exist."""
        result = PublishResult(event_id="test-123", redis_success=True, outbox_saved=True)
        assert result.partial_error is None


class TestPublishResultImmutability:
    """Test that PublishResult is immutable (frozen dataclass)."""

    def test_is_frozen(self) -> None:
        """PublishResult should be a frozen dataclass."""
        import dataclasses

        assert dataclasses.is_dataclass(PublishResult)
        params = getattr(PublishResult, "__dataclass_params__", None)
        assert params is not None
        assert params.frozen is True


class TestPublishResultDomainLayerZeroDependency:
    """Verify PublishResult has zero external dependencies."""

    def test_no_external_imports(self) -> None:
        """PublishResult should only use dataclass and typing from stdlib."""
        import src.domain.events.publish_result as module

        # Get all imports from the module
        source_file = getattr(module, "__file__", None)
        if source_file:
            with open(source_file) as f:
                content = f.read()

            # Should not have imports from external packages
            external_patterns = [
                "from pydantic",
                "import pydantic",
                "from sqlalchemy",
                "import sqlalchemy",
                "from redis",
                "import redis",
                "from aio_pika",
                "import aio_pika",
                "from prefect",
                "import prefect",
                "from langgraph",
                "import langgraph",
            ]
            for pattern in external_patterns:
                assert pattern not in content, f"Found external dependency: {pattern}"
