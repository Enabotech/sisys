"""Base domain event class.

Domain events use only Python standard library types (dataclasses, uuid, datetime).
Pydantic is used only at the application/infrastructure layer boundaries for
serialization and validation.
"""

from __future__ import annotations

import json
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

        Raises:
            ValueError: If event_type is empty or payload is not JSON serializable.
        """
        # P1-05 Fix: Validate event_type is non-empty
        if not self.event_type:
            raise ValueError("event_type must not be empty")
        result: dict[str, Any] = {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "occurred_on": self.occurred_on.isoformat(),
            "payload": self.payload,
        }
        # P0-01: Conditionally serialize aggregate_id
        if self.aggregate_id is not None:
            result["aggregate_id"] = str(self.aggregate_id)
        # P1-04: Validate payload is JSON serializable
        try:
            json.dumps(self.payload)
        except (TypeError, ValueError) as e:
            raise ValueError(f"payload is not JSON serializable: {e}") from e
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainEvent:
        """Deserialize event from dictionary.

        Args:
            data: Dictionary with event data.

        Returns:
            Reconstructed DomainEvent instance.

        Raises:
            ValueError: If required fields are missing or malformed.
        """
        # P1-04 Fix: Validate required fields with descriptive errors
        if "event_id" not in data:
            raise ValueError("Missing required field: event_id")
        if "event_type" not in data:
            raise ValueError("Missing required field: event_type")
        if "occurred_on" not in data:
            raise ValueError("Missing required field: occurred_on")

        # P0-01 Fix: UUID parsing with context
        try:
            eid = uuid.UUID(data["event_id"])
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Invalid event_id: {data.get('event_id', 'missing')}") from e

        # P0-01: Safely parse aggregate_id (may be None)
        agg_id: uuid.UUID | None = None
        if data.get("aggregate_id") is not None:
            try:
                agg_id = uuid.UUID(data["aggregate_id"])
            except (ValueError, AttributeError) as e:
                raise ValueError(f"Invalid aggregate_id: {data.get('aggregate_id', 'missing')}") from e

        # P0-02 Fix: datetime parsing with context
        try:
            occurred = datetime.fromisoformat(data["occurred_on"])
        except (ValueError, AttributeError, TypeError) as e:
            raise ValueError(
                f"Invalid occurred_on: {data.get('occurred_on', 'missing')}"
            ) from e

        return cls(
            event_id=eid,
            event_type=data["event_type"],
            aggregate_id=agg_id,
            payload=data.get("payload", {}),
            occurred_on=occurred,
        )
