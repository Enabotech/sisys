"""Tests for sovereignty API contract models.

Tests Pydantic models for API request/response validation.
Reference: Story 1.11 Data Sovereignty Isolation.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError


class TestWhitelistRuleCreate:
    """Tests for WhitelistRuleCreate model."""

    def test_valid_create_request(self):
        """Should create with required fields."""
        from src.interfaces.api.sovereignty_endpoints import WhitelistRuleCreate

        rule = WhitelistRuleCreate(
            endpoint="https://api.example.com",
            provider="ExampleAPI",
        )
        assert rule.endpoint == "https://api.example.com"
        assert rule.provider == "ExampleAPI"
        assert rule.purpose == ""
        assert rule.risk_level == "medium"
        assert rule.expiry_date is None

    def test_create_with_all_fields(self):
        """Should create with all fields."""
        from src.interfaces.api.sovereignty_endpoints import WhitelistRuleCreate

        expiry = datetime(2025, 12, 31)
        rule = WhitelistRuleCreate(
            endpoint="https://api.example.com",
            provider="ExampleAPI",
            purpose="Data sync",
            risk_level="high",
            expiry_date=expiry,
        )
        assert rule.purpose == "Data sync"
        assert rule.risk_level == "high"
        assert rule.expiry_date == expiry

    def test_create_missing_required_fields(self):
        """Should fail when required fields missing."""
        from src.interfaces.api.sovereignty_endpoints import WhitelistRuleCreate

        with pytest.raises(ValidationError):
            WhitelistRuleCreate(endpoint="https://api.example.com")

        with pytest.raises(ValidationError):
            WhitelistRuleCreate(provider="ExampleAPI")


class TestWhitelistValidateRequest:
    """Tests for WhitelistValidateRequest model."""

    def test_valid_request(self):
        """Should create with endpoint."""
        from src.interfaces.api.sovereignty_endpoints import WhitelistValidateRequest

        req = WhitelistValidateRequest(endpoint="https://api.example.com")
        assert req.endpoint == "https://api.example.com"


class TestWhitelistValidateResponse:
    """Tests for WhitelistValidateResponse model."""

    def test_allowed_response(self):
        """Should create allowed response."""
        from src.interfaces.api.sovereignty_endpoints import WhitelistValidateResponse

        resp = WhitelistValidateResponse(
            is_allowed=True,
            matched_rule_id=uuid4(),
            reason="Matched rule",
        )
        assert resp.is_allowed is True
        assert resp.matched_rule_id is not None
        assert resp.reason == "Matched rule"

    def test_denied_response(self):
        """Should create denied response."""
        from src.interfaces.api.sovereignty_endpoints import WhitelistValidateResponse

        resp = WhitelistValidateResponse(
            is_allowed=False,
            reason="Endpoint not in whitelist",
        )
        assert resp.is_allowed is False
        assert resp.matched_rule_id is None


class TestCrossBorderApprovalCreate:
    """Tests for CrossBorderApprovalCreate model."""

    def test_valid_create_request(self):
        """Should create with required fields."""
        from src.interfaces.api.sovereignty_endpoints import CrossBorderApprovalCreate

        data_id = uuid4()
        req = CrossBorderApprovalCreate(
            data_id=data_id,
            destination="US",
            purpose="International collaboration",
            requester="user123",
        )
        assert req.data_id == data_id
        assert req.destination == "US"
        assert req.purpose == "International collaboration"
        assert req.requester == "user123"

    def test_create_missing_required_fields(self):
        """Should fail when required fields missing."""
        from src.interfaces.api.sovereignty_endpoints import CrossBorderApprovalCreate

        with pytest.raises(ValidationError):
            CrossBorderApprovalCreate(destination="US", purpose="test", requester="user")

        with pytest.raises(ValidationError):
            CrossBorderApprovalCreate(data_id=uuid4(), purpose="test", requester="user")


class TestCrossBorderApprovalAction:
    """Tests for CrossBorderApprovalAction model."""

    def test_approve_action(self):
        """Should create approve action."""
        from src.interfaces.api.sovereignty_endpoints import CrossBorderApprovalAction

        action = CrossBorderApprovalAction(approver="compliance_officer")
        assert action.approver == "compliance_officer"
        assert action.reason is None

    def test_reject_action(self):
        """Should create reject action with reason."""
        from src.interfaces.api.sovereignty_endpoints import CrossBorderApprovalAction

        action = CrossBorderApprovalAction(
            approver="compliance_officer",
            reason="Policy violation",
        )
        assert action.approver == "compliance_officer"
        assert action.reason == "Policy violation"


class TestComplianceStatusResponse:
    """Tests for ComplianceStatusResponse model."""

    def test_compliance_status(self):
        """Should create compliance status response."""
        from src.interfaces.api.sovereignty_endpoints import ComplianceStatusResponse

        resp = ComplianceStatusResponse(
            sovereignty_enabled=True,
            data_residency_compliance=True,
            whitelist_validation_rate=1.0,
            cross_border_approval_rate=1.0,
            sensitive_data_detection_rate=0.95,
            pipl_compliance=True,
            last_audit_at=datetime(2025, 1, 1),
        )
        assert resp.sovereignty_enabled is True
        assert resp.data_residency_compliance is True
        assert resp.whitelist_validation_rate == 1.0
        assert resp.pipl_compliance is True


class TestDataSovereigntyStatus:
    """Tests for DataSovereigntyStatus model."""

    def test_sensitive_data_status(self):
        """Should create sovereignty status for sensitive data."""
        from src.infrastructure.security.models import DataResidency, SensitiveDataType
        from src.interfaces.api.sovereignty_endpoints import DataSovereigntyStatus

        resp = DataSovereigntyStatus(
            data_id=uuid4(),
            is_sensitive=True,
            sensitive_type=SensitiveDataType.PII,
            residency_requirement=DataResidency.CHINA_DOMESTIC,
            is_domestic_storage=True,
            cross_border_status="allowed",
        )
        assert resp.is_sensitive is True
        assert resp.sensitive_type == SensitiveDataType.PII
        assert resp.residency_requirement == DataResidency.CHINA_DOMESTIC
        assert resp.is_domestic_storage is True


class TestPIPLComplianceReport:
    """Tests for PIPLComplianceReport model."""

    def test_pipl_report(self):
        """Should create PIPL compliance report."""
        from src.interfaces.api.sovereignty_endpoints import PIPLComplianceReport

        report = PIPLComplianceReport(
            report_id=uuid4(),
            generated_at=datetime(2025, 1, 1),
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 12, 31),
            total_pipl_processing_records=1000,
            consent_records=800,
            legal_basis_breakdown={"consent": 600, "legitimate_interest": 400},
            data_subject_rights_exercised={"access": 50, "deletion": 10},
            biometric_processing_count=100,
            minor_data_processing_count=50,
        )
        assert report.total_pipl_processing_records == 1000
        assert report.consent_records == 800
        assert report.biometric_processing_count == 100
        assert report.minor_data_processing_count == 50


class TestErrorResponse:
    """Tests for ErrorResponse model."""

    def test_error_response(self):
        """Should create error response."""
        from src.interfaces.api.sovereignty_endpoints import ErrorResponse

        resp = ErrorResponse(
            error="validation_error",
            message="Invalid input",
            details={"field": "endpoint", "issue": "Invalid URL format"},
        )
        assert resp.error == "validation_error"
        assert resp.message == "Invalid input"
        assert resp.details["field"] == "endpoint"


class TestValidationErrorResponse:
    """Tests for ValidationErrorResponse model."""

    def test_validation_error(self):
        """Should create validation error response."""
        from src.interfaces.api.sovereignty_endpoints import ValidationErrorResponse

        resp = ValidationErrorResponse(
            message="Validation failed",
            field_errors=[
                {"field": "endpoint", "issue": "Required"},
                {"field": "provider", "issue": "Required"},
            ],
        )
        assert resp.error == "validation_error"
        assert len(resp.field_errors) == 2
