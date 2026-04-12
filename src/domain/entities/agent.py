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
    failure_reason: str = ""
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

    # P1-05 Fix: Add state transition methods
    def start(self) -> None:
        """Transition agent from IDLE to RUNNING.

        Raises:
            ValueError: If agent is not in IDLE state.
        """
        if self.status != AgentStatus.IDLE:
            raise ValueError(f"Can only start from IDLE, current: {self.status.value}")
        self.status = AgentStatus.RUNNING
        self.updated_at = datetime.now(UTC)

    def complete(self) -> None:
        """Transition agent from RUNNING to COMPLETED.

        Raises:
            ValueError: If agent is not in RUNNING state.
        """
        if self.status != AgentStatus.RUNNING:
            raise ValueError(f"Can only complete from RUNNING, current: {self.status.value}")
        self.status = AgentStatus.COMPLETED
        self.updated_at = datetime.now(UTC)

    def fail(self, reason: str = "") -> None:
        """Transition agent to FAILED state.

        Args:
            reason: Optional failure reason for diagnostics.

        Raises:
            ValueError: If agent is already in FAILED state.
        """
        # P1-03 Fix: Reject re-failing an already failed agent
        if self.status == AgentStatus.FAILED:
            raise ValueError(
                f"Agent is already failed (reason: {self.failure_reason!r})"
            )
        self.failure_reason = reason
        self.status = AgentStatus.FAILED
        self.updated_at = datetime.now(UTC)

    def restart(self) -> None:
        """Restart a failed or completed agent back to IDLE.

        Raises:
            ValueError: If agent is not in FAILED or COMPLETED state.
        """
        if self.status not in (AgentStatus.FAILED, AgentStatus.COMPLETED):
            raise ValueError(
                f"Can only restart from FAILED or COMPLETED, current: {self.status.value}"
            )
        self.failure_reason = ""
        self.status = AgentStatus.IDLE
        self.updated_at = datetime.now(UTC)

    def wait(self) -> None:
        """Transition agent to WAITING state."""
        if self.status not in (AgentStatus.RUNNING, AgentStatus.WAITING):
            raise ValueError(f"Can only wait from RUNNING or WAITING, current: {self.status.value}")
        self.status = AgentStatus.WAITING
        self.updated_at = datetime.now(UTC)
