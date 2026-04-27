"""SessionNamespaceManager — manages session to namespace mapping and resource limits.

Ensures tasks with the same session_id run in the same namespace for
state sharing, while different sessions are isolated from each other.
"""

from __future__ import annotations

import logging
from typing import Any

from src.interfaces.sandbox.sandbox_port import SandboxExecutor

logger = logging.getLogger(__name__)


class SessionNamespaceManager:
    """Manages session to namespace mapping and resource limits.

    Responsibilities:
    - Map session_id to namespace/container
    - Enforce resource limits per session
    - Track active sessions
    - Cleanup resources when sessions end

    Architecture: Infrastructure layer, used by ExecuteService.
    """

    def __init__(self, sandbox: SandboxExecutor | None = None):
        """Initialize SessionNamespaceManager.

        Args:
            sandbox: Sandbox executor for container management. None for testing.
        """
        self._sandbox = sandbox
        self._active_sessions: dict[str, dict[str, Any]] = {}

    async def get_or_create_namespace(self, session_id: str) -> str:
        """Get existing namespace or create new one for session.

        Args:
            session_id: Session identifier

        Returns:
            Namespace identifier (same as session_id for simplicity)
        """
        if session_id in self._active_sessions:
            logger.debug("Reusing namespace for session: %s", session_id)
            return session_id

        # Create new namespace
        if self._sandbox:
            await self._sandbox.start_container(session_id)

        self._active_sessions[session_id] = {
            "namespace": session_id,
            "created_at": "now",  # Would use datetime in production
            "resource_usage": {"cpu": 0, "memory": 0},
        }

        logger.info("Created namespace for session: %s", session_id)
        return session_id

    async def release_namespace(self, session_id: str) -> None:
        """Release namespace and cleanup resources for session.

        Args:
            session_id: Session identifier
        """
        if session_id not in self._active_sessions:
            logger.debug("No namespace to release for session: %s", session_id)
            return

        if self._sandbox:
            await self._sandbox.stop_container(session_id)

        del self._active_sessions[session_id]
        logger.info("Released namespace for session: %s", session_id)

    def get_active_sessions(self) -> list[str]:
        """Get list of active session IDs.

        Returns:
            List of active session IDs
        """
        return list(self._active_sessions.keys())

    def is_session_active(self, session_id: str) -> bool:
        """Check if session is active.

        Args:
            session_id: Session identifier

        Returns:
            True if session is active, False otherwise
        """
        return session_id in self._active_sessions

    async def update_resource_usage(
        self,
        session_id: str,
        cpu_delta: float = 0,
        memory_delta: int = 0,
    ) -> None:
        """Update resource usage for a session.

        Args:
            session_id: Session identifier
            cpu_delta: CPU usage change (cores)
            memory_delta: Memory usage change (bytes)
        """
        if session_id not in self._active_sessions:
            logger.warning("Cannot update resources for unknown session: %s", session_id)
            return

        self._active_sessions[session_id]["resource_usage"]["cpu"] += cpu_delta
        self._active_sessions[session_id]["resource_usage"]["memory"] += memory_delta

        logger.debug(
            "Updated resources: session_id=%s cpu=%.2f memory=%d",
            session_id,
            self._active_sessions[session_id]["resource_usage"]["cpu"],
            self._active_sessions[session_id]["resource_usage"]["memory"],
        )
