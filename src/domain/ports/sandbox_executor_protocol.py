"""SandboxExecutorProtocol — domain port for sandbox execution.

This protocol defines the interface for sandbox execution adapters.
Infrastructure layer implements this protocol (e.g., DockerSandboxAdapter).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SandboxExecutorProtocol(Protocol):
    """Protocol for sandbox execution (implemented by infrastructure).

    Defines the interface for starting, executing code in, and stopping
    sandboxed containers for session isolation.
    """

    async def start_container(self, session_id: str) -> None:
        """Start a sandbox container for the given session.

        Args:
            session_id: Session identifier
        """
        ...

    async def execute_code(self, session_id: str, code: str) -> dict[str, Any]:
        """Execute code in the sandbox.

        Args:
            session_id: Session identifier
            code: Code to execute

        Returns:
            Execution result dictionary with status, output, etc.
        """
        ...

    async def stop_container(self, session_id: str) -> None:
        """Stop the sandbox container.

        Args:
            session_id: Session identifier
        """
        ...
