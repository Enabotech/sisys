"""Tests for compliance_events module — PIPL, 等保 2.0, data sovereignty."""

from __future__ import annotations

import uuid

import pytest

from src.domain.events.compliance_events import (
    AttackType,
    CrossBorderTransferRequested,
    DataIntegrityViolationEvent,
    DataSovereigntyViolation,
    IntrusionAction,
    IntrusionDetectedEvent,
    IntrusionSeverity,
    MFAChallengeIssuedEvent,
    MFAChallengeStatus,
    MFAChallengeType,
    PIPLDataAccessRequested,
    SensitiveDataDetected,
    SensitiveType,
)


class TestMFAChallengeIssuedEvent:
    """Test MFAChallengeIssuedEvent."""

    def test_create_mfa_challenge_event(self) -> None:
        """Test creating MFA challenge event."""
        event = MFAChallengeIssuedEvent(
            user_id=uuid.uuid4(),
            challenge_type=MFAChallengeType.TOTP,
            status=MFAChallengeStatus.PENDING,
        )
        assert event.event_type == "MFAChallengeIssuedEvent"
        assert event.challenge_type == MFAChallengeType.TOTP
        assert event.status == MFAChallengeStatus.PENDING

    def test_mfa_challenge_with_ip_and_agent(self) -> None:
        """Test MFA challenge with IP and user agent."""
        event = MFAChallengeIssuedEvent(
            user_id=uuid.uuid4(),
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
        )
        assert event.ip_address == "192.168.1.100"
        assert event.user_agent == "Mozilla/5.0"

    def test_mfa_challenge_expired_status(self) -> None:
        """Test MFA challenge with expired status."""
        event = MFAChallengeIssuedEvent(
            user_id=uuid.uuid4(),
            status=MFAChallengeStatus.EXPIRED,
        )
        assert event.status == MFAChallengeStatus.EXPIRED

    def test_mfa_challenge_verified_status(self) -> None:
        """Test MFA challenge with verified status."""
        event = MFAChallengeIssuedEvent(
            user_id=uuid.uuid4(),
            status=MFAChallengeStatus.VERIFIED,
        )
        assert event.status == MFAChallengeStatus.VERIFIED

    def test_mfa_challenge_failed_status(self) -> None:
        """Test MFA challenge with failed status."""
        event = MFAChallengeIssuedEvent(
            user_id=uuid.uuid4(),
            status=MFAChallengeStatus.FAILED,
        )
        assert event.status == MFAChallengeStatus.FAILED

    def test_mfa_challenge_is_frozen(self) -> None:
        """Test MFAChallengeIssuedEvent is frozen."""
        event = MFAChallengeIssuedEvent(user_id=uuid.uuid4())
        with pytest.raises(Exception):
            event.challenge_id = uuid.uuid4()


class TestIntrusionDetectedEvent:
    """Test IntrusionDetectedEvent."""

    def test_create_intrusion_event(self) -> None:
        """Test creating intrusion detection event."""
        event = IntrusionDetectedEvent(
            source_ip="10.0.0.1",
            attack_type=AttackType.BRUTE_FORCE,
            severity=IntrusionSeverity.HIGH,
        )
        assert event.event_type == "IntrusionDetectedEvent"
        assert event.attack_type == AttackType.BRUTE_FORCE
        assert event.severity == IntrusionSeverity.HIGH

    def test_intrusion_with_description(self) -> None:
        """Test intrusion event with description."""
        event = IntrusionDetectedEvent(
            source_ip="192.168.1.50",
            attack_type=AttackType.SQL_INJECTION,
            description="SQL injection attempt detected",
            raw_evidence="'; DROP TABLE users;--",
        )
        assert event.description == "SQL injection attempt detected"
        assert event.raw_evidence == "'; DROP TABLE users;--"

    def test_intrusion_all_severity_levels(self) -> None:
        """Test all intrusion severity levels."""
        for severity in IntrusionSeverity:
            event = IntrusionDetectedEvent(
                source_ip="10.0.0.1",
                severity=severity,
            )
            assert event.severity == severity

    def test_intrusion_all_action_types(self) -> None:
        """Test all intrusion action types."""
        for action in IntrusionAction:
            event = IntrusionDetectedEvent(
                source_ip="10.0.0.1",
                action_taken=action,
            )
            assert event.action_taken == action

    def test_intrusion_all_attack_types(self) -> None:
        """Test all attack types."""
        for attack_type in AttackType:
            event = IntrusionDetectedEvent(
                source_ip="10.0.0.1",
                attack_type=attack_type,
            )
            assert event.attack_type == attack_type


