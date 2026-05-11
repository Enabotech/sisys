"""Tests for PIPLComplianceService service implementation.

TDD Red Phase: These tests define expected PIPL compliance behavior.
"""


class TestPIPLComplianceServiceRecordAccess:
    """Test record_access functionality."""

    def test_record_access_with_consent(self):
        """Test recording access with valid consent."""
        from src.domain.entities.pipl_compliance_record import (
            ConsentStatus,
            LegalBasis,
            PIPLComplianceRecord,
        )
        from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl

        service = PIPLComplianceServiceImpl()

        record = PIPLComplianceRecord(
            personal_data_id="pd-123",
            purpose="Analytics",
            legal_basis=LegalBasis.CONSENT.value,
            consent_status=ConsentStatus.GIVEN,
            accessor="system",
            data_subject_id="user-456",
        )

        service.record_access(record)

        # Verify record was stored
        stored = service.get_record("pd-123")
        assert stored is not None
        assert stored.consent_status == ConsentStatus.GIVEN

    def test_record_access_with_legal_obligation(self):
        """Test recording access with legal obligation basis."""
        from src.domain.entities.pipl_compliance_record import (
            LegalBasis,
            PIPLComplianceRecord,
        )
        from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl

        service = PIPLComplianceServiceImpl()

        record = PIPLComplianceRecord(
            personal_data_id="pd-456",
            purpose="Legal Compliance",
            legal_basis=LegalBasis.LEGAL_OBLIGATION.value,
            accessor="system",
            data_subject_id="user-789",
        )

        service.record_access(record)

        # Verify is_compliant returns True for legal obligation
        result = service.validate_legal_basis("pd-456", LegalBasis.LEGAL_OBLIGATION.value)
        assert result is True


class TestPIPLComplianceServiceValidateLegalBasis:
    """Test validate_legal_basis functionality."""

    def test_validate_consent_basis_with_given_consent(self):
        """Test consent basis is valid when consent is given."""
        from src.domain.entities.pipl_compliance_record import (
            ConsentStatus,
            LegalBasis,
            PIPLComplianceRecord,
        )
        from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl

        service = PIPLComplianceServiceImpl()

        record = PIPLComplianceRecord(
            personal_data_id="pd-123",
            purpose="Analytics",
            legal_basis=LegalBasis.CONSENT.value,
            consent_status=ConsentStatus.GIVEN,
            accessor="system",
            data_subject_id="user-456",
        )

        service.record_access(record)
        result = service.validate_legal_basis("pd-123", LegalBasis.CONSENT.value)
        assert result is True

    def test_validate_consent_basis_with_withdrawn_consent(self):
        """Test consent basis is invalid when consent is withdrawn."""
        from src.domain.entities.pipl_compliance_record import (
            ConsentStatus,
            LegalBasis,
            PIPLComplianceRecord,
        )
        from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl

        service = PIPLComplianceServiceImpl()

        record = PIPLComplianceRecord(
            personal_data_id="pd-123",
            purpose="Analytics",
            legal_basis=LegalBasis.CONSENT.value,
            consent_status=ConsentStatus.WITHDRAWN,
            accessor="system",
            data_subject_id="user-456",
        )

        service.record_access(record)
        result = service.validate_legal_basis("pd-123", LegalBasis.CONSENT.value)
        assert result is False

    def test_validate_non_consent_basis(self):
        """Test non-consent bases are always valid."""
        from src.domain.entities.pipl_compliance_record import (
            LegalBasis,
            PIPLComplianceRecord,
        )
        from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl

        service = PIPLComplianceServiceImpl()

        bases = [
            LegalBasis.CONTRACT.value,
            LegalBasis.LEGAL_OBLIGATION.value,
            LegalBasis.VITAL_INTEREST.value,
            LegalBasis.PUBLIC_TASK.value,
            LegalBasis.LEGITIMATE_INTEREST.value,
        ]

        for basis in bases:
            record = PIPLComplianceRecord(
                personal_data_id=f"pd-{basis}",
                purpose="Test",
                legal_basis=basis,
                accessor="system",
                data_subject_id="user-123",
            )
            service.record_access(record)
            result = service.validate_legal_basis(f"pd-{basis}", basis)
            assert result is True


class TestPIPLComplianceServiceDataSubjectRights:
    """Test data subject rights functionality."""

    def test_respond_to_access_request(self):
        """Test responding to data subject access request."""
        from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl

        service = PIPLComplianceServiceImpl()
        response = service.respond_to_access_request("user-123")

        assert "status" in response
        assert response["status"] == "available"

    def test_respond_to_correction_request(self):
        """Test responding to data subject correction request."""
        from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl

        service = PIPLComplianceServiceImpl()
        corrections = {"name": "New Name", "email": "new@example.com"}
        response = service.respond_to_correction_request("user-123", corrections)

        assert "status" in response
        assert response["status"] == "processed"

    def test_respond_to_deletion_request(self):
        """Test responding to data subject deletion request."""
        from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl

        service = PIPLComplianceServiceImpl()
        response = service.respond_to_deletion_request("user-123")

        assert "status" in response
        assert response["status"] == "deleted"

    def test_respond_to_portability_request(self):
        """Test responding to data subject portability request."""
        from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl

        service = PIPLComplianceServiceImpl()
        response = service.respond_to_portability_request("user-123")

        assert "status" in response
        assert response["status"] == "available"
        assert "data" in response


class TestPIPLComplianceServiceMinorConsent:
    """Test minor consent functionality."""

    def test_validate_minor_consent_with_guardian_consent(self):
        """Test minor consent is valid with guardian consent."""
        from src.domain.entities.pipl_compliance_record import (
            ConsentStatus,
            LegalBasis,
            PIPLComplianceRecord,
        )
        from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl

        service = PIPLComplianceServiceImpl()

        record = PIPLComplianceRecord(
            personal_data_id="pd-minor",
            purpose="Education Service",
            legal_basis=LegalBasis.MINOR_CONSENT.value,
            consent_status=ConsentStatus.GIVEN,
            accessor="system",
            data_subject_id="user-minor",
            is_minor=True,
            guardian_consent_obtained=True,
        )

        service.record_access(record)

        # Validate the record
        stored = service.get_record("pd-minor")
        assert stored is not None
        assert stored.validate_minor_consent() is True

    def test_validate_minor_consent_without_guardian_consent(self):
        """Test minor consent is invalid without guardian consent."""
        from src.domain.entities.pipl_compliance_record import (
            ConsentStatus,
            LegalBasis,
            PIPLComplianceRecord,
        )
        from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl

        service = PIPLComplianceServiceImpl()

        record = PIPLComplianceRecord(
            personal_data_id="pd-minor",
            purpose="Education Service",
            legal_basis=LegalBasis.MINOR_CONSENT.value,
            consent_status=ConsentStatus.NOT_GIVEN,
            accessor="system",
            data_subject_id="user-minor",
            is_minor=True,
            guardian_consent_obtained=False,
        )

        service.record_access(record)

        stored = service.get_record("pd-minor")
        assert stored is not None
        assert stored.validate_minor_consent() is False
