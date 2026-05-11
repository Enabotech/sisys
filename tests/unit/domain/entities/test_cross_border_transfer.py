"""Tests for CrossBorderTransferRequest domain entity.

TDD Red Phase: These tests define expected behavior before implementation.
"""

from datetime import UTC

import pytest


class TestCrossBorderTransferRequestCreation:
    """Test CrossBorderTransferRequest entity creation."""

    def test_create_with_required_fields(self):
        """Test creating CrossBorderTransferRequest with required fields."""
        from src.domain.entities.cross_border_transfer import CrossBorderTransferRequest

        request = CrossBorderTransferRequest(
            data_id="data-123",
            destination="US",
            purpose="Model Inference",
            requester="user-456",
        )

        assert request.data_id == "data-123"
        assert request.destination == "US"
        assert request.purpose == "Model Inference"
        assert request.requester == "user-456"
        assert request.request_id is not None
        assert request.status.value == "pending"

    def test_create_with_all_fields(self):
        """Test creating CrossBorderTransferRequest with all fields."""
        import uuid
        from datetime import datetime

        from src.domain.entities.cross_border_transfer import (
            CrossBorderTransferRequest,
            LegalBasisType,
            TransferStatus,
        )

        custom_id = uuid.uuid4()
        now = datetime.now(UTC)

        request = CrossBorderTransferRequest(
            request_id=custom_id,
            data_id="data-789",
            destination="EU",
            purpose="Analytics",
            status=TransferStatus.APPROVED,
            requester="admin-001",
            approver="approver-002",
            approval_timestamp=now,
            legal_basis_type=LegalBasisType.SCC,
        )

        assert request.request_id == custom_id
        assert request.status == TransferStatus.APPROVED
        assert request.approver == "approver-002"
        assert request.legal_basis_type == LegalBasisType.SCC


class TestCrossBorderTransferRequestMethods:
    """Test CrossBorderTransferRequest business methods."""

    def test_approve(self):
        """Test approve method changes status to approved."""
        from src.domain.entities.cross_border_transfer import (
            CrossBorderTransferRequest,
            TransferStatus,
        )

        request = CrossBorderTransferRequest(
            data_id="data-123",
            destination="US",
            purpose="Test",
            requester="user-456",
        )

        approved = request.approve(approver="admin-001")

        assert approved.status == TransferStatus.APPROVED
        assert approved.approver == "admin-001"
        assert approved.approval_timestamp is not None

    def test_reject(self):
        """Test reject method changes status to rejected."""
        from src.domain.entities.cross_border_transfer import (
            CrossBorderTransferRequest,
            TransferStatus,
        )

        request = CrossBorderTransferRequest(
            data_id="data-123",
            destination="US",
            purpose="Test",
            requester="user-456",
        )

        rejected = request.reject(approver="admin-001")

        assert rejected.status == TransferStatus.REJECTED
        assert rejected.approver == "admin-001"

    def test_execute(self):
        """Test execute method changes status to executed."""
        from src.domain.entities.cross_border_transfer import (
            CrossBorderTransferRequest,
            TransferStatus,
        )

        request = CrossBorderTransferRequest(
            data_id="data-123",
            destination="US",
            purpose="Test",
            requester="user-456",
            status=TransferStatus.APPROVED,
        )

        executed = request.execute()

        assert executed.status == TransferStatus.EXECUTED

    def test_block(self):
        """Test block method changes status to blocked."""
        from src.domain.entities.cross_border_transfer import (
            CrossBorderTransferRequest,
            TransferStatus,
        )

        request = CrossBorderTransferRequest(
            data_id="data-123",
            destination="US",
            purpose="Test",
            requester="user-456",
        )

        blocked = request.block()

        assert blocked.status == TransferStatus.BLOCKED

    def test_is_pending(self):
        """Test is_pending returns True when status is pending."""
        from src.domain.entities.cross_border_transfer import (
            CrossBorderTransferRequest,
        )

        request = CrossBorderTransferRequest(
            data_id="data-123",
            destination="US",
            purpose="Test",
            requester="user-456",
        )

        assert request.is_pending() is True

    def test_is_pending_false_after_approval(self):
        """Test is_pending returns False after approval."""
        from src.domain.entities.cross_border_transfer import (
            CrossBorderTransferRequest,
            TransferStatus,
        )

        request = CrossBorderTransferRequest(
            data_id="data-123",
            destination="US",
            purpose="Test",
            requester="user-456",
            status=TransferStatus.APPROVED,
        )

        assert request.is_pending() is False


class TestCrossBorderTransferRequestImmutability:
    """Test that CrossBorderTransferRequest is immutable."""

    def test_is_frozen_dataclass(self):
        """Test CrossBorderTransferRequest is a frozen dataclass."""
        from src.domain.entities.cross_border_transfer import CrossBorderTransferRequest

        request = CrossBorderTransferRequest()
        with pytest.raises(AttributeError):
            request.status = None  # type: ignore

    def test_request_id_not_modifiable(self):
        """Test request_id cannot be modified after creation."""
        from src.domain.entities.cross_border_transfer import CrossBorderTransferRequest

        request = CrossBorderTransferRequest()
        with pytest.raises(AttributeError):
            request.request_id = None  # type: ignore
