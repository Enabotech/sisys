"""Tests for CrossBorderTransferService service implementation.

TDD Red Phase: These tests define expected cross-border transfer behavior.
"""

import pytest


class TestCrossBorderTransferServiceRequestTransfer:
    """Test request_transfer functionality."""

    def test_request_transfer_creates_pending_request(self):
        """Test request_transfer creates a pending request."""
        from src.domain.entities.cross_border_transfer import (
            CrossBorderTransferRequest,
            LegalBasisType,
            TransferStatus,
        )
        from src.infrastructure.security.cross_border_transfer_service_impl import CrossBorderTransferServiceImpl

        service = CrossBorderTransferServiceImpl()

        request = CrossBorderTransferRequest(
            data_id="data-123",
            destination="US",
            purpose="Model Inference",
            requester="user-001",
            legal_basis_type=LegalBasisType.SCC,
        )

        service.request_transfer(request)

        # Verify request was stored
        stored = service.get_request(str(request.request_id))
        assert stored is not None
        assert stored.status == TransferStatus.PENDING


class TestCrossBorderTransferServiceApprove:
    """Test approve functionality."""

    def test_approve_transfer(self):
        """Test approving a transfer request."""
        from src.domain.entities.cross_border_transfer import (
            CrossBorderTransferRequest,
            LegalBasisType,
            TransferStatus,
        )
        from src.infrastructure.security.cross_border_transfer_service_impl import CrossBorderTransferServiceImpl

        service = CrossBorderTransferServiceImpl()

        request = CrossBorderTransferRequest(
            data_id="data-123",
            destination="US",
            purpose="Model Inference",
            requester="user-001",
            legal_basis_type=LegalBasisType.SCC,
        )

        service.request_transfer(request)

        # Approve the request
        service.approve(str(request.request_id), approver="admin-001")

        # Verify request was approved
        stored = service.get_request(str(request.request_id))
        assert stored is not None
        assert stored.status == TransferStatus.APPROVED
        assert stored.approver == "admin-001"
        assert stored.approval_timestamp is not None

    def test_approve_nonexistent_request(self):
        """Test approving a nonexistent request raises error."""
        from src.infrastructure.security.cross_border_transfer_service_impl import (
            CrossBorderTransferServiceImpl,
            TransferNotFoundError,
        )

        service = CrossBorderTransferServiceImpl()

        with pytest.raises(TransferNotFoundError):
            service.approve("nonexistent-id", approver="admin-001")


class TestCrossBorderTransferServiceReject:
    """Test reject functionality."""

    def test_reject_transfer(self):
        """Test rejecting a transfer request."""
        from src.domain.entities.cross_border_transfer import (
            CrossBorderTransferRequest,
            LegalBasisType,
            TransferStatus,
        )
        from src.infrastructure.security.cross_border_transfer_service_impl import CrossBorderTransferServiceImpl

        service = CrossBorderTransferServiceImpl()

        request = CrossBorderTransferRequest(
            data_id="data-123",
            destination="US",
            purpose="Model Inference",
            requester="user-001",
            legal_basis_type=LegalBasisType.SCC,
        )

        service.request_transfer(request)
        service.reject(str(request.request_id), approver="admin-001")

        stored = service.get_request(str(request.request_id))
        assert stored is not None
        assert stored.status == TransferStatus.REJECTED


class TestCrossBorderTransferServiceExecute:
    """Test execute functionality."""

    def test_execute_approved_transfer(self):
        """Test executing an approved transfer."""
        from src.domain.entities.cross_border_transfer import (
            CrossBorderTransferRequest,
            LegalBasisType,
            TransferStatus,
        )
        from src.infrastructure.security.cross_border_transfer_service_impl import CrossBorderTransferServiceImpl

        service = CrossBorderTransferServiceImpl()

        request = CrossBorderTransferRequest(
            data_id="data-123",
            destination="US",
            purpose="Model Inference",
            requester="user-001",
            legal_basis_type=LegalBasisType.SCC,
        )

        service.request_transfer(request)
        service.approve(str(request.request_id), approver="admin-001")
        service.execute(str(request.request_id))

        stored = service.get_request(str(request.request_id))
        assert stored is not None
        assert stored.status == TransferStatus.EXECUTED

    def test_execute_pending_transfer_fails(self):
        """Test executing a pending (not approved) transfer raises error."""
        from src.domain.entities.cross_border_transfer import (
            CrossBorderTransferRequest,
            LegalBasisType,
        )
        from src.infrastructure.security.cross_border_transfer_service_impl import (
            CrossBorderTransferServiceImpl,
            TransferNotApprovedError,
        )

        service = CrossBorderTransferServiceImpl()

        request = CrossBorderTransferRequest(
            data_id="data-123",
            destination="US",
            purpose="Model Inference",
            requester="user-001",
            legal_basis_type=LegalBasisType.SCC,
        )

        service.request_transfer(request)

        with pytest.raises(TransferNotApprovedError):
            service.execute(str(request.request_id))


class TestCrossBorderTransferServiceBlock:
    """Test block functionality."""

    def test_block_transfer(self):
        """Test blocking a transfer request."""
        from src.domain.entities.cross_border_transfer import (
            CrossBorderTransferRequest,
            LegalBasisType,
            TransferStatus,
        )
        from src.infrastructure.security.cross_border_transfer_service_impl import CrossBorderTransferServiceImpl

        service = CrossBorderTransferServiceImpl()

        request = CrossBorderTransferRequest(
            data_id="data-123",
            destination="US",
            purpose="Model Inference",
            requester="user-001",
            legal_basis_type=LegalBasisType.SCC,
        )

        service.request_transfer(request)
        service.block(str(request.request_id))

        stored = service.get_request(str(request.request_id))
        assert stored is not None
        assert stored.status == TransferStatus.BLOCKED


class TestCrossBorderTransferServiceSLAControl:
    """Test SLA control functionality."""

    def test_sla_normal_4_hours(self):
        """Test normal SLA is 4 hours."""
        from src.infrastructure.security.cross_border_transfer_service_impl import CrossBorderTransferServiceImpl

        service = CrossBorderTransferServiceImpl()
        assert service.SLA_NORMAL_HOURS == 4

    def test_sla_urgent_1_hour(self):
        """Test urgent SLA is 1 hour."""
        from src.infrastructure.security.cross_border_transfer_service_impl import CrossBorderTransferServiceImpl

        service = CrossBorderTransferServiceImpl()
        assert service.SLA_URGENT_HOURS == 1
