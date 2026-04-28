"""Tests for DockerSandboxAdapter infrastructure implementation."""


import pytest

from src.infrastructure.external_services.sandbox.docker_sandbox_adapter import (
    ContainerStartError,
    ContainerStopError,
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

    @pytest.mark.asyncio
    async def test_execute_code_raises_when_not_running(self) -> None:
        """Coverage: execute_code raises ExecutionError when container not running."""
        adapter = DockerSandboxAdapter()

        with pytest.raises(Exception) as exc_info:
            await adapter.execute_code("never-started", "print('test')")

        assert "No running container" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_is_container_running_returns_false_for_unknown(self) -> None:
        """Coverage: is_container_running returns False for unknown session."""
        adapter = DockerSandboxAdapter()

        result = await adapter.is_container_running("unknown-session")

        assert result is False

    @pytest.mark.asyncio
    async def test_start_container_idempotent_already_running(self) -> None:
        """Coverage: start_container early return when already running."""
        adapter = DockerSandboxAdapter()
        await adapter.start_container("session-1")
        DockerSandboxAdapter._running_containers["session-1"] = True  # already running

        await adapter.start_container("session-1")  # Should early return

        # Container should still be running
        assert await adapter.is_container_running("session-1") is True

    @pytest.mark.asyncio
    async def test_start_container_exception_handler(self) -> None:
        """Coverage: start_container exception handler (lines 68-70).

        Note: This test verifies the exception handler exists and raises
        ContainerStartError. In MVP, the try block contains mock code,
        so we simulate a production-like failure.
        """
        from unittest.mock import MagicMock

        from src.infrastructure.external_services.sandbox import docker_sandbox_adapter as dsa_module

        adapter = DockerSandboxAdapter()
        original_logger = dsa_module.logger

        # Create a mock logger that raises on info call
        mock_logger = MagicMock()
        mock_logger.info = MagicMock(side_effect=Exception("logger failed"))
        mock_logger.debug = original_logger.debug
        mock_logger.error = original_logger.error

        dsa_module.logger = mock_logger  # type: ignore
        try:
            with pytest.raises(ContainerStartError):
                await adapter.start_container("session-exc")
        finally:
            dsa_module.logger = original_logger

    @pytest.mark.asyncio
    async def test_execute_code_exception_handler(self) -> None:
        """Coverage: execute_code exception handler (lines 104-106).

        Note: In MVP, we simulate a production-like failure.
        """
        from unittest.mock import MagicMock

        from src.infrastructure.external_services.sandbox import docker_sandbox_adapter as dsa_module

        adapter = DockerSandboxAdapter()
        await adapter.start_container("session-exc")

        original_logger = dsa_module.logger

        # Create a mock logger that raises on debug call
        mock_logger = MagicMock()
        mock_logger.debug = MagicMock(side_effect=Exception("logger failed"))
        mock_logger.info = original_logger.info
        mock_logger.error = original_logger.error

        dsa_module.logger = mock_logger  # type: ignore
        try:
            with pytest.raises(ExecutionError):
                await adapter.execute_code("session-exc", "print('test')")
        finally:
            dsa_module.logger = original_logger

    @pytest.mark.asyncio
    async def test_stop_container_exception_handler(self) -> None:
        """Coverage: stop_container exception handler (lines 127-129).

        Note: In MVP, we simulate a production-like failure.
        """
        from unittest.mock import MagicMock

        from src.infrastructure.external_services.sandbox import docker_sandbox_adapter as dsa_module

        adapter = DockerSandboxAdapter()
        await adapter.start_container("session-stop")

        original_logger = dsa_module.logger

        # Create a mock logger that raises on info call
        mock_logger = MagicMock()
        mock_logger.info = MagicMock(side_effect=Exception("logger failed"))
        mock_logger.debug = original_logger.debug
        mock_logger.error = original_logger.error

        dsa_module.logger = mock_logger  # type: ignore
        try:
            with pytest.raises(ContainerStopError):
                await adapter.stop_container("session-stop")
        finally:
            dsa_module.logger = original_logger
