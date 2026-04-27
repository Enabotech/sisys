"""AutoTriggerContext value object — extracted context from domain/heartbeat events."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class AutoTriggerContext:
    """Context extracted from auto-trigger events for downstream auto-route/auto-execute stages.

    Used by AutoTriggerService to pass session_id, agent_id, and task context to Story 1.14b (auto-route).
    """

    session_id: str
    trigger_type: str  # "domain_event" | "heartbeat"
    agent_id: str | None = None
    task_context: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    source_event_type: str = ""
    source_event_id: str | None = None

    def __post_init__(self) -> None:
        """Validate required fields and apply defaults."""
        if not self.session_id:
            # Use default session when none provided
            object.__setattr__(self, "session_id", "default")

    @classmethod
    def from_domain_event(
        cls,
        event_type: str,
        payload: dict[str, Any],
        event_id: str | None = None,
    ) -> AutoTriggerContext:
        """Factory: extract AutoTriggerContext from a domain event payload.

        Args:
            event_type: The domain event type (e.g., "DocumentProcessed")
            payload: Event payload dict
            event_id: Optional event ID

        Returns:
            AutoTriggerContext with extracted fields
        """
        # Extract session_id from various possible locations
        session_id = (
            payload.get("session_id")
            or payload.get("payload", {}).get("session_id")
            or payload.get("aggregate_id")
            or "default"
        )
        # Extract agent_id
        agent_id = payload.get("agent_id") or payload.get("payload", {}).get("agent_id")
        # Extract task context
        task_context = {
            k: v
            for k, v in payload.items()
            if k
            in (
                "task_type",
                "priority",
                "tool_name",
                "checkpoint_id",
                "correction_type",
                "routing_decision",
                "isolation_level",
                "document_id",
                "strategy_id",
                "agent_id",
                "session_id",
                "error_message",
                "retry_count",
            )
            and k not in ("aggregate_id", "event_id", "event_type")
        }

        return cls(
            session_id=session_id,
            trigger_type="domain_event",
            agent_id=agent_id,
            task_context=task_context,
            source_event_type=event_type,
            source_event_id=event_id,
        )

    @classmethod
    def from_heartbeat(
        cls,
        heartbeat_id: str,
        wake_reason: str = "",
        todo_items: tuple[str, ...] | None = None,
        cost_budget: float = 0.0,
    ) -> AutoTriggerContext:
        """Factory: extract AutoTriggerContext from a heartbeat event.

        Args:
            heartbeat_id: Unique heartbeat identifier
            wake_reason: Reason for wake (scheduled/user_request/system_recovery)
            todo_items: Pending task list
            cost_budget: Cost budget cap

        Returns:
            AutoTriggerContext derived from heartbeat
        """
        return cls(
            session_id="heartbeat-scheduler",
            trigger_type="heartbeat",
            agent_id=None,
            task_context={
                "heartbeat_id": heartbeat_id,
                "wake_reason": wake_reason,
                "todo_items": list(todo_items) if todo_items else [],
                "cost_budget": cost_budget,
            },
            source_event_type="HeartbeatTriggered",
            source_event_id=heartbeat_id,
        )
