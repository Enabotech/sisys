"""Test HealthCheckPort - Red Phase (Test First)."""
from __future__ import annotations

import pytest

from src.domain.ports.health_check import HealthCheckPort


class TestHealthCheckPort:
    """HealthCheckPort interface tests."""

    def test_health_check_port_is_abstract(self):
        """HealthCheckPort should be abstract class."""
        with pytest.raises(TypeError):
            HealthCheckPort()

    def test_check_method_is_abstract(self):
        """check() should be abstract method."""
        port = HealthCheckPort.__abstractmethods__
        assert "check" in port

    def test_close_method_is_abstract(self):
        """close() should be abstract method."""
        port = HealthCheckPort.__abstractmethods__
        assert "close" in port


class ConcreteHealthCheckAdapter(HealthCheckPort):
    """Concrete implementation for testing."""

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
    """Concrete implementation should work."""
    adapter = ConcreteHealthCheckAdapter()
    result = await adapter.check()
    assert result is True
    assert adapter._check_called is True


@pytest.mark.asyncio
async def test_close_releases_resources():
    """close() should be callable."""
    adapter = ConcreteHealthCheckAdapter()
    await adapter.close()
    assert adapter._close_called is True
