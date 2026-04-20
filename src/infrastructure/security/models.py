"""Security models — Role, Permission, and Data Sovereignty value objects.

These are domain value objects that represent security concepts
in the infrastructure layer, not SQLAlchemy models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    pass


class SensitiveDataType(str, Enum):
    """Sensitive data type classification (PIPL and data sovereignty)."""

    PII = "pii"  # Personally Identifiable Information
    TRADE_SECRET = "trade_secret"  # Business trade secrets  # pragma: allowlist secret
    FINANCIAL = "financial"  # Financial data
    BIOMETRIC = "biometric"  # Biometric data (PIPL sensitive)
    MINOR = "minor"  # Data about minors (PIPL enhanced protection)
    HEALTH = "health"  # Health/medical data
    IDENTITY_DOCUMENT = "identity_document"  # ID cards, passports
    CUSTOM = "custom"  # User-defined sensitive type


class DataResidency(str, Enum):
    """Data residency requirement levels."""

    CHINA_DOMESTIC = "china_domestic"  # Must be stored in mainland China
    CHINA_BORDER = "china_border"  # Stored in Hong Kong/Macau/Taiwan
    GLOBAL = "global"  # Can be stored anywhere


class WhitelistStatus(str, Enum):
    """Whitelist rule status."""

    ACTIVE = "active"
    PENDING = "pending"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ApprovalStatus(str, Enum):
    """Cross-border approval request status."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class Permission:
    """Permission value object.

    Represents a permission in the format "resource:action".
    Examples: "document:read", "document:write", "tool:execute", "*:*"

    Attributes:
        id: Unique permission identifier.
        resource: Resource name (e.g., "document", "tool", "agent").
        action: Action name (e.g., "read", "write", "delete", "execute").
        description: Human-readable description.
    """

    id: UUID
    resource: str
    action: str
    description: str | None = None

    @property
    def permission_string(self) -> str:
        """Return permission string in resource:action format."""
        return f"{self.resource}:{self.action}"

    @classmethod
    def from_string(cls, permission_str: str, permission_id: UUID | None = None) -> Permission:
        """Create Permission from string format (e.g., "document:read").

        Args:
            permission_str: Permission string in resource:action format.
            permission_id: Optional UUID for the permission.

        Returns:
            Permission: New Permission instance.

        Raises:
            ValueError: If permission string format is invalid.
        """
        parts = permission_str.split(":", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid permission format: {permission_str}. Expected 'resource:action'")
        resource, action = parts
        return cls(id=permission_id or uuid4(), resource=resource, action=action)


@dataclass
class Role:
    """Role value object.

    Represents a role with associated permissions.
    A role is a collection of permissions that can be assigned to users.

    Attributes:
        id: Unique role identifier.
        name: Role name (e.g., "admin", "analyst", "viewer").
        description: Human-readable description.
        permissions: List of permissions granted by this role.
        is_active: Whether the role is active (soft delete support).
        created_at: Role creation timestamp.
        updated_at: Role last update timestamp.
    """

    id: UUID
    name: str
    description: str | None = None
    permissions: list[str] = field(default_factory=list)
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def has_permission(self, resource: str, action: str) -> bool:
        """Check if this role has a specific permission.

        Supports wildcard matching:
        - "*:*" matches all permissions
        - "document:*" matches all document permissions
        - "*:read" matches all read permissions

        Args:
            resource: Resource name.
            action: Action name.

        Returns:
            bool: True if role has the permission.
        """
        # Check for wildcard permission
        if "*:*" in self.permissions:
            return True

        # Check for resource wildcard
        if f"{resource}:*" in self.permissions:
            return True

        # Check for action wildcard
        if f"*:{action}" in self.permissions:
            return True

        # Check for exact match
        if f"{resource}:{action}" in self.permissions:
            return True

        return False

    def add_permission(self, permission: str) -> None:
        """Add a permission to this role.

        Args:
            permission: Permission string in resource:action format.
        """
        if permission not in self.permissions:
            self.permissions.append(permission)

    def remove_permission(self, permission: str) -> None:
        """Remove a permission from this role.

        Args:
            permission: Permission string in resource:action format.
        """
        if permission in self.permissions:
            self.permissions.remove(permission)


@dataclass
class User:
    """User value object for authentication.

    Represents a user with their authentication information and roles.

    Attributes:
        id: Unique user identifier.
        username: User's username (unique).
        email: User's email (unique).
        hashed_password: Bcrypt hashed password.
        is_active: Whether the user account is active.
        roles: List of role names assigned to this user.
        failed_login_attempts: Number of consecutive failed login attempts.
        locked_until: Timestamp when account lock expires (None if not locked).
        created_at: User creation timestamp.
        updated_at: User last update timestamp.
    """

    id: UUID
    username: str
    email: str
    hashed_password: str | None = None
    is_active: bool = True
    roles: list[str] = field(default_factory=list)
    failed_login_attempts: int = 0
    locked_until: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def is_locked(self) -> bool:
        """Check if the account is currently locked.

        Returns:
            bool: True if account is locked.
        """
        if self.locked_until is None:
            return False
        now = datetime.now(UTC)
        locked = self.locked_until
        if locked.tzinfo is None:
            locked = locked.replace(tzinfo=UTC)
        return now < locked

    def increment_failed_login(self) -> None:
        """Increment failed login attempt counter."""
        self.failed_login_attempts += 1

    def reset_failed_login(self) -> None:
        """Reset failed login attempt counter."""
        self.failed_login_attempts = 0

    def lock_account(self, duration_minutes: int) -> None:
        """Lock the account for a specified duration.

        Args:
            duration_minutes: Lockout duration in minutes.
        """
        from datetime import timedelta

        self.locked_until = datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=duration_minutes)


