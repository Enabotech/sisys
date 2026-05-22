"""Tests for PublishResult and ChannelResult domain types."""

from __future__ import annotations

from dataclasses import is_dataclass

from src.domain.events.publish_result import ChannelResult, PublishResult


class TestChannelResultFields:
    """Test ChannelResult field definitions."""

    def test_is_a_frozen_dataclass(self) -> None:
        """ChannelResult should be a frozen dataclass."""
        assert is_dataclass(ChannelResult)
        params = getattr(ChannelResult, "__dataclass_params__", None)
        assert params is not None
        assert params.frozen is True

    def test_required_fields(self) -> None:
        """ChannelResult should require channel_name and success."""
        cr = ChannelResult("realtime", True)
        assert cr.channel_name == "realtime"
        assert cr.success is True
        assert cr.error is None

    def test_error_optional(self) -> None:
        """ChannelResult error should default to None."""
        cr = ChannelResult("realtime", False, "connection refused")
        assert cr.error == "connection refused"


class TestPublishResultFields:
    """Test PublishResult field definitions."""

    def test_is_a_frozen_dataclass(self) -> None:
        """PublishResult should be a frozen dataclass."""
        assert is_dataclass(PublishResult)
        params = getattr(PublishResult, "__dataclass_params__", None)
        assert params is not None
        assert params.frozen is True

    def test_event_id_field_exists(self) -> None:
        """PublishResult should have event_id field."""
        result = PublishResult(event_id="test-123")
        assert result.event_id == "test-123"

    def test_results_default_empty(self) -> None:
        """results should default to empty tuple."""
        result = PublishResult(event_id="test-123")
        assert result.results == ()

    def test_results_accepts_channel_results(self) -> None:
        """results should accept ChannelResult tuples."""
        cr = ChannelResult("realtime", True)
        result = PublishResult(event_id="test-123", results=(cr,))
        assert len(result.results) == 1
        assert result.results[0].channel_name == "realtime"
        assert result.results[0].success is True


class TestPublishResultIsSuccess:
    """Test PublishResult.is_success property."""

    def test_is_success_false_when_no_results(self) -> None:
        """is_success should be False when results is empty."""
        result = PublishResult(event_id="test-123")
        assert result.is_success is False

    def test_is_success_true_when_single_channel_succeeds(self) -> None:
        """is_success should be True when the single channel succeeds."""
        result = PublishResult(
            event_id="test-123",
            results=(ChannelResult("realtime", True),),
        )
        assert result.is_success is True

    def test_is_success_false_when_single_channel_fails(self) -> None:
        """is_success should be False when the single channel fails."""
        result = PublishResult(
            event_id="test-123",
            results=(ChannelResult("realtime", False, "error"),),
        )
        assert result.is_success is False

    def test_is_success_true_when_all_channels_succeed(self) -> None:
        """is_success should be True when all channels succeed."""
        result = PublishResult(
            event_id="test-123",
            results=(
                ChannelResult("realtime", True),
                ChannelResult("reliable", True),
            ),
        )
        assert result.is_success is True

    def test_is_success_false_when_any_channel_fails(self) -> None:
        """is_success should be False when any channel fails."""
        result = PublishResult(
            event_id="test-123",
            results=(
                ChannelResult("realtime", True),
                ChannelResult("reliable", False, "db error"),
            ),
        )
        assert result.is_success is False


class TestPublishResultIsFullFailure:
    """Test PublishResult.is_full_failure property."""

    def test_is_full_failure_false_when_no_results(self) -> None:
        """is_full_failure should be False when results is empty."""
        result = PublishResult(event_id="test-123")
        assert result.is_full_failure is False

    def test_is_full_failure_true_when_all_channels_fail(self) -> None:
        """is_full_failure should be True when all channels fail."""
        result = PublishResult(
            event_id="test-123",
            results=(
                ChannelResult("realtime", False, "conn refused"),
                ChannelResult("reliable", False, "db error"),
            ),
        )
        assert result.is_full_failure is True

    def test_is_full_failure_false_when_any_channel_succeeds(self) -> None:
        """is_full_failure should be False when any channel succeeds."""
        result = PublishResult(
            event_id="test-123",
            results=(
                ChannelResult("realtime", True),
                ChannelResult("reliable", False, "db error"),
            ),
        )
        assert result.is_full_failure is False


