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

    def approve(
        self,
        approval_id: UUID | None = None,
        approver: str = "",
        request_id: UUID | None = None,
    ) -> CrossBorderApproval:
        """Approve a cross-border transfer request.

        Args:
            approval_id: ID of approval request (deprecated, use request_id).
            approver: User ID of compliance officer.
            request_id: ID of approval request (alias for approval_id).

        Returns:
            Updated CrossBorderApproval.

        Raises:
            ApprovalNotFoundError: If approval request not found.
        """
        # Support both parameter names for compatibility
        actual_id = request_id or approval_id
        if not actual_id:
            raise ApprovalNotFoundError("approval_id or request_id must be provided")

        approval = self._approvals.get(actual_id)
        if approval is None:
            raise ApprovalNotFoundError(f"Approval {actual_id} not found")

        if approval.status != ApprovalStatus.PENDING:
            raise ValueError(f"Cannot approve from status {approval.status.value}")

        approval.approve(approver)
        return approval

    def reject(
        self,
        approval_id: UUID | None = None,
        approver: str = "",
        reason: str = "",
        request_id: UUID | None = None,
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
        # Support both parameter names for compatibility
        actual_id = request_id or approval_id
        if not actual_id:
            raise ApprovalNotFoundError("approval_id or request_id must be provided")

        approval = self._approvals.get(actual_id)
        if approval is None:
            raise ApprovalNotFoundError(f"Approval {actual_id} not found")

        if approval.status != ApprovalStatus.PENDING:
            raise ValueError(f"Cannot reject from status {approval.status.value}")

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

    def create_request(
        self,
        data_id: UUID,
        destination: str,
        purpose: str,
        requester: str,
    ) -> CrossBorderApproval:
        """Create a new cross-border approval request.

        Alias for create_approval_request().

        Args:
            data_id: UUID of data to be transferred.
            destination: Target country/region.
            purpose: Purpose of transfer.
            requester: User ID who requested the transfer.

        Returns:
            Created CrossBorderApproval.
        """
        return self.create_approval_request(
            data_id=data_id,
            destination=destination,
            purpose=purpose,
            requester=requester,
        )

    def list_requests(
        self,
        status: ApprovalStatus | None = None,
    ) -> list[CrossBorderApproval]:
        """List approval requests with optional status filter.

        Alias for list_approvals().

        Args:
            status: Filter by approval status.

        Returns:
            List of matching CrossBorderApproval.
        """
        return self.list_approvals(status=status)

    def get_history(self, data_id: UUID) -> list[CrossBorderApproval]:
        """Get approval history for a specific data item.

        Args:
            data_id: UUID of the data item.

        Returns:
            List of approval records for the data item.
        """
        return [a for a in self._approvals.values() if a.data_id == data_id]

    def validate_transfer(
        self,
        data_id: UUID,
        destination: str,
    ) -> bool:
        """Validate if a cross-border transfer is allowed.

        Args:
            data_id: UUID of data to be transferred.
            destination: Target destination.

        Returns:
            True if transfer is allowed (approved), False otherwise.
        """
        approvals = self.get_history(data_id)
        if not approvals:
            return False

        # Check if ANY approval has APPROVED status (not just the most recent)
        return any(a.status == ApprovalStatus.APPROVED for a in approvals)

    def get_approval_rate_report(self) -> dict:
        """Get approval rate statistics report.

        Returns:
            Dict with approval rate statistics.
        """
        total = len(self._approvals)
        if total == 0:
            return {
                "total_requests": 0,
                "approved": 0,
                "rejected": 0,
                "pending": 0,
                "approval_rate": 1.0,
            }

        approved = sum(1 for a in self._approvals.values() if a.status == ApprovalStatus.APPROVED)
        rejected = sum(1 for a in self._approvals.values() if a.status == ApprovalStatus.REJECTED)
        pending = sum(1 for a in self._approvals.values() if a.status == ApprovalStatus.PENDING)

        return {
            "total_requests": total,
            "approved": approved,
            "rejected": rejected,
            "pending": pending,
            "approval_rate": approved / total if total > 0 else 0.0,
        }

    def validate_all_transfers(
        self,
        requests: list[CrossBorderApproval],
    ) -> list[CrossBorderApproval]:
        """Validate all transfer requests.

        Args:
            requests: List of CrossBorderApproval to validate.

        Returns:
            List of validated approvals (those that are approved).
        """
        return [r for r in requests if r.status == ApprovalStatus.APPROVED]

    def escalate_request(self, approval_id: UUID) -> CrossBorderApproval:
        """Escalate an approval request to上级合规官.

        Args:
            approval_id: ID of approval request to escalate.

        Returns:
            Updated CrossBorderApproval.

        Raises:
            ApprovalNotFoundError: If approval request not found.
        """
        approval = self._approvals.get(approval_id)
        if approval is None:
            raise ApprovalNotFoundError(f"Approval {approval_id} not found")

        if approval.status == ApprovalStatus.PENDING:
            from datetime import timedelta

            approval.sla_deadline = datetime.now(UTC) + timedelta(hours=self._config.cross_border_sla_hours)

        return approval
