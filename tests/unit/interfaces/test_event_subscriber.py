"""Tests for EventSubscriber interface."""

from __future__ import annotations

from abc import ABC

import pytest

from src.application.ports.event_subscriber import EventSubscriber


class TestEventSubscriberIsAbstract:
    """Test that EventSubscriber is an abstract class."""

    def test_is_abc(self) -> None:
        """EventSubscriber should be an ABC."""
        assert issubclass(EventSubscriber, ABC)

    def test_cannot_instantiate_directly(self) -> None:
        """EventSubscriber cannot be instantiated directly."""
        with pytest.raises(TypeError):
            EventSubscriber()  # type: ignore[abstract]


class TestEventSubscriberMethods:
    """Test that EventSubscriber has all required methods."""

    def test_has_subscribe_method(self) -> None:
        """EventSubscriber should have subscribe method."""
        assert hasattr(EventSubscriber, "subscribe")

    def test_has_subscribe_async_method(self) -> None:
        """EventSubscriber should have subscribe_async method."""
        assert hasattr(EventSubscriber, "subscribe_async")

    def test_has_start_method(self) -> None:
        """EventSubscriber should have start method."""
        assert hasattr(EventSubscriber, "start")

    def test_has_close_method(self) -> None:
        """EventSubscriber should have close method."""
        assert hasattr(EventSubscriber, "close")

    def test_all_methods_are_abstract(self) -> None:
        """All methods should be abstract."""
        for method_name in ["subscribe", "subscribe_async", "start", "close"]:
            method = getattr(EventSubscriber, method_name)
            assert getattr(method, "__isabstractmethod__", False), f"{method_name} should be abstract"


class TestEventSubscriberSignatures:
    """Test EventSubscriber method signatures."""

    def test_subscribe_is_async(self) -> None:
        """subscribe should be an async method."""
        import inspect

        assert inspect.iscoroutinefunction(EventSubscriber.subscribe)

    def test_subscribe_async_is_async(self) -> None:
        """subscribe_async should be an async method."""
        import inspect

        assert inspect.iscoroutinefunction(EventSubscriber.subscribe_async)

    def test_start_is_async(self) -> None:
        """start should be an async method."""
        import inspect

        assert inspect.iscoroutinefunction(EventSubscriber.start)

    def test_close_is_async(self) -> None:
        """close should be an async method."""
        import inspect

        assert inspect.iscoroutinefunction(EventSubscriber.close)
