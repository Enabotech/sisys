"""Tests for EventPublisher interface."""

from __future__ import annotations

from abc import ABC

import pytest

from src.interfaces.event_publisher import EventPublisher


class TestEventPublisherIsAbstract:
    """Test that EventPublisher is an abstract class."""

    def test_is_abc(self) -> None:
        """EventPublisher should be an ABC."""
        assert issubclass(EventPublisher, ABC)

    def test_cannot_instantiate_directly(self) -> None:
        """EventPublisher cannot be instantiated directly."""
        with pytest.raises(TypeError):
            EventPublisher()  # type: ignore[abstract]


class TestEventPublisherHasPublishMethod:
    """Test that EventPublisher has the required publish method."""

    def test_has_abstract_publish_method(self) -> None:
        """EventPublisher should have an abstract publish method."""
        # The publish method should be marked as abstract
        assert hasattr(EventPublisher, "publish")
        # It should be an abstract method
        assert getattr(EventPublisher.publish, "__isabstractmethod__", False)


class TestEventPublisherSignature:
    """Test EventPublisher.publish method signature."""

    def test_publish_is_async(self) -> None:
        """publish should be an async method."""
        import inspect

        assert inspect.iscoroutinefunction(EventPublisher.publish)

    def test_publish_returns_publish_result(self) -> None:
        """publish should be annotated to return PublishResult."""
        import typing

        hints = typing.get_type_hints(EventPublisher.publish)
        assert "return" in hints
        # The return type should be PublishResult
        assert "PublishResult" in str(hints.get("return"))
