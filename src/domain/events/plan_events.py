"""Core domain events for strategic planning.

P2-03 Design Note: DomainEvent uses frozen=True for immutability, but
subclasses use object.__setattr__() in __post_init__ to set aggregate_id.
This is the standard Python pattern for modifying frozen dataclasses during
initialization — the immutability guarantee applies after construction,
not during it. Event objects cannot be mutated after they are created.
"""

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


@dataclass(frozen=True)
class ToolExecuted(DomainEvent):
    """Event emitted when a tool has been executed."""

    tool_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="ToolExecuted", init=False)
    execution_result: dict[str, Any] = field(default_factory=dict)
    cost_audit: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Set aggregate_id and aggregate_type if not already set."""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.tool_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Tool")


@dataclass(frozen=True)
class AgentDecided(DomainEvent):
    """Event emitted when an Agent has made a decision."""

    agent_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="AgentDecided", init=False)
    decision_result: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0

    def __post_init__(self) -> None:
        """Set aggregate_id and aggregate_type if not already set."""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.agent_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Agent")


@dataclass(frozen=True)
class CheckpointReached(DomainEvent):
    """Event emitted when a planning checkpoint has been reached."""

    checkpoint_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="CheckpointReached", init=False)
    phase_identifier: str = ""
    user_feedback_request: bool = False

    def __post_init__(self) -> None:
        """Set aggregate_id and aggregate_type if not already set."""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.checkpoint_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Checkpoint")


@dataclass(frozen=True)
class CorrectionApproved(DomainEvent):
    """Event emitted when a correction has been approved."""

    correction_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="CorrectionApproved", init=False)
    correction_type: str = ""
    previous_value: Any = None
    new_value: Any = None
    approval_chain: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Set aggregate_id and aggregate_type if not already set."""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.correction_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Correction")
