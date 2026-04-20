"""Approval Workflow Service.

Implements cross-border data transfer approval workflow.
Reference: Story 1.11 Data Sovereignty Isolation - AC-4.

Architecture: Infrastructure layer service (hexagonal architecture).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from .models import ApprovalStatus, CrossBorderApproval

if TYPE_CHECKING:
    from ..config.sovereignty import DataSovereigntyConfig


class ApprovalNotFoundError(Exception):
    """Raised when approval request is not found."""

    pass


class ApprovalWorkflowService:
    """Service for managing cross-border approval workflow.

    Handles:
    - Approval request creation
    - Approval/rejection actions
    - SLA deadline tracking
    - Request listing and retrieval

    NOTE: This service is SYNCHRONOUS. All role authorization
    (i.e., verifying the approver has compliance_officer role)
    MUST be performed by the caller before invoking approve/reject.
    This service trusts the caller and does not validate roles internally.

    Architecture: API Layer pre-validation pattern (ADR-011).
    """

    def __init__(self, config: DataSovereigntyConfig | None = None) -> None:
        """Initialize service with configuration.

        Args:
            config: Data sovereignty configuration.
        """
        from ..config.sovereignty import get_sovereignty_config

        self._config = config or get_sovereignty_config()
        self._approvals: dict[UUID, CrossBorderApproval] = {}

    def create_approval_request(
        self,
        data_id: UUID,
        destination: str,
        purpose: str,
        requester: str,
    ) -> CrossBorderApproval:
        """Create a new cross-border approval request.

        Args:
            data_id: UUID of data to be transferred.
            destination: Target country/region.
            purpose: Purpose of transfer.
            requester: User ID who requested the transfer.

        Returns:
            Created CrossBorderApproval.

        Raises:
            ValueError: If requester is empty or invalid.
        """
        if not requester or not requester.strip():
            raise ValueError("Requester cannot be empty")

        # Calculate SLA deadline based on config
        sla_hours = self._config.cross_border_sla_hours
        sla_deadline = datetime.now(UTC) + timedelta(hours=sla_hours)

        approval = CrossBorderApproval(
            request_id=uuid4(),
            data_id=data_id,
            destination=destination,
            purpose=purpose,
            status=ApprovalStatus.PENDING,
            requester=requester.strip(),
            sla_deadline=sla_deadline,
        )

        self._approvals[approval.id] = approval
        return approval

    def approve(self, approval_id: UUID, approver: str) -> CrossBorderApproval:
        """Approve a cross-border transfer request.

        Args:
            approval_id: ID of approval request.
            approver: User ID of compliance officer.

        Returns:
            Updated CrossBorderApproval.

        Raises:
            ApprovalNotFoundError: If approval request not found.
        """
        approval = self._approvals.get(approval_id)
        if approval is None:
            raise ApprovalNotFoundError(f"Approval {approval_id} not found")

        approval.approve(approver)
        return approval

    def reject(
        self,
        approval_id: UUID,
        approver: str,
        reason: str,
    ) -> CrossBorderApproval:
        """Reject a cross-border transfer request.

        Args:
            approval_id: ID of approval request.
            approver: User ID of compliance officer.
            reason: Rejection reason.

        Returns:
            Updated CrossBorderApproval.

        Raises:
            ApprovalNotFoundError: If approval request not found.
        """
        approval = self._approvals.get(approval_id)
        if approval is None:
            raise ApprovalNotFoundError(f"Approval {approval_id} not found")

        approval.reject(approver, reason)
        return approval

    def get_approval(self, approval_id: UUID) -> CrossBorderApproval | None:
        """Get an approval request by ID.

        Args:
            approval_id: Approval request ID.

        Returns:
            CrossBorderApproval or None if not found.
        """
        return self._approvals.get(approval_id)

    def list_approvals(
        self,
        status: ApprovalStatus | None = None,
    ) -> list[CrossBorderApproval]:
        """List approval requests with optional status filter.

        Args:
            status: Filter by approval status.

        Returns:
            List of matching CrossBorderApproval.
        """
        approvals = list(self._approvals.values())

        if status is not None:
            approvals = [a for a in approvals if a.status == status]

        return approvals

    def check_sla_violations(self) -> list[CrossBorderApproval]:
        """Check for SLA violations (expired deadlines).

        Returns:
            List of approvals with expired SLA.
        """
        violations = []
        for approval in self._approvals.values():
            if approval.status == ApprovalStatus.PENDING and approval.is_sla_expired():
                violations.append(approval)
        return violations
