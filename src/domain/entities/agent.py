"""Agent domain entity."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class AgentRole(str, Enum):
    """Agent roles in the system."""

    CEO = "ceo"
    CFO = "cfo"
    CMO = "cmo"
    CTO = "cto"
    COO = "coo"
    CHO = "cho"
    AUD = "aud"
    SYS = "sys"


class AgentStatus(str, Enum):
    """Agent execution status."""

    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Agent:
    """Agent entity with identity profile and responsibility boundaries.

    Invariant constraints:
    - agent_id must be a valid UUID
    - role must be a valid AgentRole
    - name must not be empty
    """

    agent_id: uuid.UUID
    role: AgentRole
    name: str
    description: str = ""
    status: AgentStatus = AgentStatus.IDLE
    domain_knowledge: list[str] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def validate(self) -> bool:
        """Validate invariant constraints.

        Returns:
            True if all invariants are satisfied.

        Raises:
            ValueError: If any invariant is violated.
        """
        if not isinstance(self.agent_id, uuid.UUID):
            raise ValueError("agent_id must be a valid UUID")
        if not isinstance(self.role, AgentRole):
            raise ValueError("role must be a valid AgentRole")
        if not self.name or not self.name.strip():
            raise ValueError("name must not be empty")
        return True
