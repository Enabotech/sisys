"""Compliance domain events — data sovereignty and PIPL.

Events in this module follow the DomainEvent standard:
- Use only Python standard library types (dataclasses, uuid, datetime)
- Pydantic is NOT used in domain events
- Subclass-specific fields are included in payload via to_dict()
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from .base import DomainEvent


class SensitiveType(str, Enum):
    """Sensitive data type classification."""

    PII = "pii"  # Personally Identifiable Information
    TRADE_SECRET = "trade_secret"  # Business trade secrets  # pragma: allowlist secret
    FINANCIAL = "financial"  # Financial data
    BIOMETRIC = "biometric"  # Biometric data (PIPL sensitive)
    MINOR = "minor"  # Data about minors (PIPL enhanced protection)
    CUSTOM = "custom"  # User-defined sensitive type


@dataclass(frozen=True)
class SensitiveDataDetected(DomainEvent):
    """Event emitted when sensitive data is detected in a data object.

    This event is triggered during data ingestion or access to mark
    sensitive data for appropriate handling (local processing, encryption, etc.).
    """

    data_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="SensitiveDataDetected", init=False)
    sensitive_type: SensitiveType = SensitiveType.PII
    confidence: float = 1.0  # Detection confidence 0.0-1.0
    labels: list[str] = field(default_factory=list)  # Additional labels
    detection_method: str = "regex"  # regex, keyword, nlp
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Set aggregate_id and aggregate_type if not already set."""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.data_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "DataSovereignty")


@dataclass(frozen=True)
class CrossBorderTransferRequested(DomainEvent):
    """Event emitted when a cross-border data transfer is requested.

    This event triggers the approval workflow for data that needs
    to be transferred outside the domestic region.
    """

    request_id: uuid.UUID = field(default_factory=uuid.uuid4)
    data_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="CrossBorderTransferRequested", init=False)
    destination: str = ""  # Destination country/region
    purpose: str = ""  # Purpose of transfer
    approval_id: uuid.UUID | None = None  # Set after approval workflow starts
    status: str = "pending"  # pending, approved, rejected, blocked
    requester: str = ""  # User ID who requested the transfer
    requested_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Set aggregate_id and aggregate_type if not already set."""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.request_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "CrossBorderTransfer")


@dataclass(frozen=True)
class DataSovereigntyViolation(DomainEvent):
    """Event emitted when a data sovereignty policy is violated."""

    violation_id: uuid.UUID = field(default_factory=uuid.uuid4)
    data_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="DataSovereigntyViolation", init=False)
    violation_type: str = ""  # unauthorized_transfer,境外_storage, etc.
    severity: str = "high"  # low, medium, high, critical
    description: str = ""
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Set aggregate_id and aggregate_type if not already set."""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.violation_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "DataSovereignty")


@dataclass(frozen=True)
class PIPLDataAccessRequested(DomainEvent):
    """Event emitted when personal information is accessed under PIPL.

    PIPL requires tracking all access to personal information
    including purpose, legal basis, and data subject consent.
    """

    access_id: uuid.UUID = field(default_factory=uuid.uuid4)
    personal_data_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="PIPLDataAccessRequested", init=False)
    purpose: str = ""  # Purpose of data processing
    legal_basis: str = ""  # Legal basis: consent, contract, legal_obligation, etc.
    data_subject_consent: bool = False
    accessor: str = ""  # User/System accessing the data
    accessed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Set aggregate_id and aggregate_type if not already set."""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.access_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "PIPLCompliance")
