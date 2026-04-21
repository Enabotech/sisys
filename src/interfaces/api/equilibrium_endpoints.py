"""API Contract: 等保 2.0 Level 3 Compliance Endpoints.

Reference: Story 1.12 等保 2.0 三级基础要求

API Endpoints:
- POST /api/v1/auth/mfa/setup - MFA setup for user
- POST /api/v1/auth/mfa/verify - Verify MFA code
- GET /api/v1/compliance/status - Compliance status query
- GET/POST /api/v1/admin/backups - Backup management
- POST /api/v1/admin/backups/{backup_id}/restore - Restore from backup
- POST /api/v1/integrity/check - Data integrity check

Authentication:
- All endpoints require JWT Bearer token with appropriate roles.
- MFA endpoints require user authentication.
- Admin endpoints require admin role.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from ...infrastructure.security.models import (
    BackupStatus,
    BackupType,
    IntegrityStatus,
)

# =========================================================================
# MFA Endpoints
# =========================================================================


class MFASetupRequest(BaseModel):
    """Request body for MFA setup."""

    user_id: UUID = Field(..., description="UUID of the user")
    username: str = Field(default="", description="Username for authenticator app display")


class MFASetupResponse(BaseModel):
    """Response body for MFA setup."""

    success: bool = Field(..., description="Whether setup was successful")
    secret: str = Field(..., description="TOTP secret (only returned on setup)")
    provisioning_uri: str = Field(..., description="QR code URI for authenticator app")
    challenge_id: UUID | None = Field(None, description="MFA challenge ID")


class MFAVerifyRequest(BaseModel):
    """Request body for MFA verification."""

    user_id: UUID = Field(..., description="UUID of the user")
    code: str = Field(..., description="TOTP code from authenticator app (6 digits)")


class MFAVerifyResponse(BaseModel):
    """Response body for MFA verification."""

    success: bool = Field(..., description="Whether verification was successful")
    challenge_id: UUID = Field(..., description="Challenge ID that was verified")
    message: str = Field(default="", description="Status message")


class MFAStatusResponse(BaseModel):
    """Response body for MFA status."""

    user_id: UUID = Field(..., description="UUID of the user")
    mfa_enabled: bool = Field(..., description="Whether MFA is enabled")
    challenge_type: str | None = Field(None, description="MFA challenge type")


# =========================================================================
# Compliance Status Endpoints
# =========================================================================


class ComplianceStatusResponse(BaseModel):
    """Response body for compliance status."""

    level: int = Field(..., description="等保 2.0 level (default: 3)")
    status: str = Field(..., description="Overall compliance status")
    mfa_coverage: float = Field(..., description="MFA coverage percentage (0-100)")
    rbac_coverage: float = Field(..., description="RBAC coverage percentage (0-100)")
    audit_log_integrity: float = Field(..., description="Audit log integrity percentage (0-100)")
    intrusion_detection_rate: float = Field(..., description="Intrusion detection rate (0-100)")
    data_encryption_rate: float = Field(..., description="Data encryption coverage (0-100)")
    backup_recovery_time: float = Field(..., description="Average backup recovery time in minutes")
    high_risk_count: int = Field(default=0, description="Number of high-risk vulnerabilities")
    medium_risk_count: int = Field(default=0, description="Number of medium-risk vulnerabilities")
    last_audit: datetime | None = Field(None, description="Last compliance audit timestamp")
    next_audit: datetime | None = Field(None, description="Next scheduled audit timestamp")


# =========================================================================
# Backup Management Endpoints
# =========================================================================


class BackupCreateRequest(BaseModel):
    """Request body for creating a backup."""

    backup_type: BackupType = Field(..., description="Type of backup: full or incremental")
    base_backup_id: UUID | None = Field(None, description="Base backup ID for incremental backup")
    description: str = Field(default="", description="Optional backup description")


class BackupResponse(BaseModel):
    """Response body for backup operations."""

    id: UUID = Field(..., description="Backup ID")
    backup_type: BackupType = Field(..., description="Type of backup")
    status: BackupStatus = Field(..., description="Backup status")
    size_bytes: int = Field(..., description="Size of backup in bytes")
    checksum: str = Field(..., description="SHA-256 checksum of backup")
    location: str = Field(..., description="Storage location path")
    start_time: datetime = Field(..., description="Backup start time")
    end_time: datetime | None = Field(None, description="Backup end time")
    description: str = Field(default="", description="Backup description")


class BackupRestoreRequest(BaseModel):
    """Request body for restoring from backup."""

    backup_id: UUID = Field(..., description="UUID of backup to restore from")
    target_path: str = Field(default="/var/sisys/restored", description="Target path for restored data")


class BackupRestoreResponse(BaseModel):
    """Response body for backup restore operation."""

    backup_id: UUID = Field(..., description="Source backup ID")
    backup_type: BackupType = Field(..., description="Type of backup restored")
    target_path: str = Field(..., description="Path where data was restored")
    size_bytes: int = Field(..., description="Size of restored data in bytes")
    duration_seconds: float = Field(..., description="Restore operation duration in seconds")
    status: str = Field(..., description="Restore status: success or failed")


class BackupListResponse(BaseModel):
    """Response body for listing backups."""

    backups: list[BackupResponse] = Field(..., description="List of backup records")
    total: int = Field(..., description="Total number of backups matching filter")
    limit: int = Field(..., description="Maximum number of backups returned")


# =========================================================================
# Integrity Check Endpoints
# =========================================================================


class IntegrityCheckRequest(BaseModel):
    """Request body for integrity check."""

    data_type: str = Field(default="document", description="Type of data to check")
    data_id: UUID | None = Field(None, description="UUID of specific data to check")
    expected_hash: str = Field(..., description="Expected hash value (SHA-256 or SHA-512)")
    algorithm: str = Field(default="SHA256", description="Hash algorithm: SHA256 or SHA512")


class IntegrityCheckResponse(BaseModel):
    """Response body for integrity check."""

    data_id: UUID = Field(..., description="ID of the data checked")
    data_type: str = Field(..., description="Type of data checked")
    status: IntegrityStatus = Field(..., description="Integrity status: verified or violated")
    algorithm: str = Field(..., description="Hash algorithm used")
    hash_value: str = Field(..., description="Hash value that was verified")
    verified_at: datetime = Field(..., description="Timestamp of verification")
    source: str = Field(default="", description="Storage location of data")


class IntrusionAlertResponse(BaseModel):
    """Response body for intrusion detection alerts."""

    intrusion_id: UUID = Field(..., description="Intrusion event ID")
    source_ip: str = Field(..., description="Source IP address of attacker")
    attack_type: str = Field(..., description="Type of attack detected")
    severity: str = Field(..., description="Severity level: low, medium, high, critical")
    action_taken: str = Field(..., description="Action taken: logged, blocked, etc.")
    description: str = Field(..., description="Detailed description of the intrusion")
    timestamp: datetime = Field(..., description="When the intrusion was detected")
