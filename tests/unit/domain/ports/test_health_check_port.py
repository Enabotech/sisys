"""Test HealthCheckPort - Protocol Interface Tests."""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock

import pytest

from src.domain.ports.health_check import HealthCheckPort


class TestHealthCheckPortSignature:
    """Structural signature tests — verify async contract for type checker."""

    def test_check_is_async(self) -> None:
        """check should be async."""
        assert inspect.iscoroutinefunction(HealthCheckPort.check), "check must be async"

    def test_close_is_async(self) -> None:
        """close should be async."""
        assert inspect.iscoroutinefunction(HealthCheckPort.close), "close must be async"


class TestHealthCheckPortMockBehavior:
    """Mock behavior tests — verify Protocol contract via spec约束."""

    async def test_mock_check_verified(self):
        """Mock check should be verifiable via assert_called_once."""
        mock = AsyncMock(spec=HealthCheckPort)
        mock.check.return_value = True

        result = await mock.check()
        assert result is True
        mock.check.assert_called_once()

    async def test_mock_close_verified(self):
        """Mock close should be verifiable via assert_called_once."""
        mock = AsyncMock(spec=HealthCheckPort)
        mock.close.return_value = None

        await mock.close()
        mock.close.assert_called_once()


class ConcreteHealthCheckAdapter(HealthCheckPort):
    """Concrete implementation for integration tests."""

    def __init__(self):
        self._check_called = False
        self._close_called = False

    async def check(self) -> bool:
        self._check_called = True
        return True

    async def close(self) -> None:
        self._close_called = True


@pytest.mark.asyncio
async def test_concrete_implementation():
    """Concrete implementation should work (integration test)."""
    adapter = ConcreteHealthCheckAdapter()
    result = await adapter.check()
    assert result is True
    assert adapter._check_called is True


@pytest.mark.asyncio
async def test_close_releases_resources():
    """close() should be callable (integration test)."""
    adapter = ConcreteHealthCheckAdapter()
    await adapter.close()
    assert adapter._close_called is True
