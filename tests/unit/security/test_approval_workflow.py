"""Tests for ApprovalWorkflowService.

TDD Red phase - tests should fail before implementation.
Reference: Story 1.11 Data Sovereignty Isolation - AC-4.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest

from src.infrastructure.security.models import ApprovalStatus


class TestApprovalWorkflowService:
    """ApprovalWorkflowService tests for cross-border approval workflow."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        from src.infrastructure.security.approval_workflow import ApprovalWorkflowService

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

    def test_list_pending_approvals(self, service):
        """Should list all pending approvals."""
        # Create multiple requests
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
        # SLA should be 48 hours from creation
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        deadline = approval.sla_deadline
        # Should be approximately 48 hours later
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

    def test_create_request_alias(self, service):
        """Should create request using alias method."""
        result = service.create_request(
            data_id=uuid4(),
            destination="EU",
            purpose="GDPR compliance",
            requester="user456",
        )

        assert result is not None
        assert result.destination == "EU"

    def test_list_requests_alias(self, service):
        """Should list requests using alias method."""
        service.create_approval_request(uuid4(), "US", "Test1", "user1")
        service.create_approval_request(uuid4(), "EU", "Test2", "user2")

        requests = service.list_requests()

        assert len(requests) == 2

    def test_get_history(self, service):
        """Should get approval history for a data item."""
        data_id = uuid4()
        service.create_approval_request(data_id, "US", "First request", "user1")
        service.create_approval_request(data_id, "EU", "Second request", "user2")

        history = service.get_history(data_id)

        assert len(history) == 2

    def test_get_history_no_requests(self, service):
        """Should return empty list when no history exists."""
        history = service.get_history(uuid4())

        assert history == []

    def test_validate_transfer_approved(self, service):
        """Should return True when transfer has approved request."""
        data_id = uuid4()
        approval = service.create_approval_request(data_id, "US", "Test", "user1")
        service.approve(approval.id, "compliance_officer")

        result = service.validate_transfer(data_id, "US")

        assert result is True

    def test_validate_transfer_not_approved(self, service):
        """Should return False when no approved request exists."""
        data_id = uuid4()
        service.create_approval_request(data_id, "US", "Test", "user1")

        result = service.validate_transfer(data_id, "US")

        assert result is False

    def test_validate_transfer_no_history(self, service):
        """Should return False when no history exists."""
        result = service.validate_transfer(uuid4(), "US")

        assert result is False

    def test_get_approval_rate_report_empty(self, service):
        """Should return empty report when no approvals."""
        report = service.get_approval_rate_report()

        assert report["total_requests"] == 0
        assert report["approval_rate"] == 1.0

    def test_get_approval_rate_report(self, service):
        """Should calculate approval rate correctly."""
        approval1 = service.create_approval_request(uuid4(), "US", "Test1", "user1")
        approval2 = service.create_approval_request(uuid4(), "EU", "Test2", "user2")
        service.create_approval_request(uuid4(), "JP", "Test3", "user3")  # pending

        service.approve(approval1.id, "officer1")
        service.reject(approval2.id, "officer2", "Rejected")

        report = service.get_approval_rate_report()

        assert report["total_requests"] == 3
        assert report["approved"] == 1
        assert report["rejected"] == 1
        assert report["pending"] == 1
        assert report["approval_rate"] == 1 / 3

    def test_validate_all_transfers(self, service):
        """Should return only approved transfers."""
        approval1 = service.create_approval_request(uuid4(), "US", "Test1", "user1")
        approval2 = service.create_approval_request(uuid4(), "EU", "Test2", "user2")
        service.create_approval_request(uuid4(), "JP", "Test3", "user3")  # pending

        service.approve(approval1.id, "officer1")
        # approval2 is rejected
        service.reject(approval2.id, "officer2", "Rejected")
        # approval3 is pending

        approvals = service.list_approvals()
        validated = service.validate_all_transfers(approvals)

        assert len(validated) == 1
        assert validated[0].status == ApprovalStatus.APPROVED

    def test_escalate_request(self, service):
        """Should escalate pending request by extending SLA."""
        approval = service.create_approval_request(
            data_id=uuid4(),
            destination="US",
            purpose="Test",
            requester="user1",
        )

        original_deadline = approval.sla_deadline
        result = service.escalate_request(approval.id)

        assert result.sla_deadline >= original_deadline

    def test_escalate_request_not_found(self, service):
        """Should raise error when approval not found."""
        from src.infrastructure.security.approval_workflow import ApprovalNotFoundError

        with pytest.raises(ApprovalNotFoundError):
            service.escalate_request(uuid4())

    def test_approve_with_request_id(self, service):
        """Should support request_id as alias for approval_id."""
        approval = service.create_approval_request(
            data_id=uuid4(),
            destination="US",
            purpose="Test",
            requester="user1",
        )

        result = service.approve(request_id=approval.id, approver="officer")

        assert result.status == ApprovalStatus.APPROVED

    def test_reject_with_request_id(self, service):
        """Should support request_id as alias for approval_id."""
        approval = service.create_approval_request(
            data_id=uuid4(),
            destination="US",
            purpose="Test",
            requester="user1",
        )

        result = service.reject(request_id=approval.id, approver="officer", reason="No reason")

        assert result.status == ApprovalStatus.REJECTED

    def test_approve_without_id_raises(self, service):
        """Should raise error when neither approval_id nor request_id provided."""
        from src.infrastructure.security.approval_workflow import ApprovalNotFoundError

        with pytest.raises(ApprovalNotFoundError):
            service.approve(approval_id=None, approver="officer", request_id=None)

    def test_reject_without_id_raises(self, service):
        """Should raise error when neither approval_id nor request_id provided."""
        from src.infrastructure.security.approval_workflow import ApprovalNotFoundError

        with pytest.raises(ApprovalNotFoundError):
            service.reject(approval_id=None, approver="officer", reason="reason", request_id=None)

    def test_approve_non_pending_raises(self, service):
        """Should raise error when approving non-pending request."""
        approval = service.create_approval_request(uuid4(), "US", "Test", "user1")
        service.approve(approval.id, "officer")

        with pytest.raises(ValueError, match="Cannot approve from status"):
            service.approve(approval.id, "officer2")

    def test_reject_non_pending_raises(self, service):
        """Should raise error when rejecting non-pending request."""
        approval = service.create_approval_request(uuid4(), "US", "Test", "user1")
        service.reject(approval.id, "officer", "Rejected")

        with pytest.raises(ValueError, match="Cannot reject from status"):
            service.reject(approval.id, "officer2", "Rejected2")
