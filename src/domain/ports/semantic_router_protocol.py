"""SemanticRouterProtocol — domain port for semantic task routing.

This protocol defines the interface for semantic routing adapters.
Infrastructure layer implements this protocol for intelligent task routing.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SemanticRouterProtocol(Protocol):
    """Protocol for semantic routing (implemented in infrastructure).

    Defines the interface for routing tasks based on semantic similarity
    matching between task context and available targets.
    """

    async def route(self, task_context: dict[str, Any]) -> tuple[str, float]:
        """Route based on task context semantic similarity.

        Args:
            task_context: Task context dictionary

        Returns:
            Tuple of (target_id, similarity_score)
        """
        ...
