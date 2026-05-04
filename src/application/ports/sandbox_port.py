"""SandboxExecutor port — application layer port for sandbox execution.

This port defines the interface for task execution in isolated sandboxes.
Infrastructure layer implements this port using Docker or gVisor.

Hexagonal Architecture:
    - Port defined in application layer (allowed: infrastructure can implement)
    - Implementation in infrastructure layer
    - Interfaces layer uses the port from application layer
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SandboxExecutor(ABC):
    """Port interface for sandbox execution.

    Implementations:
    - DockerSandboxAdapter: Uses Docker containers for isolation
    - GvisorSandboxAdapter: Uses gVisor for stronger isolation (V2+)

    Architecture: Hexagonal architecture port defined in application layer.
    Infrastructure layer provides concrete implementations.
    """

    @abstractmethod
    async def start_container(self, session_id: str) -> None:
        """Start a sandbox container for the given session.

        Args:
            session_id: Unique session identifier

        Raises:
            SandboxError: If container fails to start
        """
        ...

    @abstractmethod
    async def execute_code(self, session_id: str, code: str) -> dict[str, Any]:
        """Execute code in the sandbox.

        Args:
            session_id: Session identifier
            code: Code to execute

        Returns:
            Execution result dictionary with keys: status, output, error

        Raises:
            SandboxError: If execution fails
        """
        ...

    @abstractmethod
    async def stop_container(self, session_id: str) -> None:
        """Stop and cleanup the sandbox container.

        Args:
            session_id: Session identifier

        Raises:
            SandboxError: If container fails to stop
        """
        ...

    @abstractmethod
    async def is_container_running(self, session_id: str) -> bool:
        """Check if a container is running for the session.

        Args:
            session_id: Session identifier

        Returns:
            True if container is running, False otherwise
        """
        ...


class SandboxError(Exception):
    """Base exception for sandbox-related errors."""

    pass


class ContainerStartError(SandboxError):
    """Raised when container fails to start."""

    pass


class ExecutionError(SandboxError):
    """Raised when code execution fails."""

    pass


class ContainerStopError(SandboxError):
    """Raised when container fails to stop."""

    pass
