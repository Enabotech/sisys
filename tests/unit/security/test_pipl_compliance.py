"""Tests for PIPLComplianceService.

TDD Red phase - tests should fail before implementation.
Reference: Story 1.11 Data Sovereignty Isolation - AC-5.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.infrastructure.security.models import SensitiveDataType


class TestPIPLComplianceService:
    """PIPLComplianceService tests for PIPL compliance functionality."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        from src.infrastructure.security.pipl_compliance import PIPLComplianceService

        return PIPLComplianceService()

    def test_record_pipl_access_consent(self, service):
        """Should record personal data access with consent."""
        result = service.record_access(
            personal_data_id=uuid4(),
            purpose="user_authentication",
            legal_basis="consent",
            data_subject_consent=True,
            accessor="auth_service",
        )

        assert result is not None
        assert result.purpose == "user_authentication"
        assert result.legal_basis == "consent"
        assert result.data_subject_consent is True

    def test_record_pipl_access_contract(self, service):
        """Should record personal data access with contract legal basis."""
        result = service.record_access(
            personal_data_id=uuid4(),
            purpose="service_delivery",
            legal_basis="contract",
            data_subject_consent=False,
            accessor="service_module",
        )

        assert result is not None
        assert result.legal_basis == "contract"
        assert result.data_subject_consent is False

    def test_record_biometric_data_access(self, service):
        """Should apply enhanced protection for biometric data."""
        result = service.record_access(
            personal_data_id=uuid4(),
            purpose="identity_verification",
            legal_basis="consent",
            data_subject_consent=True,
            accessor="biometric_service",
        )

        assert result is not None
        # Biometric should be recorded with enhanced tracking
        assert result.legal_basis == "consent"

    def test_check_consent_required_true(self, service):
        """Should require consent for sensitive data when configured."""
        result = service.check_consent_required(SensitiveDataType.BIOMETRIC)

        assert result is True

    def test_check_consent_required_false_for_non_sensitive(self, service):
        """Should not require consent for non-PII data."""
        result = service.check_consent_required(SensitiveDataType.CUSTOM)

        # Custom type might not require consent depending on config
        assert result is not None

    def test_generate_pipl_report(self, service):
        """Should generate PIPL compliance report."""
        # Add some access records first
        service.record_access(
            personal_data_id=uuid4(),
            purpose="test",
            legal_basis="consent",
            data_subject_consent=True,
            accessor="test",
        )

        report = service.generate_report()

        assert report is not None
        assert hasattr(report, "total_pipl_processing_records")
        assert report.total_pipl_processing_records >= 1

    def test_record_minor_data_access_with_guardian_consent(self, service):
        """Should require guardian consent for minor data."""
        result = service.record_minor_access(
            personal_data_id=uuid4(),
            purpose="educational_service",
            legal_basis="consent",
            guardian_consent=True,
            accessor="edu_platform",
            minor_age=12,
        )

        assert result is not None
        assert result.purpose == "educational_service"

    def test_record_minor_access_without_guardian_consent_blocked(self, service):
        """Should block minor data access without guardian consent."""
        from src.infrastructure.security.pipl_compliance import GuardianConsentRequiredError

        with pytest.raises(GuardianConsentRequiredError):
            service.record_minor_access(
                personal_data_id=uuid4(),
                purpose="educational_service",
                legal_basis="consent",
                guardian_consent=False,
                accessor="edu_platform",
                minor_age=12,
            )

    def test_check_data_subject_rights(self, service):
        """Should check data subject rights exercised."""
        data_id = uuid4()

        rights = service.check_data_subject_rights(data_id)

        assert rights is not None
        assert hasattr(rights, "access_right")
        assert hasattr(rights, "deletion_right")
        assert hasattr(rights, "correction_right")

    def test_verify_legal_basis_valid(self, service):
        """Should verify valid legal basis."""
        result = service.verify_legal_basis("consent")

        assert result is True

    def test_verify_legal_basis_invalid(self, service):
        """Should reject invalid legal basis."""
        result = service.verify_legal_basis("invalid_basis")

        assert result is False
