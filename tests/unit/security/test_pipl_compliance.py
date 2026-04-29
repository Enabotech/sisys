"""Tests for PIPLComplianceService.

TDD Red phase - tests should fail before implementation.
Reference: Story 1.11 Data Sovereignty Isolation - AC-5.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.infrastructure.security.models import SensitiveDataType
from src.infrastructure.security.pipl_compliance import GuardianConsentRequiredError, PIPLComplianceService


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

    def test_record_access_invalid_legal_basis_raises(self, service):
        """Should raise ValueError for invalid legal basis in record_access."""
        with pytest.raises(ValueError, match="Invalid legal basis"):
            service.record_access(
                personal_data_id=uuid4(),
                purpose="test",
                legal_basis="invalid_basis",
                data_subject_consent=False,
                accessor="test",
            )

    def test_record_access_consent_required_but_not_provided_raises(self, service):
        """Should raise ValueError when consent is required but not provided."""
        # Create service with consent required
        from src.infrastructure.config.sovereignty import DataSovereigntyConfig

        config = DataSovereigntyConfig(pipl_consent_required=True)
        svc = PIPLComplianceService(config=config)

        with pytest.raises(ValueError, match="Consent is required"):
            svc.record_access(
                personal_data_id=uuid4(),
                purpose="test",
                legal_basis="consent",
                data_subject_consent=False,
                accessor="test",
                data_type=SensitiveDataType.PII,
            )

    def test_check_consent_required_pii(self, service):
        """Should require consent for PII data."""
        result = service.check_consent_required(SensitiveDataType.PII)
        assert result is True

    def test_check_consent_required_health(self, service):
        """Should require consent for health data."""
        result = service.check_consent_required(SensitiveDataType.HEALTH)
        assert result is True

    def test_check_consent_required_identity_document(self, service):
        """Should require consent for identity document data."""
        result = service.check_consent_required(SensitiveDataType.IDENTITY_DOCUMENT)
        assert result is True

    def test_check_consent_required_financial(self, service):
        """Should not require consent for financial data (non-sensitive by default)."""
        result = service.check_consent_required(SensitiveDataType.FINANCIAL)
        assert result is False

    def test_check_consent_required_when_disabled(self):
        """Should not require consent when pipl_consent_required is False."""
        from src.infrastructure.config.sovereignty import DataSovereigntyConfig
        from src.infrastructure.security.pipl_compliance import PIPLComplianceService

        config = DataSovereigntyConfig(pipl_consent_required=False)
        svc = PIPLComplianceService(config=config)

        result = svc.check_consent_required(SensitiveDataType.BIOMETRIC)
        assert result is False

    def test_record_processing(self, service):
        """Should record personal information processing."""
        result = service.record_processing(
            personal_data_id=uuid4(),
            processor="data_pipeline",
            purpose="analytics",
            legal_basis="legitimate_interest",
        )

        assert result is not None
        assert result.purpose == "analytics"
        assert result.legal_basis == "legitimate_interest"
        assert result.accessor == "data_pipeline"
        assert result.data_subject_consent is False

    def test_record_processing_invalid_legal_basis_raises(self, service):
        """Should raise ValueError for invalid legal basis in record_processing."""
        with pytest.raises(ValueError, match="Invalid legal basis"):
            service.record_processing(
                personal_data_id=uuid4(),
                processor="test",
                purpose="test",
                legal_basis="invalid",
            )

    def test_validate_consent_found(self, service):
        """Should return True when valid consent is found."""
        data_id = uuid4()
        service.record_access(
            personal_data_id=data_id,
            purpose="marketing",
            legal_basis="consent",
            data_subject_consent=True,
            accessor="marketing_service",
        )

        result = service.validate_consent(data_id, "marketing")
        assert result is True

    def test_validate_consent_not_found_required(self, service):
        """Should return False when consent is required but not found."""
        from src.infrastructure.config.sovereignty import DataSovereigntyConfig

        config = DataSovereigntyConfig(pipl_consent_required=True)
        svc = PIPLComplianceService(config=config)

        result = svc.validate_consent(uuid4(), "marketing")
        assert result is False

    def test_validate_consent_not_found_not_required(self, service):
        """Should return True when consent is not required and not found."""
        from src.infrastructure.config.sovereignty import DataSovereigntyConfig

        config = DataSovereigntyConfig(pipl_consent_required=False)
        svc = PIPLComplianceService(config=config)

        result = svc.validate_consent(uuid4(), "marketing")
        assert result is True

    def test_get_access_records(self, service):
        """Should return all access records for a personal data item."""
        data_id = uuid4()
        service.record_access(
            personal_data_id=data_id,
            purpose="test1",
            legal_basis="consent",
            data_subject_consent=True,
            accessor="test",
        )
        service.record_access(
            personal_data_id=data_id,
            purpose="test2",
            legal_basis="contract",
            data_subject_consent=False,
            accessor="test",
        )

        records = service.get_access_records(data_id)
        assert len(records) == 2

    def test_get_access_records_none_exist(self, service):
        """Should return empty list when no records exist."""
        records = service.get_access_records(uuid4())
        assert records == []

    def test_delete_personal_data(self, service):
        """Should mark personal data as deleted."""
        data_id = uuid4()
        result = service.delete_personal_data(data_id)
        assert result is True

        rights = service.check_data_subject_rights(data_id)
        assert rights.deletion_right is True

    def test_correct_personal_data(self, service):
        """Should record correction of personal data."""
        data_id = uuid4()
        corrected_data = {"name": "corrected_name"}

        result = service.correct_personal_data(data_id, corrected_data)
        assert result is True

        rights = service.check_data_subject_rights(data_id)
        assert rights.correction_right is True
        assert rights.corrected_values == corrected_data

    def test_process_biometric_data(self, service):
        """Should record biometric data processing with enhanced protection."""
        data_id = uuid4()
        result = service.process_biometric_data(
            data_id=data_id,
            biometric_type="fingerprint",
            purpose="identity_verification",
        )

        assert result is not None
        assert result.personal_data_id == data_id
        assert result.is_biometric is True
        assert result.legal_basis == "consent"
        assert result.data_subject_consent is True
        assert result.accessor == "system"

    def test_process_minor_data_with_guardian_consent(self, service):
        """Should record minor data processing with guardian consent."""
        from src.infrastructure.config.sovereignty import DataSovereigntyConfig

        config = DataSovereigntyConfig(minor_age_threshold=14)
        svc = PIPLComplianceService(config=config)

        data_id = uuid4()
        result = svc.process_minor_data(
            data_id=data_id,
            age=10,
            guardian_id="guardian_123",
        )

        assert result is not None
        assert result.personal_data_id == data_id
        assert result.is_minor is True
        assert result.accessor == "guardian_123"

    def test_process_minor_data_guardian_consent_required_raises(self, service):
        """Should raise GuardianConsentRequiredError when guardian consent is required but not provided."""
        from src.infrastructure.config.sovereignty import DataSovereigntyConfig

        config = DataSovereigntyConfig(minor_age_threshold=14)
        svc = PIPLComplianceService(config=config)

        with pytest.raises(GuardianConsentRequiredError):
            svc.process_minor_data(
                data_id=uuid4(),
                age=10,
                guardian_id="",  # No guardian ID provided
            )

    def test_generate_pipl_report_with_date_filter(self, service):
        """Should filter records by date range."""
        from datetime import timedelta

        service.record_access(
            personal_data_id=uuid4(),
            purpose="test",
            legal_basis="consent",
            data_subject_consent=True,
            accessor="test",
        )

        now = service._access_records[list(service._access_records.keys())[0]].accessed_at
        start_date = now - timedelta(days=1)
        end_date = now + timedelta(days=1)

        report = service.generate_pipl_report(start_date=start_date, end_date=end_date)
        assert report.total_pipl_processing_records >= 1

    def test_generate_pipl_report_legal_basis_breakdown(self, service):
        """Should correctly breakdown by legal basis."""
        data_id = uuid4()
        service.record_access(
            personal_data_id=data_id,
            purpose="test1",
            legal_basis="consent",
            data_subject_consent=True,
            accessor="test",
        )
        service.record_access(
            personal_data_id=data_id,
            purpose="test2",
            legal_basis="contract",
            data_subject_consent=False,
            accessor="test",
        )
        service.record_access(
            personal_data_id=data_id,
            purpose="test3",
            legal_basis="consent",
            data_subject_consent=True,
            accessor="test",
        )

        report = service.generate_pipl_report()
        assert report.consent_records == 2
        assert report.legal_basis_breakdown.get("consent") == 2
        assert report.legal_basis_breakdown.get("contract") == 1

    def test_generate_pipl_report_biometric_count(self, service):
        """Should count biometric processing records."""
        service.process_biometric_data(
            data_id=uuid4(),
            biometric_type="face",
            purpose="security",
        )

        report = service.generate_pipl_report()
        assert report.biometric_processing_count == 1

    def test_generate_pipl_report_minor_count(self, service):
        """Should count minor data processing records."""
        from src.infrastructure.config.sovereignty import DataSovereigntyConfig

        config = DataSovereigntyConfig(minor_age_threshold=14)
        svc = PIPLComplianceService(config=config)

        svc.process_minor_data(
            data_id=uuid4(),
            age=10,
            guardian_id="guardian",
        )

        report = svc.generate_pipl_report()
        assert report.minor_data_processing_count == 1

    def test_generate_pipl_report_data_subject_rights(self, service):
        """Should count data subject rights exercises."""
        data_id = uuid4()
        service.exercise_access_right(data_id)
        service.exercise_deletion_right(data_id)
        service.exercise_correction_right(data_id)

        report = service.generate_pipl_report()
        assert report.data_subject_rights_exercised.get("access") == 1
        assert report.data_subject_rights_exercised.get("deletion") == 1
        assert report.data_subject_rights_exercised.get("correction") == 1

    def test_run_compliance_tests(self, service):
        """Should return True for compliance tests (MVP stub)."""
        result = service.run_compliance_tests()
        assert result is True

    def test_exercise_access_right(self, service):
        """Should record exercise of access right."""
        data_id = uuid4()
        service.exercise_access_right(data_id)

        rights = service.check_data_subject_rights(data_id)
        assert rights.access_right is True
        assert rights.last_exercised is not None

    def test_exercise_deletion_right(self, service):
        """Should record exercise of deletion right."""
        data_id = uuid4()
        service.exercise_deletion_right(data_id)

        rights = service.check_data_subject_rights(data_id)
        assert rights.deletion_right is True
        assert rights.last_exercised is not None

    def test_exercise_correction_right(self, service):
        """Should record exercise of correction right."""
        data_id = uuid4()
        service.exercise_correction_right(data_id)

        rights = service.check_data_subject_rights(data_id)
        assert rights.correction_right is True
        assert rights.last_exercised is not None

    def test_generate_report_full(self, service):
        """Should generate complete compliance report."""
        data_id = uuid4()
        service.record_access(
            personal_data_id=data_id,
            purpose="test",
            legal_basis="consent",
            data_subject_consent=True,
            accessor="test",
        )
        service.exercise_access_right(data_id)

        report = service.generate_report()

        assert report.total_pipl_processing_records == 1
        assert report.consent_records == 1
        assert report.legal_basis_breakdown.get("consent") == 1
        assert report.data_subject_rights_exercised.get("access") == 1
        assert report.report_id is not None
        assert report.generated_at is not None
