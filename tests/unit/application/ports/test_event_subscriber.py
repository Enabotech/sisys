"""Tests for EventSubscriber interface - Protocol version."""

from __future__ import annotations

import inspect

from src.application.ports.event_subscriber import EventSubscriber


class TestEventSubscriberIsProtocol:
    """Test that EventSubscriber is a Protocol."""

    def test_is_protocol(self) -> None:
        """EventSubscriber should be a Protocol."""
        assert inspect.isclass(EventSubscriber)
        assert hasattr(EventSubscriber, "_is_protocol")

    def test_has_required_methods(self) -> None:
        """EventSubscriber should have all required methods."""
        required = ["subscribe", "subscribe_async", "start", "close"]
        for method_name in required:
            assert hasattr(EventSubscriber, method_name), f"Missing method: {method_name}"


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


class TestEventSubscriberSignatures:
    """Test EventSubscriber method signatures."""

    def test_subscribe_signature(self) -> None:
        """subscribe should have correct signature."""
        sig = inspect.signature(EventSubscriber.subscribe)
        params = list(sig.parameters.keys())
        assert "event_type" in params
        assert "handler" in params

    def test_subscribe_async_signature(self) -> None:
        """subscribe_async should have correct signature."""
        sig = inspect.signature(EventSubscriber.subscribe_async)
        params = list(sig.parameters.keys())
        assert "event_type" in params
        assert "handler" in params

    def test_subscribe_is_async(self) -> None:
        """subscribe should be an async method."""
        import asyncio

        assert asyncio.iscoroutinefunction(EventSubscriber.subscribe)

    def test_subscribe_async_is_async(self) -> None:
        """subscribe_async should be an async method."""
        import asyncio

        assert asyncio.iscoroutinefunction(EventSubscriber.subscribe_async)

    def test_start_is_async(self) -> None:
        """start should be an async method."""
        import asyncio

        assert asyncio.iscoroutinefunction(EventSubscriber.start)

    def test_close_is_async(self) -> None:
        """close should be an async method."""
        import asyncio

        assert asyncio.iscoroutinefunction(EventSubscriber.close)
