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


# =============================================================================
# 等保 2.0 Level 3 Compliance Models (Story 1.12)
# =============================================================================


class MFAChallengeType(str, Enum):
    """MFA challenge types supported in 等保 2.0."""

    TOTP = "totp"  # Time-based One-Time Password (RFC 6238)
    HOTP = "hotp"  # HMAC-based One-Time Password (RFC 4226)


class MFAChallengeStatus(str, Enum):
    """MFA challenge status."""

    PENDING = "pending"
    VERIFIED = "verified"
    EXPIRED = "expired"
    FAILED = "failed"


class BackupType(str, Enum):
    """Backup types supported."""

    FULL = "full"  # Full backup
    INCREMENTAL = "incremental"  # Incremental backup
    DIFFERENTIAL = "differential"  # Differential backup


class BackupStatus(str, Enum):
    """Backup operation status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IntegrityStatus(str, Enum):
    """Data integrity verification status."""

    VERIFIED = "verified"
    VIOLATED = "violated"
    UNKNOWN = "unknown"


class HashAlgorithm(str, Enum):
    """Hash algorithms for integrity verification."""

    SHA256 = "sha256"
    SHA512 = "sha512"
    MD5 = "md5"  # Deprecated but supported for legacy data


@dataclass
class MFAChallenge:
    """MFA challenge model for multi-factor authentication.

    Represents a TOTP/HOTP challenge issued to a user during
    MFA setup or verification.

    Attributes:
        id: Unique challenge identifier.
        user_id: UUID of the user this challenge is for.
        challenge_type: Type of MFA challenge (TOTP/HOTP).
        secret: Base32-encoded secret key for TOTP/HOTP.
        attempts: Number of verification attempts made.
        max_attempts: Maximum allowed verification attempts.
        expires_at: Challenge expiration timestamp.
        status: Current challenge status.
        created_at: Challenge creation timestamp.
    """

    id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)
    challenge_type: MFAChallengeType = MFAChallengeType.TOTP
    secret: str = ""  # Base32-encoded secret
    attempts: int = 0
    max_attempts: int = 3  # 等保 2.0 requires max 3 attempts
    expires_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: MFAChallengeStatus = MFAChallengeStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_expired(self) -> bool:
        """Check if the challenge has expired.

        Returns:
            bool: True if challenge is expired.
        """
        now = datetime.now(UTC)
        exp = self.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)
        return now > exp

    def is_max_attempts_reached(self) -> bool:
        """Check if max verification attempts have been reached.

        Returns:
            bool: True if max attempts reached.
        """
        return self.attempts >= self.max_attempts

    def increment_attempts(self) -> None:
        """Increment the attempt counter."""
        self.attempts += 1

    def mark_verified(self) -> None:
        """Mark the challenge as verified."""
        self.status = MFAChallengeStatus.VERIFIED

    def mark_failed(self) -> None:
        """Mark the challenge as failed."""
        self.status = MFAChallengeStatus.FAILED

    def mark_expired(self) -> None:
        """Mark the challenge as expired."""
        self.status = MFAChallengeStatus.EXPIRED


@dataclass
class BackupRecord:
    """Backup record for tracking backup operations.

    Attributes:
        id: Unique backup record identifier.
        backup_type: Type of backup (full/incremental/differential).
        start_time: Backup operation start timestamp.
        end_time: Backup operation end timestamp (None if in progress).
        status: Current backup status.
        size_bytes: Total size of backed up data in bytes.
        checksum: SHA-256 checksum of the backup.
        location: Storage location of the backup.
        user_id: UUID of user who initiated the backup.
        description: Optional description of the backup.
    """

    id: UUID = field(default_factory=uuid4)
    backup_type: BackupType = BackupType.FULL
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    end_time: datetime | None = None
    status: BackupStatus = BackupStatus.PENDING
    size_bytes: int = 0
    checksum: str = ""  # SHA-256 checksum
    location: str = ""  # MinIO/S3 location path
    user_id: UUID = field(default_factory=uuid4)
    description: str = ""

    def duration_seconds(self) -> float | None:
        """Calculate backup duration in seconds.

        Returns:
            float | None: Duration in seconds, or None if backup not completed.
        """
        if self.end_time is None:
            return None
        start = self.start_time
        end = self.end_time
        if start.tzinfo is not None:
            start = start.replace(tzinfo=None)
        if end.tzinfo is not None:
            end = end.replace(tzinfo=None)
        return (end - start).total_seconds()

    def is_completed(self) -> bool:
        """Check if backup completed successfully.

        Returns:
            bool: True if status is COMPLETED.
        """
        return self.status == BackupStatus.COMPLETED


@dataclass
class IntegrityCheck:
    """Data integrity check record.

    Records the result of a data integrity verification operation.

    Attributes:
        id: Unique check record identifier.
        data_type: Type of data checked (document, config, etc.).
        data_id: UUID of the data object checked.
        hash_value: Expected hash value.
        algorithm: Hash algorithm used (sha256, sha512, etc.).
        verified_at: Timestamp of verification.
        status: Verification status (verified/violated/unknown).
        source: Where the data is stored/accessed from.
    """

    id: UUID = field(default_factory=uuid4)
    data_type: str = ""
    data_id: UUID = field(default_factory=uuid4)
    hash_value: str = ""
    algorithm: HashAlgorithm = HashAlgorithm.SHA256
    verified_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: IntegrityStatus = IntegrityStatus.UNKNOWN
    source: str = ""  # MinIO path, PostgreSQL table, etc.

    def is_verified(self) -> bool:
        """Check if integrity was verified successfully.

        Returns:
            bool: True if status is VERIFIED.
        """
        return self.status == IntegrityStatus.VERIFIED

    def is_violated(self) -> bool:
        """Check if integrity violation was detected.

        Returns:
            bool: True if status is VIOLATED.
        """
        return self.status == IntegrityStatus.VIOLATED


@dataclass
class ThreatScore:
    """Threat score for security risk assessment.

    Attributes:
        id: Unique threat score identifier.
        source_ip: IP address being scored.
        threat_type: Type of threat detected.
        score: Threat score (0-100, higher = more severe).
        factors: List of contributing factors.
        assessed_at: Assessment timestamp.
    """

    id: UUID = field(default_factory=uuid4)
    source_ip: str = ""
    threat_type: str = ""
    score: float = 0.0  # 0-100
    factors: list[str] = field(default_factory=list)
    assessed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def severity_level(self) -> str:
        """Get severity level based on score.

        Returns:
            str: Severity level (low/medium/high/critical).
        """
        if self.score >= 80:
            return "critical"
        elif self.score >= 60:
            return "high"
        elif self.score >= 40:
            return "medium"
        else:
            return "low"
