"""Tests for DockerSandboxAdapter infrastructure implementation."""

import pytest

from src.infrastructure.sandbox.docker_sandbox_adapter import (
    DockerSandboxAdapter,
    ExecutionError,
)


class TestDockerSandboxAdapter:
    """TDD tests for DockerSandboxAdapter."""

    @pytest.fixture(autouse=True)
    def reset_containers(self):
        """Reset all containers before each test."""
        DockerSandboxAdapter.reset_all_containers()
        yield
        DockerSandboxAdapter.reset_all_containers()

    @pytest.mark.asyncio
    async def test_start_container_creates_container(self) -> None:
        """RED: start_container should mark container as running."""
        adapter = DockerSandboxAdapter()

        await adapter.start_container("session-1")

        assert await adapter.is_container_running("session-1") is True

    @pytest.mark.asyncio
    async def test_start_container_idempotent(self) -> None:
        """RED: start_container should be safe to call multiple times."""
        adapter = DockerSandboxAdapter()

        await adapter.start_container("session-1")
        await adapter.start_container("session-1")  # Second call should not error

        assert await adapter.is_container_running("session-1") is True

    @pytest.mark.asyncio
    async def test_execute_code_requires_running_container(self) -> None:
        """RED: execute_code should fail if container not running."""
        adapter = DockerSandboxAdapter()

        with pytest.raises(ExecutionError):
            await adapter.execute_code("session-not-running", "print('hello')")

    @pytest.mark.asyncio
    async def test_execute_code_returns_result(self) -> None:
        """RED: execute_code should return execution result dict."""
        adapter = DockerSandboxAdapter()
        await adapter.start_container("session-1")

        result = await adapter.execute_code("session-1", "print('hello')")

        assert result["status"] == "completed"
        assert "output" in result

    @pytest.mark.asyncio
    async def test_stop_container(self) -> None:
        """RED: stop_container should mark container as not running."""
        adapter = DockerSandboxAdapter()
        await adapter.start_container("session-1")

        await adapter.stop_container("session-1")

        assert await adapter.is_container_running("session-1") is False

    @pytest.mark.asyncio
    async def test_stop_container_idempotent(self) -> None:
        """RED: stop_container should be safe to call multiple times."""
        adapter = DockerSandboxAdapter()
        await adapter.start_container("session-1")

        await adapter.stop_container("session-1")
        await adapter.stop_container("session-1")  # Second call should not error

        assert await adapter.is_container_running("session-1") is False

    @pytest.mark.asyncio
    async def test_stop_nonexistent_container(self) -> None:
        """RED: stop_container should handle non-existent container gracefully."""
        adapter = DockerSandboxAdapter()

        # Should not raise
        await adapter.stop_container("nonexistent-session")

        assert await adapter.is_container_running("nonexistent-session") is False
