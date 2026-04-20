"""Tests for sovereignty API endpoints.

Tests for:
- ApprovalWorkflowService integration via API layer
- require_compliance_officer dependency
- Role validation (ADR-011)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from src.infrastructure.security.approval_workflow import ApprovalWorkflowService
from src.infrastructure.security.models import ApprovalStatus


class TestApprovalWorkflowService:
    """ApprovalWorkflowService tests for cross-border approval workflow."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return ApprovalWorkflowService()

    def test_create_approval_request(self, service):
        """Should create approval request with pending status."""
        result = service.create_approval_request(
            data_id=uuid4(),
            destination="US",
            purpose="International collaboration",
            requester="user123",
        )

        assert result is not None
        assert result.status == ApprovalStatus.PENDING
        assert result.destination == "US"
        assert result.requester == "user123"

    def test_approve_request(self, service):
        """Should approve request and update status."""
        approval = service.create_approval_request(
            data_id=uuid4(),
            destination="US",
            purpose="Test",
            requester="user123",
        )

        result = service.approve(approval.id, "compliance_officer")

        assert result is not None
        assert result.status == ApprovalStatus.APPROVED
        assert result.approver == "compliance_officer"
        assert result.approved_at is not None

    def test_reject_request(self, service):
        """Should reject request with reason."""
        approval = service.create_approval_request(
            data_id=uuid4(),
            destination="US",
            purpose="Test",
            requester="user123",
        )

        result = service.reject(approval.id, "compliance_officer", "Policy violation")

        assert result is not None
        assert result.status == ApprovalStatus.REJECTED
        assert result.rejection_reason == "Policy violation"
        assert result.approver == "compliance_officer"

    def test_approve_after_reject_raises_error(self, service):
        """Should raise error when trying to approve after reject."""
        approval = service.create_approval_request(
            data_id=uuid4(),
            destination="US",
            purpose="Test",
            requester="user123",
        )

        service.reject(approval.id, "compliance_officer", "Policy violation")

        with pytest.raises(ValueError, match="Cannot approve from status rejected"):
            service.approve(approval.id, "compliance_officer")

    def test_approve_empty_approver_raises_error(self, service):
        """Should raise error when approver is empty."""
        approval = service.create_approval_request(
            data_id=uuid4(),
            destination="US",
            purpose="Test",
            requester="user123",
        )

        with pytest.raises(ValueError, match="Approver cannot be empty"):
            service.approve(approval.id, "")

        with pytest.raises(ValueError, match="Approver cannot be empty"):
            service.approve(approval.id, "   ")

    def test_reject_empty_approver_raises_error(self, service):
        """Should raise error when approver is empty on reject."""
        approval = service.create_approval_request(
            data_id=uuid4(),
            destination="US",
            purpose="Test",
            requester="user123",
        )

        with pytest.raises(ValueError, match="Approver cannot be empty"):
            service.reject(approval.id, "", "reason")

    def test_list_pending_approvals(self, service):
        """Should list all pending approvals."""
        service.create_approval_request(uuid4(), "US", "Test1", "user1")
        service.create_approval_request(uuid4(), "EU", "Test2", "user2")
        service.create_approval_request(uuid4(), "JP", "Test3", "user3")

        pending = service.list_approvals(status=ApprovalStatus.PENDING)

        assert len(pending) == 3

    def test_sla_deadline_set(self, service):
        """Should set SLA deadline on creation."""
        approval = service.create_approval_request(
            data_id=uuid4(),
            destination="US",
            purpose="Test",
            requester="user123",
        )

        assert approval.sla_deadline is not None
        now = datetime.now(UTC)
        deadline = approval.sla_deadline
        diff = deadline - now
        assert timedelta(hours=47) < diff < timedelta(hours=49)

    def test_get_approval_by_id(self, service):
        """Should get approval by ID."""
        created = service.create_approval_request(
            data_id=uuid4(),
            destination="US",
            purpose="Test",
            requester="user123",
        )

        retrieved = service.get_approval(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id

    def test_get_nonexistent_approval(self, service):
        """Should return None for nonexistent approval."""
        result = service.get_approval(uuid4())

        assert result is None

    def test_double_approve_raises_error(self, service):
        """Should raise error when approving already approved request."""
        approval = service.create_approval_request(
            data_id=uuid4(),
            destination="US",
            purpose="Test",
            requester="user123",
        )

        service.approve(approval.id, "compliance_officer")

        with pytest.raises(ValueError, match="Cannot approve from status approved"):
            service.approve(approval.id, "another_officer")

    def test_double_reject_raises_error(self, service):
        """Should raise error when rejecting already rejected request."""
        approval = service.create_approval_request(
            data_id=uuid4(),
            destination="US",
            purpose="Test",
            requester="user123",
        )

        service.reject(approval.id, "compliance_officer", "reason")

        with pytest.raises(ValueError, match="Cannot reject from status rejected"):
            service.reject(approval.id, "another_officer", "another_reason")