class TestDataIntegrityViolationEvent:
    """Test DataIntegrityViolationEvent."""

    def test_create_integrity_violation_event(self) -> None:
        """Test creating data integrity violation event."""
        event = DataIntegrityViolationEvent(
            data_id=uuid.uuid4(),
            expected_hash="abc123",
            actual_hash="def456",
            source="PostgreSQL/users",
        )
        assert event.event_type == "DataIntegrityViolationEvent"
        assert event.expected_hash == "abc123"
        assert event.actual_hash == "def456"

    def test_integrity_violation_sha512_method(self) -> None:
        """Test integrity violation with SHA512 verification."""
        event = DataIntegrityViolationEvent(
            data_id=uuid.uuid4(),
            verification_method="sha512",
        )
        assert event.verification_method == "sha512"

    def test_integrity_violation_md5_method(self) -> None:
        """Test integrity violation with MD5 verification."""
        event = DataIntegrityViolationEvent(
            data_id=uuid.uuid4(),
            verification_method="md5",
        )
        assert event.verification_method == "md5"


class TestSensitiveDataDetected:
    """Test SensitiveDataDetected event."""

    def test_create_sensitive_data_event(self) -> None:
        """Test creating sensitive data detection event."""
        event = SensitiveDataDetected(
            data_id=uuid.uuid4(),
            sensitive_type=SensitiveType.PII,
            confidence=0.95,
        )
        assert event.event_type == "SensitiveDataDetected"
        assert event.sensitive_type == SensitiveType.PII
        assert event.confidence == 0.95

    def test_sensitive_data_all_types(self) -> None:
        """Test all sensitive data types."""
        for st in SensitiveType:
            event = SensitiveDataDetected(
                data_id=uuid.uuid4(),
                sensitive_type=st,
            )
            assert event.sensitive_type == st

    def test_sensitive_data_with_labels(self) -> None:
        """Test sensitive data with custom labels."""
        event = SensitiveDataDetected(
            data_id=uuid.uuid4(),
            labels=["confidential", "internal"],
            detection_method="nlp",
        )
        assert event.labels == ["confidential", "internal"]
        assert event.detection_method == "nlp"

    def test_sensitive_data_trade_secret(self) -> None:
        """Test sensitive data for trade secret."""
        event = SensitiveDataDetected(
            data_id=uuid.uuid4(),
            sensitive_type=SensitiveType.TRADE_SECRET,
        )
        assert event.sensitive_type == SensitiveType.TRADE_SECRET

    def test_sensitive_data_financial(self) -> None:
        """Test sensitive data for financial."""
        event = SensitiveDataDetected(
            data_id=uuid.uuid4(),
            sensitive_type=SensitiveType.FINANCIAL,
        )
        assert event.sensitive_type == SensitiveType.FINANCIAL

    def test_sensitive_data_biometric(self) -> None:
        """Test sensitive data for biometric (PIPL)."""
        event = SensitiveDataDetected(
            data_id=uuid.uuid4(),
            sensitive_type=SensitiveType.BIOMETRIC,
        )
        assert event.sensitive_type == SensitiveType.BIOMETRIC

    def test_sensitive_data_minor(self) -> None:
        """Test sensitive data for minor (PIPL enhanced protection)."""
        event = SensitiveDataDetected(
            data_id=uuid.uuid4(),
            sensitive_type=SensitiveType.MINOR,
        )
        assert event.sensitive_type == SensitiveType.MINOR

    def test_sensitive_data_custom(self) -> None:
        """Test sensitive data with custom type."""
        event = SensitiveDataDetected(
            data_id=uuid.uuid4(),
            sensitive_type=SensitiveType.CUSTOM,
        )
        assert event.sensitive_type == SensitiveType.CUSTOM


