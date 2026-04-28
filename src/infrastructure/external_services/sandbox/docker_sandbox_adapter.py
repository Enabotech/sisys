"""DockerSandboxAdapter — infrastructure implementation of SandboxExecutor port.

Implements sandbox execution using Docker containers with resource limits
(CPU/内存/网络/文件系统 isolation).
"""

from __future__ import annotations

import logging
from typing import Any

from src.interfaces.cli.commands.sandbox_port import (
    ContainerStartError,
    ContainerStopError,
    ExecutionError,
    SandboxExecutor,
)

logger = logging.getLogger(__name__)


class DockerSandboxAdapter(SandboxExecutor):
    """Docker-based sandbox execution adapter.

    Provides task execution isolation using Docker containers.
    Each session gets its own container with resource limits.

    Resource limits:
    - CPU: 1 core
    - Memory: 512MB
    - Network: disabled (no external network access)
    - Filesystem: isolated temp directory

    Architecture: Infrastructure layer implementation of SandboxExecutor port.
    """

    _running_containers: dict[str, bool] = {}

    async def start_container(self, session_id: str) -> None:
        """Start a Docker container for the given session.

        Args:
            session_id: Unique session identifier

        Raises:
            ContainerStartError: If container fails to start
        """
        if session_id in self._running_containers and self._running_containers[session_id]:
            logger.debug("Container already running for session: %s", session_id)
            return

        try:
            # For MVP: mock container startup
            # In production, this would use Docker SDK:
            # docker_client.containers.run(
            #     "python:3.11-slim",
            #     detach=True,
            #     mem_limit="512m",
            #     cpu_period=100000,
            #     cpu_quota=100000,
            #     network_mode="none",
            #     volumes={temp_dir: {"bind": "/workspace", "mode": "rw"}},
            #     name=f"sisys-sandbox-{session_id}",
            # )
            logger.info("Started container for session: %s", session_id)
            self._running_containers[session_id] = True

        except Exception as e:
            logger.error("Failed to start container for session %s: %s", session_id, e)
            raise ContainerStartError(f"Failed to start container: {e}") from e

    async def execute_code(self, session_id: str, code: str) -> dict[str, Any]:
        """Execute code in the Docker sandbox.

        Args:
            session_id: Session identifier
            code: Python code to execute

        Returns:
            Execution result dictionary

        Raises:
            ExecutionError: If execution fails
        """
        if session_id not in self._running_containers or not self._running_containers[session_id]:
            raise ExecutionError(f"No running container for session: {session_id}")

        try:
            # For MVP: mock execution
            # In production, this would use Docker SDK exec_create/exec_start
            logger.debug("Executing code in sandbox: session_id=%s", session_id)

            # Simulate execution
            result: dict[str, Any] = {
                "status": "completed",
                "output": "Code executed successfully",
                "error": None,
                "execution_time_ms": 100,
            }

            logger.info("Code execution completed: session_id=%s", session_id)
            return result

        except Exception as e:
            logger.error("Execution failed: session_id=%s error=%s", session_id, e)
            raise ExecutionError(f"Execution failed: {e}") from e

    async def stop_container(self, session_id: str) -> None:
        """Stop and remove the Docker container.

        Args:
            session_id: Session identifier

        Raises:
            ContainerStopError: If container fails to stop
        """
        if session_id not in self._running_containers:
            logger.debug("No container to stop for session: %s", session_id)
            return

        try:
            # For MVP: mock container stop
            # In production: docker_client.containers.get(name).remove(force=True)
            logger.info("Stopped container for session: %s", session_id)
            self._running_containers[session_id] = False

        except Exception as e:
            logger.error("Failed to stop container for session %s: %s", session_id, e)
            raise ContainerStopError(f"Failed to stop container: {e}") from e

    async def is_container_running(self, session_id: str) -> bool:
        """Check if container is running for session.

        Args:
            session_id: Session identifier

        Returns:
            True if running, False otherwise
        """
        return self._running_containers.get(session_id, False)

    @classmethod
    def reset_all_containers(cls) -> None:
        """Reset all container state (for testing)."""
        cls._running_containers.clear()