class TestPublishResultPartialError:
    """Test PublishResult.partial_error property."""

    def test_partial_error_returns_first_failed_channel_error(self) -> None:
        """partial_error should return the first failed channel's error."""
        result = PublishResult(
            event_id="test-123",
            results=(
                ChannelResult("realtime", False, "Redis failed"),
                ChannelResult("reliable", False, "Outbox failed"),
            ),
        )
        assert result.partial_error == "Redis failed"

    def test_partial_error_returns_none_when_all_succeed(self) -> None:
        """partial_error should be None when all channels succeed."""
        result = PublishResult(
            event_id="test-123",
            results=(
                ChannelResult("realtime", True),
                ChannelResult("reliable", True),
            ),
        )
        assert result.partial_error is None

    def test_partial_error_returns_none_when_no_results(self) -> None:
        """partial_error should be None when results is empty."""
        result = PublishResult(event_id="test-123")
        assert result.partial_error is None

    def test_partial_error_skips_failed_without_error_message(self) -> None:
        """partial_error should skip failures that have no error message."""
        result = PublishResult(
            event_id="test-123",
            results=(
                ChannelResult("realtime", False),
                ChannelResult("reliable", False, "Outbox failed"),
            ),
        )
        assert result.partial_error == "Outbox failed"


class TestPublishResultBackwardCompat:
    """Test backward-compatible properties (redis_success, outbox_saved, etc.)."""

    def test_redis_success_true(self) -> None:
        """redis_success should be True when realtime channel succeeds."""
        result = PublishResult(
            event_id="test-123",
            results=(ChannelResult("realtime", True),),
        )
        assert result.redis_success is True

    def test_redis_success_false_when_failed(self) -> None:
        """redis_success should be False when realtime channel fails."""
        result = PublishResult(
            event_id="test-123",
            results=(ChannelResult("realtime", False, "error"),),
        )
        assert result.redis_success is False

    def test_redis_success_false_when_no_results(self) -> None:
        """redis_success should be False when no results."""
        result = PublishResult(event_id="test-123")
        assert result.redis_success is False

    def test_redis_error_returns_error(self) -> None:
        """redis_error should return error when realtime channel fails."""
        result = PublishResult(
            event_id="test-123",
            results=(ChannelResult("realtime", False, "Connection refused"),),
        )
        assert result.redis_error == "Connection refused"

    def test_redis_error_none_when_succeeded(self) -> None:
        """redis_error should be None when realtime channel succeeds."""
        result = PublishResult(
            event_id="test-123",
            results=(ChannelResult("realtime", True),),
        )
        assert result.redis_error is None

    def test_outbox_saved_true(self) -> None:
        """outbox_saved should be True when reliable channel succeeds."""
        result = PublishResult(
            event_id="test-123",
            results=(ChannelResult("reliable", True),),
        )
        assert result.outbox_saved is True

    def test_outbox_saved_false_when_no_results(self) -> None:
        """outbox_saved should be False when no results."""
        result = PublishResult(event_id="test-123")
        assert result.outbox_saved is False

    def test_outbox_error_returns_error(self) -> None:
        """outbox_error should return error when reliable channel fails."""
        result = PublishResult(
            event_id="test-123",
            results=(ChannelResult("reliable", False, "DB failed"),),
        )
        assert result.outbox_error == "DB failed"

    def test_outbox_error_none_when_succeeded(self) -> None:
        """outbox_error should be None when reliable channel succeeds."""
        result = PublishResult(
            event_id="test-123",
            results=(ChannelResult("reliable", True),),
        )
        assert result.outbox_error is None


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

        source_file = getattr(module, "__file__", None)
        if source_file:
            with open(source_file) as f:
                content = f.read()

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
