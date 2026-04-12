"""Base domain event class.

Domain events use only Python standard library types (dataclasses, uuid, datetime).
Pydantic is used only at the application/infrastructure layer boundaries for
serialization and validation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events.

    Attributes:
        event_id: Unique identifier for this event instance.
        occurred_on: Timestamp when the event occurred.
        aggregate_id: ID of the aggregate that produced this event.
        event_type: Type discriminator string for the event.
        payload: Event-specific data dictionary.
    """

    aggregate_id: uuid.UUID | None = None
    event_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    occurred_on: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to dictionary.

        Returns:
            Dictionary representation of the event.
        """
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "aggregate_id": str(self.aggregate_id),
            "occurred_on": self.occurred_on.isoformat(),
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainEvent:
        """Deserialize event from dictionary.

        Args:
            data: Dictionary with event data.

        Returns:
            Reconstructed DomainEvent instance.
        """
        return cls(
            event_id=uuid.UUID(data["event_id"]),
            event_type=data["event_type"],
            aggregate_id=uuid.UUID(data["aggregate_id"]),
            payload=data.get("payload", {}),
            occurred_on=datetime.fromisoformat(data["occurred_on"]),
        )
