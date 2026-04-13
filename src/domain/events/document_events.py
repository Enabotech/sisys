"""Document domain event."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from .base import DomainEvent


@dataclass(frozen=True)
class DocumentProcessed(DomainEvent):
    """Event emitted when a document has been successfully parsed and indexed."""

    document_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="DocumentProcessed", init=False)
    parse_result: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None

    def __post_init__(self) -> None:
        """Set aggregate_id and aggregate_type if not already set."""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.document_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Document")
