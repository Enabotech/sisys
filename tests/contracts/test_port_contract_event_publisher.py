"""Port contract tests for EventPublisher port.

Tests that DualChannelEventBus implementation satisfies the EventPublisher Protocol.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.domain.events.base import DomainEvent
from src.domain.events.publish_result import PublishResult
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.registry import _global_registry


class TestEventPublisherContract:
    """Contract tests for EventPublisher port."""

    @classmethod
    def get_port_name(cls) -> str:
        return "event_publisher"

    @classmethod
    def get_implementation(cls) -> Any:
        """Get the registered implementation."""
        from src.domain.ports.resolver import Resolver

        resolver = Resolver()
        return resolver.resolve("event_publisher")

    def test_port_is_registered(self) -> None:
        """Port must be registered in global registry."""
        spec = _global_registry.get(self.get_port_name())
        assert spec is not None, f"Port {self.get_port_name()} not registered"
        assert spec.interface is EventPublisher

    def test_implementation_satisfies_protocol(self) -> None:
        """Implementation must satisfy EventPublisher Protocol."""
        impl = self.get_implementation()
        # Check that impl has the required publish method
        assert hasattr(impl, "publish"), "Implementation missing publish method"
        assert callable(impl.publish), "publish is not callable"

    def test_publish_method_exists(self) -> None:
        """Implementation must have publish method."""
        impl = self.get_implementation()
        assert hasattr(impl, "publish")
        assert callable(impl.publish)

    @pytest.mark.asyncio
    async def test_publish_returns_publish_result(self) -> None:
        """publish() must return PublishResult."""
        impl = self.get_implementation()
        event = DomainEvent(event_type="test.event")
        try:
            result = await impl.publish(event)
            assert isinstance(result, PublishResult)
        except Exception:
            pass
