"""Tests for EventPublisher interface."""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock

from src.domain.ports.event_publisher import EventPublisher


class TestEventPublisherSignature:
    """Test EventPublisher.publish method signature — structural check for type contract."""

    def test_publish_is_async(self) -> None:
        """publish should be an async method."""
        assert inspect.iscoroutinefunction(EventPublisher.publish), "publish must be async"

    def test_publish_returns_publish_result(self) -> None:
        """publish return type annotation should reference PublishResult."""
        import typing

        hints = typing.get_type_hints(EventPublisher.publish)
        assert "return" in hints
        assert "PublishResult" in str(hints.get("return"))


class TestEventPublisherMockBehavior:
    """Mock behavior tests — verify Protocol contract via spec约束."""

    async def test_mock_publish_verified(self):
        """Mock publish should be verifiable via assert_called_once."""
        mock = AsyncMock(spec=EventPublisher)
        mock.publish.return_value = type("PublishResult", (), {"redis_success": True, "outbox_saved": False})()

        result = await mock.publish({"event_type": "TestEvent", "data": {"key": "value"}})
        assert result.redis_success is True
        mock.publish.assert_called_once()
