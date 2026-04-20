"""API Contract: Data Sovereignty Endpoints.

Reference: Story 1.11 Data Sovereignty Isolation.

API Endpoints:
- GET/POST /api/v1/admin/whitelist - Whitelist rule management
- GET/POST /api/v1/admin/cross-border-approvals - Cross-border approval workflow
- GET /api/v1/compliance/status - Compliance status query

Authentication:
- All endpoints require JWT Bearer token with admin role.
- Some endpoints may require compliance officer role.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from ...infrastructure.security.models import (
    ApprovalStatus,
    DataResidency,
    SensitiveDataType,
    WhitelistStatus,
)

# =========================================================================
# Whitelist Management Endpoints
# =========================================================================


class WhitelistRuleCreate(BaseModel):
    """Request body for creating a whitelist rule."""

    endpoint: str = Field(..., description="External API endpoint URL pattern")
    provider: str = Field(..., description="Service provider name")
    purpose: str = Field(default="", description="Purpose/description of the external call")
    risk_level: str = Field(default="medium", description="Risk level: low, medium, high, critical")
    expiry_date: datetime | None = Field(None, description="Rule expiration date (ISO 8601)")


class WhitelistRuleResponse(BaseModel):
    """Response body for a whitelist rule."""

    id: UUID
    endpoint: str
    provider: str
    purpose: str
    risk_level: str
    status: WhitelistStatus
    approved_by: str
    expiry_date: datetime | None
    created_at: datetime


class WhitelistRuleListResponse(BaseModel):
    """Response body for listing whitelist rules."""

    rules: list[WhitelistRuleResponse]
    total: int
    offset: int
    limit: int


class WhitelistValidateRequest(BaseModel):
    """Request body for validating an endpoint against whitelist."""

    endpoint: str = Field(..., description="External API endpoint URL to validate")


class WhitelistValidateResponse(BaseModel):
    """Response body for whitelist validation."""

    is_allowed: bool
    matched_rule_id: UUID | None = None
    reason: str | None = None


# =========================================================================
# Cross-Border Approval Endpoints
# =========================================================================


class CrossBorderApprovalCreate(BaseModel):
    """Request body for creating a cross-border approval request."""

    data_id: UUID = Field(..., description="UUID of data to be transferred")
    destination: str = Field(..., description="Destination country/region (ISO 3166-1 alpha-2)")
    purpose: str = Field(..., description="Purpose of transfer")
    requester: str = Field(..., description="User ID who requested the transfer")


class CrossBorderApprovalResponse(BaseModel):
    """Response body for a cross-border approval request."""

    id: UUID
    request_id: UUID
    data_id: UUID
    destination: str
    purpose: str
    status: ApprovalStatus
    requester: str
    approver: str
    rejection_reason: str
    requested_at: datetime
    approved_at: datetime | None
    sla_deadline: datetime


class CrossBorderApprovalListResponse(BaseModel):
    """Response body for listing cross-border approval requests."""

    approvals: list[CrossBorderApprovalResponse]
    total: int
    offset: int
    limit: int


class CrossBorderApprovalAction(BaseModel):
    """Request body for approving or rejecting an approval request."""

    approver: str = Field(..., description="User ID of compliance officer")
    reason: str | None = Field(None, description="Reason (required for rejection)")


# =========================================================================
# Compliance Status Endpoints
# =========================================================================


class ComplianceStatusResponse(BaseModel):
    """Response body for compliance status."""

    sovereignty_enabled: bool
    data_residency_compliance: bool
    whitelist_validation_rate: float = Field(..., description="Percentage 0.0-1.0")
    cross_border_approval_rate: float = Field(..., description="Percentage 0.0-1.0")
    sensitive_data_detection_rate: float = Field(..., description="Percentage 0.0-1.0")
    pipl_compliance: bool
    last_audit_at: datetime | None


class DataSovereigntyStatus(BaseModel):
    """Response body for data sovereignty status of a specific data item."""

    data_id: UUID
    is_sensitive: bool
    sensitive_type: SensitiveDataType | None = None
    residency_requirement: DataResidency | None = None
    is_domestic_storage: bool | None = None
    cross_border_status: str | None = None  # allowed, pending_approval, blocked


class PIPLComplianceReport(BaseModel):
    """Response body for PIPL compliance report."""

    report_id: UUID
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    total_pipl_processing_records: int
    consent_records: int
    legal_basis_breakdown: dict[str, int]
    data_subject_rights_exercised: dict[str, int]
    biometric_processing_count: int
    minor_data_processing_count: int


# =========================================================================
# Error Responses
# =========================================================================


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    message: str
    details: dict | None = None


class ValidationErrorResponse(BaseModel):
    """Validation error response."""

    error: str = "validation_error"
    message: str
    field_errors: list[dict[str, str]]