@dataclass
class SensitiveLabel:
    """Sensitive data label attached to data objects.

    Attributes:
        id: Unique label identifier.
        data_id: UUID of the data object this label is attached to.
        sensitive_type: Type of sensitive data.
        confidence: Detection confidence (0.0-1.0).
        labels: Additional labels/tags.
        detection_method: Method used for detection (regex, keyword, nlp).
        detected_at: Timestamp when detection occurred.
    """

    id: UUID = field(default_factory=uuid4)
    data_id: UUID = field(default_factory=uuid4)
    sensitive_type: SensitiveDataType = SensitiveDataType.PII
    confidence: float = 1.0
    labels: list[str] = field(default_factory=list)
    detection_method: str = "regex"
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class DataSovereigntyPolicy:
    """Data sovereignty policy for specific data types.

    Attributes:
        id: Unique policy identifier.
        data_type: Type of sensitive data this policy applies to.
        residency_requirement: Required data residency level.
        storage_allowed: List of regions/countries where storage is allowed.
        cross_border_allowed: Whether cross-border transfer is allowed.
        created_at: Policy creation timestamp.
        updated_at: Policy last update timestamp.
    """

    id: UUID = field(default_factory=uuid4)
    data_type: SensitiveDataType = SensitiveDataType.PII
    residency_requirement: DataResidency = DataResidency.CHINA_DOMESTIC
    storage_allowed: list[str] = field(default_factory=lambda: ["CN"])
    cross_border_allowed: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def allows_storage(self, region: str) -> bool:
        """Check if storage in given region is allowed.

        Args:
            region: ISO 3166-1 alpha-2 country code.

        Returns:
            bool: True if storage is allowed.
        """
        if self.cross_border_allowed:
            return True
        return region in self.storage_allowed


@dataclass
class WhitelistRule:
    """External API call whitelist rule.

    Attributes:
        id: Unique rule identifier.
        endpoint: External API endpoint URL pattern.
        provider: Service provider name.
        purpose: Purpose/description of the external call.
        risk_level: Risk level (low, medium, high, critical).
        status: Current rule status.
        approved_by: User ID who approved this rule.
        expiry_date: Rule expiration date (None = no expiration).
        created_at: Rule creation timestamp.
    """

    id: UUID = field(default_factory=uuid4)
    endpoint: str = ""
    provider: str = ""
    purpose: str = ""
    risk_level: str = "medium"
    status: WhitelistStatus = WhitelistStatus.ACTIVE
    approved_by: str = ""
    expiry_date: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_active(self) -> bool:
        """Check if rule is currently active and valid.

        Returns:
            bool: True if rule is active and not expired.
        """
        if self.status != WhitelistStatus.ACTIVE:
            return False
        if self.expiry_date is not None:
            now = datetime.now(UTC)
            expiry = self.expiry_date
            # Compare timestamps in UTC
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=UTC)
            if now > expiry:
                return False
        return True


@dataclass
class CrossBorderApproval:
    """Cross-border data transfer approval request.

    Attributes:
        id: Unique approval ID.
        request_id: UUID of the original transfer request.
        data_id: UUID of data to be transferred.
        destination: Destination country/region.
        purpose: Purpose of transfer.
        status: Current approval status.
        requester: User ID who requested the transfer.
        approver: User ID of compliance officer who approved/rejected.
        rejection_reason: Reason for rejection (if rejected).
        requested_at: Timestamp of request.
        approved_at: Timestamp of approval/rejection.
        sla_deadline: SLA deadline for approval (48h for MVP).
    """

    id: UUID = field(default_factory=uuid4)
    request_id: UUID = field(default_factory=uuid4)
    data_id: UUID = field(default_factory=uuid4)
    destination: str = ""
    purpose: str = ""
    status: ApprovalStatus = ApprovalStatus.PENDING
    requester: str = ""
    approver: str = ""
    rejection_reason: str = ""
    requested_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    approved_at: datetime | None = None
    sla_deadline: datetime = field(default_factory=lambda: datetime.now(UTC))

    def approve(self, approver: str) -> None:
        """Approve the transfer request.

        Args:
            approver: User ID of compliance officer.

        Raises:
            ValueError: If current status is not PENDING or approver is empty.
        """
        if not approver or not approver.strip():
            raise ValueError("Approver cannot be empty")
        if self.status != ApprovalStatus.PENDING:
            raise ValueError(f"Cannot approve from status {self.status.value}")
        self.status = ApprovalStatus.APPROVED
        self.approver = approver.strip()
        self.approved_at = datetime.now(UTC)

    def reject(self, approver: str, reason: str) -> None:
        """Reject the transfer request.

        Args:
            approver: User ID of compliance officer.
            reason: Rejection reason.

        Raises:
            ValueError: If current status is not PENDING or approver is empty.
        """
        if not approver or not approver.strip():
            raise ValueError("Approver cannot be empty")
        if self.status != ApprovalStatus.PENDING:
            raise ValueError(f"Cannot reject from status {self.status.value}")
        self.status = ApprovalStatus.REJECTED
        self.approver = approver.strip()
        self.rejection_reason = reason
        self.approved_at = datetime.now(UTC)

    def is_sla_expired(self) -> bool:
        """Check if SLA deadline has passed.

        Returns:
            bool: True if SLA deadline has passed.
        """
        now = datetime.now(UTC)
        deadline = self.sla_deadline
        # Compare timestamps in UTC
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=UTC)
        return now > deadline