class TestCrossBorderTransferRequested:
    """Test CrossBorderTransferRequested event."""

    def test_create_transfer_request(self) -> None:
        """Test creating cross-border transfer request."""
        event = CrossBorderTransferRequested(
            data_id=uuid.uuid4(),
            destination="US",
            purpose="cloud_storage",
        )
        assert event.event_type == "CrossBorderTransferRequested"
        assert event.destination == "US"
        assert event.status == "pending"

    def test_transfer_approved_status(self) -> None:
        """Test transfer with approved status."""
        event = CrossBorderTransferRequested(
            data_id=uuid.uuid4(),
            status="approved",
        )
        assert event.status == "approved"

    def test_transfer_rejected_status(self) -> None:
        """Test transfer with rejected status."""
        event = CrossBorderTransferRequested(
            data_id=uuid.uuid4(),
            status="rejected",
        )
        assert event.status == "rejected"

    def test_transfer_blocked_status(self) -> None:
        """Test transfer with blocked status."""
        event = CrossBorderTransferRequested(
            data_id=uuid.uuid4(),
            status="blocked",
        )
        assert event.status == "blocked"

    def test_transfer_with_approval_id(self) -> None:
        """Test transfer with approval workflow ID."""
        approval_id = uuid.uuid4()
        event = CrossBorderTransferRequested(
            data_id=uuid.uuid4(),
            approval_id=approval_id,
        )
        assert event.approval_id == approval_id


class TestDataSovereigntyViolation:
    """Test DataSovereigntyViolation event."""

    def test_create_sovereignty_violation(self) -> None:
        """Test creating data sovereignty violation event."""
        event = DataSovereigntyViolation(
            violation_id=uuid.uuid4(),
            data_id=uuid.uuid4(),
            violation_type="unauthorized_transfer",
            severity="critical",
        )
        assert event.event_type == "DataSovereigntyViolation"
        assert event.violation_type == "unauthorized_transfer"
        assert event.severity == "critical"

    def test_violation_all_severity_levels(self) -> None:
        """Test all severity levels."""
        for severity in ["low", "medium", "high", "critical"]:
            event = DataSovereigntyViolation(
                violation_id=uuid.uuid4(),
                severity=severity,
            )
            assert event.severity == severity


class TestPIPLDataAccessRequested:
    """Test PIPLDataAccessRequested event."""

    def test_create_pipl_access_request(self) -> None:
        """Test creating PIPL data access request."""
        event = PIPLDataAccessRequested(
            personal_data_id=uuid.uuid4(),
            purpose="marketing",
            legal_basis="consent",
            data_subject_consent=True,
        )
        assert event.event_type == "PIPLDataAccessRequested"
        assert event.purpose == "marketing"
        assert event.legal_basis == "consent"
        assert event.data_subject_consent is True

    def test_pipl_all_legal_bases(self) -> None:
        """Test all legal bases."""
        for legal_basis in ["consent", "contract", "legal_obligation", "vital_interest", "public_task"]:
            event = PIPLDataAccessRequested(
                personal_data_id=uuid.uuid4(),
                legal_basis=legal_basis,
            )
            assert event.legal_basis == legal_basis

    def test_pipl_without_consent(self) -> None:
        """Test PIPL access without data subject consent."""
        event = PIPLDataAccessRequested(
            personal_data_id=uuid.uuid4(),
            data_subject_consent=False,
            legal_basis="legal_obligation",
        )
        assert event.data_subject_consent is False

    def test_pipl_with_accessor(self) -> None:
        """Test PIPL access with accessor info."""
        event = PIPLDataAccessRequested(
            personal_data_id=uuid.uuid4(),
            accessor="admin@company.com",
        )
        assert event.accessor == "admin@company.com"
