"""Document domain entity."""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class DocumentType(str, Enum):
    """Supported document types."""

    STRATEGIC_PLAN = "strategic_plan"
    BUSINESS_PLAN = "business_plan"
    MARKET_REPORT = "market_report"
    FINANCIAL_REPORT = "financial_report"
    COMPETITOR_ANALYSIS = "competitor_analysis"
    MEETING_NOTES = "meeting_notes"
    OTHER = "other"


class ParseStatus(str, Enum):
    """Document parsing status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DocumentVersion:
    """Represents a version of a document."""

    version: int
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    created_by: str = ""
    change_description: str = ""


@dataclass
class Document:
    """Document entity with metadata and version history.

    Invariant constraints:
    - document_id must be a valid UUID
    - filename must not be empty
    - version must be >= 1
    - supported_formats: pdf, docx, xlsx, pptx, txt, md, csv, html, etc.
    """

    document_id: uuid.UUID
    filename: str
    document_type: DocumentType = DocumentType.OTHER
    file_size_bytes: int = 0
    mime_type: str = ""
    parse_status: ParseStatus = ParseStatus.PENDING
    version: int = 1
    version_history: list[DocumentVersion] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    embedding: list[float] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def validate(self) -> bool:
        """Validate invariant constraints.

        Returns:
            True if all invariants are satisfied.

        Raises:
            ValueError: If any invariant is violated.
        """
        if not isinstance(self.document_id, uuid.UUID):
            raise ValueError("document_id must be a valid UUID")
        if not self.filename or not self.filename.strip():
            raise ValueError("filename must not be empty")
        if self.version < 1:
            raise ValueError("version must be >= 1")
        if self.file_size_bytes < 0:
            raise ValueError("file_size_bytes must be non-negative")
        # P1-03 Fix: Validate embedding for NaN/Inf values
        if self.embedding is not None:
            for i, val in enumerate(self.embedding):
                if not isinstance(val, int | float):
                    raise ValueError(f"embedding[{i}] must be a number")
                if math.isnan(val) or math.isinf(val):
                    raise ValueError(f"embedding[{i}] contains NaN/Inf")
        return True

    def validate_metadata(self, required_fields: list[str] | None = None) -> bool:
        """Validate that required metadata fields are present.

        Args:
            required_fields: List of required metadata keys.

        Returns:
            True if all required fields are present.

        Raises:
            ValueError: If any required field is missing.
        """
        if required_fields is None:
            required_fields = []
        missing = [f for f in required_fields if f not in self.metadata]
        if missing:
            raise ValueError(f"Missing required metadata fields: {missing}")
        return True

    def bump_version(self, change_description: str, created_by: str = "") -> int:
        """Increment document version and record history.

        Args:
            change_description: Description of changes in this version.
            created_by: User who made the change.

        Returns:
            New version number.
        """
        # Record current version in history
        current_version = DocumentVersion(
            version=self.version,
            change_description=change_description,
            created_by=created_by,
        )
        self.version_history.append(current_version)
        self.version += 1
        self.updated_at = datetime.now(UTC)
        return self.version
