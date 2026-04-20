"""Data Sovereignty API Endpoints.

FastAPI routes for:
- POST /api/v1/admin/approvals - Create approval request
- GET /api/v1/admin/approvals - List approval requests
- GET /api/v1/admin/approvals/{id} - Get approval request
- POST /api/v1/admin/approvals/{id}/approve - Approve request (requires compliance_officer)
- POST /api/v1/admin/approvals/{id}/reject - Reject request (requires compliance_officer)

Reference: Story 1.11 Data Sovereignty Isolation - ADR-011
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.infrastructure.security.approval_workflow import (
    ApprovalNotFoundError,
    ApprovalWorkflowService,
)
from src.infrastructure.security.models import ApprovalStatus
from src.infrastructure.security.permission_middleware import get_current_user as auth_get_current_user

router = APIRouter(prefix="/api/v1/admin/approvals", tags=["data-sovereignty"])


# =========================================================================
# Request/Response Models
# =========================================================================


class ApprovalCreateRequest(BaseModel):
    """Request body for creating an approval request."""

    data_id: UUID = Field(..., description="UUID of data to be transferred")
    destination: str = Field(..., description="Destination country/region (ISO 3166-1 alpha-2)")
    purpose: str = Field(..., description="Purpose of transfer")


class ApprovalCreateResponse(BaseModel):
    """Response body for created approval request."""

    id: UUID
    request_id: UUID
    data_id: UUID
    destination: str
    purpose: str
    status: ApprovalStatus
    requester: str
    sla_deadline: datetime


class ApprovalResponse(BaseModel):
    """Response body for an approval request."""

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


class ApprovalListResponse(BaseModel):
    """Response body for listing approval requests."""

    approvals: list[ApprovalResponse]
    total: int


class ApprovalActionResponse(BaseModel):
    """Response body for approve/reject action."""

    id: UUID
    status: ApprovalStatus
    approver: str
    approved_at: datetime | None
    rejection_reason: str | None = None


# =========================================================================
# Dependencies
# =========================================================================

# Re-export for convenience
CurrentUserDep = Annotated[dict[str, Any], Depends(auth_get_current_user)]


async def require_compliance_officer(
    current_user: CurrentUserDep,
) -> dict[str, Any]:
    """Verify current user has compliance_officer role.

    This implements the API Layer pre-validation pattern (ADR-011).
    Role validation happens here in the async API layer,
    NOT in the synchronous ApprovalWorkflowService.

    Raises:
        HTTPException 403: If user lacks compliance_officer role.
    """
    roles = current_user.get("roles", [])
    if "compliance_officer" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have compliance_officer role",
        )
    return current_user


# =========================================================================
# Endpoints
# =========================================================================


@router.post("", response_model=ApprovalCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_approval_request(
    request: ApprovalCreateRequest,
    current_user: CurrentUserDep,
) -> ApprovalCreateResponse:
    """Create a new cross-border approval request.

    Any authenticated user can request a cross-border transfer.
    The request will be in PENDING status until approved/rejected.
    """
    service = ApprovalWorkflowService()

    approval = service.create_approval_request(
        data_id=request.data_id,
        destination=request.destination,
        purpose=request.purpose,
        requester=current_user["user_id"],
    )

    return ApprovalCreateResponse(
        id=approval.id,
        request_id=approval.request_id,
        data_id=approval.data_id,
        destination=approval.destination,
        purpose=approval.purpose,
        status=approval.status,
        requester=approval.requester,
        sla_deadline=approval.sla_deadline,
    )


@router.get("", response_model=ApprovalListResponse)
async def list_approval_requests(
    current_user: CurrentUserDep,
    status_filter: ApprovalStatus | None = None,
) -> ApprovalListResponse:
    """List cross-border approval requests.

    Users can see all requests (in production, filter by permissions).
    """
    service = ApprovalWorkflowService()

    approvals = service.list_approvals(status=status_filter)

    return ApprovalListResponse(
        approvals=[
            ApprovalResponse(
                id=a.id,
                request_id=a.request_id,
                data_id=a.data_id,
                destination=a.destination,
                purpose=a.purpose,
                status=a.status,
                requester=a.requester,
                approver=a.approver,
                rejection_reason=a.rejection_reason,
                requested_at=a.requested_at,
                approved_at=a.approved_at,
                sla_deadline=a.sla_deadline,
            )
            for a in approvals
        ],
        total=len(approvals),
    )


@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval_request(
    approval_id: UUID,
    current_user: CurrentUserDep,
) -> ApprovalResponse:
    """Get a specific approval request by ID."""
    service = ApprovalWorkflowService()

    approval = service.get_approval(approval_id)
    if approval is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval {approval_id} not found",
        )

    return ApprovalResponse(
        id=approval.id,
        request_id=approval.request_id,
        data_id=approval.data_id,
        destination=approval.destination,
        purpose=approval.purpose,
        status=approval.status,
        requester=approval.requester,
        approver=approval.approver,
        rejection_reason=approval.rejection_reason,
        requested_at=approval.requested_at,
        approved_at=approval.approved_at,
        sla_deadline=approval.sla_deadline,
    )


@router.post("/{approval_id}/approve", response_model=ApprovalActionResponse)
async def approve_approval_request(
    approval_id: UUID,
    current_user: Annotated[dict[str, Any], Depends(require_compliance_officer)],
) -> ApprovalActionResponse:
    """Approve a cross-border transfer request.

    Requires compliance_officer role.
    Role validation is done by require_compliance_officer dependency.

    Raises:
        HTTPException 403: If user lacks compliance_officer role.
        HTTPException 404: If approval request not found.
    """
    service = ApprovalWorkflowService()

    try:
        approval = service.approve(approval_id, current_user["user_id"])
    except ApprovalNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval {approval_id} not found",
        )

    return ApprovalActionResponse(
        id=approval.id,
        status=approval.status,
        approver=approval.approver,
        approved_at=approval.approved_at,
        rejection_reason=None,
    )


@router.post("/{approval_id}/reject", response_model=ApprovalActionResponse)
async def reject_approval_request(
    approval_id: UUID,
    reason: str,
    current_user: Annotated[dict[str, Any], Depends(require_compliance_officer)],
) -> ApprovalActionResponse:
    """Reject a cross-border transfer request.

    Requires compliance_officer role.
    Role validation is done by require_compliance_officer dependency.

    Raises:
        HTTPException 403: If user lacks compliance_officer role.
        HTTPException 404: If approval request not found.
    """
    service = ApprovalWorkflowService()

    try:
        approval = service.reject(approval_id, current_user["user_id"], reason)
    except ApprovalNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval {approval_id} not found",
        )

    return ApprovalActionResponse(
        id=approval.id,
        status=approval.status,
        approver=approval.approver,
        approved_at=approval.approved_at,
        rejection_reason=approval.rejection_reason,
    )
