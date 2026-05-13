"""Tests for PIPLComplianceRecord domain entity.

TDD Red Phase: These tests define expected behavior before implementation.
"""

from datetime import UTC

import pytest


class TestPIPLComplianceRecordCreation:
    """Test PIPLComplianceRecord entity creation."""

    def test_create_with_required_fields(self):
        """Test creating PIPLComplianceRecord with required fields."""
        from src.domain.entities.pipl_compliance_record import PIPLComplianceRecord

        record = PIPLComplianceRecord(
            personal_data_id="pd-123",
            purpose="User Authentication",
            legal_basis="consent",
            accessor="system",
            data_subject_id="user-456",
        )

        assert record.personal_data_id == "pd-123"
        assert record.purpose == "User Authentication"
        assert record.legal_basis == "consent"
        assert record.accessor == "system"
        assert record.data_subject_id == "user-456"
        assert record.access_id is not None
        assert record.consent_status.value == "not_given"

    def test_create_with_all_fields(self):
        """Test creating PIPLComplianceRecord with all fields."""
        import uuid
        from datetime import datetime

        from src.domain.entities.pipl_compliance_record import (
            ConsentStatus,
            LegalBasis,
            PIPLComplianceRecord,
        )

        custom_id = uuid.uuid4()
        now = datetime.now(UTC)

        record = PIPLComplianceRecord(
            access_id=custom_id,
            personal_data_id="pd-789",
            purpose="Analytics",
            legal_basis=LegalBasis.CONTRACT.value,
            consent_status=ConsentStatus.GIVEN,
            accessor="admin-001",
            accessed_at=now,
            data_subject_id="user-789",
        )

        assert record.access_id == custom_id
        assert record.consent_status == ConsentStatus.GIVEN
        assert record.legal_basis == LegalBasis.CONTRACT.value


class TestPIPLComplianceRecordMethods:
    """Test PIPLComplianceRecord business methods."""

    def test_validate_consent_given(self):
        """Test validate_consent returns True when consent is given."""
        from src.domain.entities.pipl_compliance_record import (
            ConsentStatus,
            PIPLComplianceRecord,
        )

        record = PIPLComplianceRecord(
            personal_data_id="pd-123",
            purpose="Test",
            legal_basis="consent",
            consent_status=ConsentStatus.GIVEN,
            accessor="system",
            data_subject_id="user-456",
        )

        assert record.validate_consent() is True

    def test_validate_consent_withdrawn(self):
        """Test validate_consent returns False when consent is withdrawn."""
        from src.domain.entities.pipl_compliance_record import (
            ConsentStatus,
            PIPLComplianceRecord,
        )

        record = PIPLComplianceRecord(
            personal_data_id="pd-123",
            purpose="Test",
            legal_basis="consent",
            consent_status=ConsentStatus.WITHDRAWN,
            accessor="system",
            data_subject_id="user-456",
        )

        assert record.validate_consent() is False

    def test_is_compliant_consent_basis(self):
        """Test is_compliant returns True for consent basis with valid consent."""
        from src.domain.entities.pipl_compliance_record import (
            ConsentStatus,
            PIPLComplianceRecord,
        )

        record = PIPLComplianceRecord(
            personal_data_id="pd-123",
            purpose="Test",
            legal_basis="consent",
            consent_status=ConsentStatus.GIVEN,
            accessor="system",
            data_subject_id="user-456",
        )

        assert record.is_compliant() is True

    def test_is_compliant_non_consent_basis(self):
        """Test is_compliant returns True for non-consent legal basis."""
        from src.domain.entities.pipl_compliance_record import (
            LegalBasis,
            PIPLComplianceRecord,
        )

        record = PIPLComplianceRecord(
            personal_data_id="pd-123",
            purpose="Legal Compliance",
            legal_basis=LegalBasis.LEGAL_OBLIGATION.value,
            accessor="system",
            data_subject_id="user-456",
        )

        assert record.is_compliant() is True

    def test_validate_minor_consent_not_minor(self):
        """Test validate_minor_consent returns True for adult."""
        from src.domain.entities.pipl_compliance_record import PIPLComplianceRecord

        record = PIPLComplianceRecord(
            personal_data_id="pd-123",
            purpose="Test",
            legal_basis="minor_consent",
            accessor="system",
            data_subject_id="user-456",
            is_minor=False,
        )

        assert record.validate_minor_consent() is True

    def test_validate_minor_consent_minor_with_consent(self):
        """Test validate_minor_consent returns True for minor with guardian consent."""
        from src.domain.entities.pipl_compliance_record import (
            ConsentStatus,
            PIPLComplianceRecord,
        )

        record = PIPLComplianceRecord(
            personal_data_id="pd-123",
            purpose="Test",
            legal_basis="minor_consent",
            consent_status=ConsentStatus.GIVEN,
            accessor="system",
            data_subject_id="user-minor",
            is_minor=True,
            guardian_consent_obtained=True,
        )

        assert record.validate_minor_consent() is True

    def test_validate_minor_consent_minor_without_consent(self):
        """Test validate_minor_consent returns False for minor without guardian consent."""
        from src.domain.entities.pipl_compliance_record import (
            ConsentStatus,
            PIPLComplianceRecord,
        )

        record = PIPLComplianceRecord(
            personal_data_id="pd-123",
            purpose="Test",
            legal_basis="minor_consent",
            consent_status=ConsentStatus.NOT_GIVEN,
            accessor="system",
            data_subject_id="user-minor",
            is_minor=True,
            guardian_consent_obtained=False,
        )

        assert record.validate_minor_consent() is False


class TestPIPLComplianceRecordImmutability:
    """Test that PIPLComplianceRecord is immutable."""

    def test_is_frozen_dataclass(self):
        """Test PIPLComplianceRecord is a frozen dataclass."""
        from src.domain.entities.pipl_compliance_record import PIPLComplianceRecord

        record = PIPLComplianceRecord()
        with pytest.raises(AttributeError):
            record.purpose = "Modified"

    def test_access_id_not_modifiable(self):
        """Test access_id cannot be modified after creation."""
        from src.domain.entities.pipl_compliance_record import PIPLComplianceRecord

        record = PIPLComplianceRecord()
        with pytest.raises(AttributeError):
            record.access_id = None
