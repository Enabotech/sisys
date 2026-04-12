"""Tool domain entity."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class ToolStatus(str, Enum):
    """Tool lifecycle status."""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    MAINTENANCE = "maintenance"


class ToolCategory(str, Enum):
    """Tool categories."""

    ANALYSIS = "analysis"
    GENERATION = "generation"
    VALIDATION = "validation"
    VISUALIZATION = "visualization"
    OTHER = "other"


@dataclass
class Tool:
    """Tool entity with unique identifier, I/O schema, and executor.

    Invariant constraints:
    - tool_id must be a valid UUID
    - name must not be empty
    - input_schema must be valid JSON schema dict
    - output_schema must be valid JSON schema dict
    """

    tool_id: uuid.UUID
    name: str
    description: str = ""
    category: ToolCategory = ToolCategory.OTHER
    input_schema: dict = field(default_factory=dict)
    output_schema: dict = field(default_factory=dict)
    status: ToolStatus = ToolStatus.ACTIVE
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def validate(self) -> bool:
        """Validate invariant constraints.

        Returns:
            True if all invariants are satisfied.

        Raises:
            ValueError: If any invariant is violated.
        """
        if not isinstance(self.tool_id, uuid.UUID):
            raise ValueError("tool_id must be a valid UUID")
        if not self.name or not self.name.strip():
            raise ValueError("name must not be empty")
        if not isinstance(self.input_schema, dict):
            raise ValueError("input_schema must be a dict")
        if not isinstance(self.output_schema, dict):
            raise ValueError("output_schema must be a dict")
        return True
