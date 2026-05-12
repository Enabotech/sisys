"""HashRouterProtocol — domain port for hash-based session routing.

This protocol defines the interface for hash-based routing adapters.
Infrastructure layer implements this protocol for consistent session routing.
"""

from __future__ import annotations

from typing import Protocol


class HashRouterProtocol(Protocol):
    """Protocol for hash-based routing (implemented in infrastructure).

    Defines the interface for routing sessions based on session_id hash
    to ensure consistent session-to-node mapping.
    """

    def route(self, session_id: str) -> str:
        """Route based on session_id hash.

        Args:
            session_id: Session identifier

        Returns:
            Target node/agent ID
        """
        ...
