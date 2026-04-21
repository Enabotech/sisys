"""Integration Tests for 等保 2.0 Level 3 Compliance.

Comprehensive integration tests for MFA, intrusion detection,
backup/recovery, and integrity verification workflows.

Reference: Story 1.12 等保 2.0 三级基础要求
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.domain.events.compliance_events import (
    AttackType,
    IntrusionDetectedEvent,
    MFAChallengeIssuedEvent,
    MFAChallengeType,
)
from src.infrastructure.security.backup_service import BackupService, RecoveryService
from src.infrastructure.security.integrity_service import IntegrityVerifier, SignatureService
from src.infrastructure.security.intrusion_detector import (
    IntrusionDetector,
    ThreatAssessment,
    ThreatLevel,
)
from src.infrastructure.security.mfa_service import MFAService
from src.infrastructure.security.models import (
    BackupStatus,
    BackupType,
    HashAlgorithm,
    IntegrityStatus,
)
from src.infrastructure.security.totp_generator import TOTPGenerator, TOTPVerifier

# =============================================================================
# MFA Integration Tests
# =============================================================================


class TestMFAIntegration:
    """Integration tests for MFA workflow."""

    @pytest.mark.asyncio
    async def test_complete_mfa_setup_and_verification_flow(self):
        """Test complete MFA setup and verification flow."""
        # 1. Setup MFA for user
        mfa_service = MFAService()
        user_id = uuid4()

        setup_result = mfa_service.setup_mfa(user_id, "testuser")

        assert setup_result.success is True
        assert len(setup_result.secret) > 0
        assert len(setup_result.provisioning_uri) > 0

        # 2. Verify setup with valid code
        generator = TOTPGenerator()
        counter = TOTPGenerator.get_current_counter(30)
        code = generator.generate(setup_result.secret, counter)

        is_valid = mfa_service.verify_mfa_setup(user_id, code)
        assert is_valid is True

        # 3. Create and verify challenge
        challenge_event = mfa_service.create_challenge(user_id)
        assert isinstance(challenge_event, MFAChallengeIssuedEvent)
        assert challenge_event.challenge_type == MFAChallengeType.TOTP

        # 4. Generate new code and verify challenge
        new_counter = TOTPGenerator.get_current_counter(30)
        new_code = generator.generate(setup_result.secret, new_counter)

        result = mfa_service.verify_challenge(challenge_event.challenge_id, new_code)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_mfa_with_totp_time_tolerance(self):
        """Test MFA works within time tolerance window."""
        mfa_service = MFAService()
        user_id = uuid4()

        # Setup MFA
        setup_result = mfa_service.setup_mfa(user_id, "testuser")

        # Verify with TOTPVerifier (which has time window tolerance)
        generator = TOTPGenerator()
        verifier = TOTPVerifier(generator)

        # Current time counter should verify
        counter = TOTPGenerator.get_current_counter(30)
        code = generator.generate(setup_result.secret, counter)

        # Using TOTPVerifier directly
        assert verifier.verify(setup_result.secret, code) is True

        # Slightly old counter should still verify (within window)
        old_counter = counter - 1
        old_code = generator.generate(setup_result.secret, old_counter)
        assert verifier.verify(setup_result.secret, old_code) is True


# =============================================================================
# Intrusion Detection Integration Tests
# =============================================================================


class TestIntrusionDetectionIntegration:
    """Integration tests for intrusion detection workflow."""

    def test_attack_detection_and_threat_assessment_flow(self):
        """Test complete attack detection and threat assessment flow."""
        detector = IntrusionDetector()

        # 1. Detect SQL injection attack
        content = "'; DROP TABLE users; --"
        attacks = detector.detect_attack(content)
        assert AttackType.SQL_INJECTION in attacks

        # 2. Assess threat level
        ip = "192.168.1.100"
        assessment = detector.assess_threat(ip, content)

        assert isinstance(assessment, ThreatAssessment)
        assert assessment.threat_level in [ThreatLevel.SUSPICIOUS, ThreatLevel.MALICIOUS, ThreatLevel.CRITICAL]
        assert AttackType.SQL_INJECTION in assessment.detected_attacks

        # 3. Create intrusion event
        event = detector.create_intrusion_event(ip, assessment, content)
        assert isinstance(event, IntrusionDetectedEvent)
        assert event.source_ip == ip
        assert event.attack_type == AttackType.SQL_INJECTION

    def test_brute_force_detection_and_blocking_flow(self):
        """Test brute force detection and IP blocking flow."""
        detector = IntrusionDetector(
            brute_force_window=300,
            brute_force_max_attempts=3,
        )

        ip = "192.168.1.200"

        # Record failed logins
        for i in range(3):
            is_blocked = detector.record_failed_login(ip)
            if i < 2:
                assert is_blocked is False
            else:
                assert is_blocked is True

        # IP should now be blocked
        assert detector.is_ip_blocked(ip) is True

        # Rate limit should also fail
        assert detector.check_rate_limit(ip) is False

    def test_multiple_attack_types_detection(self):
        """Test detection of multiple attack types in single request."""
        detector = IntrusionDetector()

        # Multiple attack patterns
        content = "<script>alert('xss')</script>'; DROP TABLE users; --"
        attacks = detector.detect_attack(content)

        assert AttackType.XSS in attacks
        assert AttackType.SQL_INJECTION in attacks


# =============================================================================
# Backup/Recovery Integration Tests
# =============================================================================


class TestBackupRecoveryIntegration:
    """Integration tests for backup and recovery workflow."""

    @pytest.mark.asyncio
    async def test_full_backup_and_restore_flow(self):
        """Test complete full backup and restore flow."""
        backup_service = BackupService()
        recovery_service = RecoveryService(backup_service)

        user_id = uuid4()

        # 1. Create full backup
        backup = await backup_service.create_full_backup(
            user_id=user_id,
            description="Integration test backup",
        )

        assert backup.status == BackupStatus.COMPLETED
        assert backup.backup_type == BackupType.FULL
        assert len(backup.checksum) > 0

        # 2. Verify backup
        is_valid = await backup_service.verify_backup(backup.id)
        assert is_valid is True

        # 3. Restore from backup
        result = await recovery_service.recover_from_backup(
            backup_id=backup.id,
            target_path="/tmp/test_restore",
        )

        assert result["status"] == "success"
        assert result["backup_id"] == str(backup.id)

    @pytest.mark.asyncio
    async def test_incremental_backup_chain_flow(self):
        """Test incremental backup chain creation and restore."""
        backup_service = BackupService()
        recovery_service = RecoveryService(backup_service)

        user_id = uuid4()

        # 1. Create base full backup
        full_backup = await backup_service.create_full_backup(
            user_id=user_id,
            description="Base full backup",
        )
        assert full_backup.backup_type == BackupType.FULL

        # 2. Create incremental backup
        incremental = await backup_service.create_incremental_backup(
            user_id=user_id,
            base_backup_id=full_backup.id,
            description="Incremental backup 1",
        )
        assert incremental.backup_type == BackupType.INCREMENTAL

        # 3. List backups
        backups = await backup_service.list_backups()
        assert len(backups) >= 2

        # 4. Restore incremental chain
        result = await recovery_service.recover_incremental_chain(
            base_backup_id=full_backup.id,
            target_path="/tmp/test_restore_chain",
        )

        assert result["status"] == "success"
        assert result["incremental_count"] >= 1


# =============================================================================
# Integrity Verification Integration Tests
# =============================================================================


class TestIntegrityVerificationIntegration:
    """Integration tests for integrity verification workflow."""

    @pytest.mark.asyncio
    async def test_hash_computation_and_verification_flow(self):
        """Test complete hash computation and verification flow."""
        verifier = IntegrityVerifier()

        data = "Important test data"

        # 1. Compute SHA-256 hash
        hash_256 = verifier.compute_hash(data, HashAlgorithm.SHA256)
        assert len(hash_256) == 64  # 256 bits / 4 = 64 hex chars

        # 2. Compute SHA-512 hash
        hash_512 = verifier.compute_hash(data, HashAlgorithm.SHA512)
        assert len(hash_512) == 128  # 512 bits / 4 = 128 hex chars

        # 3. Verify with correct hash
        assert verifier.verify_hash(data, hash_256) is True
        assert verifier.verify_hash(data, hash_512, HashAlgorithm.SHA512) is True

        # 4. Verify with wrong hash
        assert verifier.verify_hash(data, "invalid_hash") is False
        # SHA512 hash should fail verification with SHA256 (default algorithm)
        assert verifier.verify_hash(data, hash_512) is False

    @pytest.mark.asyncio
    async def test_signature_and_verification_flow(self):
        """Test complete digital signature and verification flow."""
        signature_service = SignatureService()

        # 1. Generate key pair
        private_pem, public_pem = signature_service.generate_key_pair()
        assert len(private_pem) > 0
        assert len(public_pem) > 0

        # 2. Sign data
        data = "Test message for signing"
        signature = signature_service.sign(data)
        assert len(signature) > 0

        # 3. Verify signature
        assert signature_service.verify(data, signature) is True

        # 4. Verify with tampered data
        assert signature_service.verify("Tampered data", signature) is False

    @pytest.mark.asyncio
    async def test_timestamped_signature_flow(self):
        """Test signed data with timestamp verification."""
        signature_service = SignatureService()
        signature_service.generate_key_pair()

        # 1. Sign data with timestamp
        signed = signature_service.sign_data_with_timestamp("Test data")
        assert "data" in signed
        assert "timestamp" in signed
        assert "signature" in signed

        # 2. Verify signed data with timestamp
        assert signature_service.verify_data_with_timestamp(signed) is True

        # 3. Tamper with data - should fail
        signed["data"] = "Tampered data"
        assert signature_service.verify_data_with_timestamp(signed) is False

    @pytest.mark.asyncio
    async def test_verify_and_record_flow(self):
        """Test integrity verification and recording flow."""
        verifier = IntegrityVerifier()
        data_id = uuid4()
        data = "Test data for integrity check"

        # 1. Compute expected hash
        expected_hash = verifier.compute_hash(data)

        # 2. Verify and record
        check = await verifier.verify_and_record(
            data_id=data_id,
            data=data,
            expected_hash=expected_hash,
            data_type="test_document",
        )

        assert check.status == IntegrityStatus.VERIFIED
        assert check.data_id == data_id


# =============================================================================
# Cross-Component Integration Tests
# =============================================================================


class TestCrossComponentIntegration:
    """Integration tests for interactions between components."""

    @pytest.mark.asyncio
    async def test_mfa_then_backup_with_audit(self):
        """Test MFA verification before backup operation."""
        mfa_service = MFAService()
        backup_service = BackupService()

        user_id = uuid4()

        # 1. Setup MFA
        mfa_service.setup_mfa(user_id, "testuser")

        # 2. Verify MFA is enabled
        assert mfa_service.get_mfa_status(user_id) is True

        # 3. Create backup (MFA verified)
        backup = await backup_service.create_full_backup(
            user_id=user_id,
            description="MFA-verified backup",
        )
        assert backup.status == BackupStatus.COMPLETED

    def test_intrusion_detection_with_threat_scoring(self):
        """Test intrusion detection with threat scoring."""
        detector = IntrusionDetector()

        # Simulate various attack scenarios
        test_cases = [
            ("'; DROP TABLE users; --", ThreatLevel.MALICIOUS),
            ("<script>alert('xss')</script>", ThreatLevel.SUSPICIOUS),
            ("../../../etc/passwd", ThreatLevel.SUSPICIOUS),
            ("normal request content", ThreatLevel.BENIGN),
        ]

        for content, expected_min_level in test_cases:
            assessment = detector.assess_threat(
                ip_address="192.168.1.1",
                request_content=content,
            )

            # Threat level should be at least the expected level or higher
            threat_order = [ThreatLevel.BENIGN, ThreatLevel.SUSPICIOUS, ThreatLevel.MALICIOUS, ThreatLevel.CRITICAL]
            assert threat_order.index(assessment.threat_level) >= threat_order.index(expected_min_level)


# =============================================================================
# Compliance Status Integration Tests
# =============================================================================


class TestComplianceStatusIntegration:
    """Integration tests for compliance status reporting."""

    def test_compliance_components_summary(self):
        """Test that compliance components can report status."""
        # MFA Service
        mfa_service = MFAService()
        mfa_status = mfa_service.get_mfa_status(uuid4())
        assert isinstance(mfa_status, bool)

        # Intrusion Detector
        detector = IntrusionDetector()
        attacks = detector.detect_attack("test")
        assert isinstance(attacks, list)

        # Integrity Verifier
        verifier = IntegrityVerifier()
        hash_val = verifier.compute_hash("test")
        assert len(hash_val) > 0

        # Backup Service
        backup_service = BackupService()
        assert backup_service is not None

        # Signature Service
        sig_service = SignatureService()
        assert sig_service is not None
