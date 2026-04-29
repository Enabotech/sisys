"""Tests for 等保 2.0 Level 3 Configuration.

Comprehensive tests for compliance configuration dataclasses and
singleton getter functions.

Reference: Story 1.12 等保 2.0 三级基础要求
"""

from __future__ import annotations

from src.infrastructure.config.equilibrium import (
    BackupRecoveryConfig,
    ComplianceReportingConfig,
    IntegrityVerificationConfig,
    IntrusionDetectionConfig,
    MFAConfig,
    get_backup_recovery_config,
    get_compliance_reporting_config,
    get_integrity_verification_config,
    get_intrusion_detection_config,
    get_mfa_config,
)

# =============================================================================
# MFAConfig Tests
# =============================================================================


class TestMFAConfig:
    """Tests for MFAConfig dataclass."""

    def test_totp_digits_default(self):
        """TOTP should default to 6 digits."""
        config = MFAConfig()
        assert config.TOTP_DIGITS == 6

    def test_totp_period_seconds_default(self):
        """TOTP period should default to 30 seconds."""
        config = MFAConfig()
        assert config.TOTP_PERIOD_SECONDS == 30

    def test_totp_issuer_default(self):
        """TOTP issuer should default to SISYS."""
        config = MFAConfig()
        assert config.TOTP_ISSUER == "SISYS"

    def test_challenge_ttl_minutes_default(self):
        """Challenge TTL should default to 5 minutes."""
        config = MFAConfig()
        assert config.CHALLENGE_TTL_MINUTES == 5

    def test_max_verification_attempts_default(self):
        """Max verification attempts should default to 3."""
        config = MFAConfig()
        assert config.MAX_VERIFICATION_ATTEMPTS == 3

    def test_mfa_coverage_target_default(self):
        """MFA coverage target should be 100%."""
        config = MFAConfig()
        assert config.MFA_COVERAGE_TARGET == 100.0

    def test_custom_values(self):
        """Should accept custom values."""
        config = MFAConfig(
            TOTP_DIGITS=8,
            TOTP_PERIOD_SECONDS=60,
            TOTP_ISSUER="CUSTOM",
            CHALLENGE_TTL_MINUTES=10,
            MAX_VERIFICATION_ATTEMPTS=5,
            MFA_COVERAGE_TARGET=95.0,
        )
        assert config.TOTP_DIGITS == 8
        assert config.TOTP_PERIOD_SECONDS == 60
        assert config.TOTP_ISSUER == "CUSTOM"
        assert config.CHALLENGE_TTL_MINUTES == 10
        assert config.MAX_VERIFICATION_ATTEMPTS == 5
        assert config.MFA_COVERAGE_TARGET == 95.0


# =============================================================================
# IntrusionDetectionConfig Tests
# =============================================================================


class TestIntrusionDetectionConfig:
    """Tests for IntrusionDetectionConfig dataclass."""

    def test_rate_limit_defaults(self):
        """Rate limit should have sensible defaults."""
        config = IntrusionDetectionConfig()
        assert config.RATE_LIMIT_WINDOW_SECONDS == 60
        assert config.RATE_LIMIT_MAX_REQUESTS == 100

    def test_brute_force_defaults(self):
        """Brute force detection should have sensible defaults."""
        config = IntrusionDetectionConfig()
        assert config.BRUTE_FORCE_WINDOW_SECONDS == 300
        assert config.BRUTE_FORCE_MAX_ATTEMPTS == 5
        assert config.BRUTE_FORCE_BLOCK_DURATION_SECONDS == 300

    def test_threat_level_thresholds(self):
        """Threat level thresholds should be in ascending order."""
        config = IntrusionDetectionConfig()
        assert config.THREAT_LEVEL_BENIGN == 0.0
        assert config.THREAT_LEVEL_SUSPICIOUS == 30.0
        assert config.THREAT_LEVEL_MALICIOUS == 60.0
        assert config.THREAT_LEVEL_CRITICAL == 80.0

    def test_attack_severity_scores(self):
        """Attack severity scores should be defined."""
        config = IntrusionDetectionConfig()
        assert config.SCORE_SQL_INJECTION == 40.0
        assert config.SCORE_XSS == 30.0
        assert config.SCORE_COMMAND_INJECTION == 50.0
        assert config.SCORE_PATH_TRAVERSAL == 30.0
        assert config.SCORE_PROMPT_INJECTION == 35.0
        assert config.SCORE_CSRF == 20.0
        assert config.SCORE_DATA_EXFILTRATION == 45.0
        assert config.SCORE_RATE_LIMIT_VIOLATION == 30.0
        assert config.SCORE_BRUTE_FORCE == 50.0

    def test_coverage_requirements(self):
        """Coverage requirements should match 等保 2.0 Level 3."""
        config = IntrusionDetectionConfig()
        assert config.PENETRATION_TEST_COVERAGE_TARGET == 90.0
        assert config.HIGH_RISK_COUNT_TARGET == 0
        assert config.MEDIUM_RISK_COUNT_TARGET == 5

    def test_custom_values(self):
        """Should accept custom values."""
        config = IntrusionDetectionConfig(
            RATE_LIMIT_WINDOW_SECONDS=120,
            RATE_LIMIT_MAX_REQUESTS=200,
            BRUTE_FORCE_WINDOW_SECONDS=600,
            BRUTE_FORCE_MAX_ATTEMPTS=10,
            THREAT_LEVEL_CRITICAL=90.0,
        )
        assert config.RATE_LIMIT_WINDOW_SECONDS == 120
        assert config.RATE_LIMIT_MAX_REQUESTS == 200
        assert config.BRUTE_FORCE_WINDOW_SECONDS == 600
        assert config.BRUTE_FORCE_MAX_ATTEMPTS == 10
        assert config.THREAT_LEVEL_CRITICAL == 90.0


# =============================================================================
# BackupRecoveryConfig Tests
# =============================================================================


class TestBackupRecoveryConfig:
    """Tests for BackupRecoveryConfig dataclass."""

    def test_storage_path_default(self):
        """Storage path should have default."""
        config = BackupRecoveryConfig()
        assert config.STORAGE_PATH == "/var/sisys/backups"

    def test_backup_schedule_defaults(self):
        """Backup schedules should have defaults."""
        config = BackupRecoveryConfig()
        assert config.FULL_BACKUP_SCHEDULE == "daily"
        assert config.INCREMENTAL_BACKUP_SCHEDULE == "hourly"

    def test_recovery_settings(self):
        """Recovery settings should have sensible defaults."""
        config = BackupRecoveryConfig()
        assert config.MAX_RECOVERY_TIME_MINUTES == 60
        assert config.ESTIMATED_RECOVERY_SPEED_MBPS == 10.0

    def test_retention_defaults(self):
        """Retention periods should have defaults."""
        config = BackupRecoveryConfig()
        assert config.FULL_BACKUP_RETENTION_DAYS == 30
        assert config.INCREMENTAL_BACKUP_RETENTION_DAYS == 7

    def test_coverage_requirements(self):
        """Coverage requirements should be defined."""
        config = BackupRecoveryConfig()
        assert config.BACKUP_COVERAGE_TARGET == 100.0
        assert config.RECOVERY_TIME_TARGET_MINUTES == 60

    def test_custom_values(self):
        """Should accept custom values."""
        config = BackupRecoveryConfig(
            STORAGE_PATH="/custom/path",
            FULL_BACKUP_SCHEDULE="weekly",
            INCREMENTAL_BACKUP_SCHEDULE="daily",
            MAX_RECOVERY_TIME_MINUTES=30,
            FULL_BACKUP_RETENTION_DAYS=60,
        )
        assert config.STORAGE_PATH == "/custom/path"
        assert config.FULL_BACKUP_SCHEDULE == "weekly"
        assert config.INCREMENTAL_BACKUP_SCHEDULE == "daily"
        assert config.MAX_RECOVERY_TIME_MINUTES == 30
        assert config.FULL_BACKUP_RETENTION_DAYS == 60


# =============================================================================
# IntegrityVerificationConfig Tests
# =============================================================================


class TestIntegrityVerificationConfig:
    """Tests for IntegrityVerificationConfig dataclass."""

    def test_default_hash_algorithm(self):
        """Default hash algorithm should be SHA256."""
        config = IntegrityVerificationConfig()
        assert config.DEFAULT_HASH_ALGORITHM == "SHA256"

    def test_supported_algorithms_default(self):
        """Supported algorithms should include common hashes."""
        config = IntegrityVerificationConfig()
        assert "SHA256" in config.SUPPORTED_ALGORITHMS
        assert "SHA512" in config.SUPPORTED_ALGORITHMS
        assert "MD5" in config.SUPPORTED_ALGORITHMS

    def test_signature_settings(self):
        """Signature settings should have defaults."""
        config = IntegrityVerificationConfig()
        assert config.RSA_KEY_SIZE_BITS == 2048
        assert config.SIGNATURE_ALGORITHM == "RSASSA-PKCS1-v1_5-SHA256"

    def test_coverage_requirements(self):
        """Coverage requirements should be 100%."""
        config = IntegrityVerificationConfig()
        assert config.ENCRYPTION_COVERAGE_TARGET == 100.0
        assert config.INTEGRITY_CHECK_COVERAGE_TARGET == 100.0

    def test_custom_values(self):
        """Should accept custom values."""
        config = IntegrityVerificationConfig(
            DEFAULT_HASH_ALGORITHM="SHA512",
            SUPPORTED_ALGORITHMS=["SHA512", "SHA256"],
            RSA_KEY_SIZE_BITS=4096,
        )
        assert config.DEFAULT_HASH_ALGORITHM == "SHA512"
        assert config.SUPPORTED_ALGORITHMS == ["SHA512", "SHA256"]
        assert config.RSA_KEY_SIZE_BITS == 4096


# =============================================================================
# ComplianceReportingConfig Tests
# =============================================================================


class TestComplianceReportingConfig:
    """Tests for ComplianceReportingConfig dataclass."""

    def test_report_generation_schedule_default(self):
        """Report generation schedule should default to weekly."""
        config = ComplianceReportingConfig()
        assert config.REPORT_GENERATION_SCHEDULE == "weekly"

    def test_report_formats_default(self):
        """Report formats should include common formats."""
        config = ComplianceReportingConfig()
        assert "pdf" in config.REPORT_FORMATS
        assert "html" in config.REPORT_FORMATS
        assert "json" in config.REPORT_FORMATS

    def test_audit_log_integrity_target(self):
        """Audit log integrity target should be 100%."""
        config = ComplianceReportingConfig()
        assert config.AUDIT_LOG_INTEGRITY_TARGET == 100.0

    def test_rbac_coverage_target(self):
        """RBAC coverage target should be 100%."""
        config = ComplianceReportingConfig()
        assert config.RBAC_COVERAGE_TARGET == 100.0

    def test_default_compliance_level(self):
        """Default compliance level should be 3 (等保 2.0 Level 3)."""
        config = ComplianceReportingConfig()
        assert config.DEFAULT_COMPLIANCE_LEVEL == 3

    def test_custom_values(self):
        """Should accept custom values."""
        config = ComplianceReportingConfig(
            REPORT_GENERATION_SCHEDULE="daily",
            REPORT_FORMATS=["json", "xml"],
            AUDIT_LOG_INTEGRITY_TARGET=95.0,
            RBAC_COVERAGE_TARGET=90.0,
            DEFAULT_COMPLIANCE_LEVEL=2,
        )
        assert config.REPORT_GENERATION_SCHEDULE == "daily"
        assert config.REPORT_FORMATS == ["json", "xml"]
        assert config.AUDIT_LOG_INTEGRITY_TARGET == 95.0
        assert config.RBAC_COVERAGE_TARGET == 90.0
        assert config.DEFAULT_COMPLIANCE_LEVEL == 2


# =============================================================================
# Singleton Getter Tests
# =============================================================================


class TestConfigGetters:
    """Tests for configuration singleton getters."""

    def test_get_mfa_config_returns_mfa_config(self):
        """Should return MFAConfig instance."""
        config = get_mfa_config()
        assert isinstance(config, MFAConfig)

    def test_get_mfa_config_singleton(self):
        """Should return same instance on multiple calls."""
        config1 = get_mfa_config()
        config2 = get_mfa_config()
        assert config1 is config2

    def test_get_intrusion_detection_config_returns_config(self):
        """Should return IntrusionDetectionConfig instance."""
        config = get_intrusion_detection_config()
        assert isinstance(config, IntrusionDetectionConfig)

    def test_get_intrusion_detection_config_singleton(self):
        """Should return same instance on multiple calls."""
        config1 = get_intrusion_detection_config()
        config2 = get_intrusion_detection_config()
        assert config1 is config2

    def test_get_backup_recovery_config_returns_config(self):
        """Should return BackupRecoveryConfig instance."""
        config = get_backup_recovery_config()
        assert isinstance(config, BackupRecoveryConfig)

    def test_get_backup_recovery_config_singleton(self):
        """Should return same instance on multiple calls."""
        config1 = get_backup_recovery_config()
        config2 = get_backup_recovery_config()
        assert config1 is config2

    def test_get_integrity_verification_config_returns_config(self):
        """Should return IntegrityVerificationConfig instance."""
        config = get_integrity_verification_config()
        assert isinstance(config, IntegrityVerificationConfig)

    def test_get_integrity_verification_config_singleton(self):
        """Should return same instance on multiple calls."""
        config1 = get_integrity_verification_config()
        config2 = get_integrity_verification_config()
        assert config1 is config2

    def test_get_compliance_reporting_config_returns_config(self):
        """Should return ComplianceReportingConfig instance."""
        config = get_compliance_reporting_config()
        assert isinstance(config, ComplianceReportingConfig)

    def test_get_compliance_reporting_config_singleton(self):
        """Should return same instance on multiple calls."""
        config1 = get_compliance_reporting_config()
        config2 = get_compliance_reporting_config()
        assert config1 is config2


# =============================================================================
# Cross-Configuration Tests
# =============================================================================


class TestConfigurationIntegration:
    """Tests for configuration value relationships."""

    def test_backup_recovery_time_aligned_with_requirements(self):
        """Backup recovery time should meet SLA."""
        config = get_backup_recovery_config()
        assert config.MAX_RECOVERY_TIME_MINUTES <= config.RECOVERY_TIME_TARGET_MINUTES

    def test_intrusion_detection_aligned_with_requirements(self):
        """Intrusion detection config should meet 等保 2.0 requirements."""
        config = get_intrusion_detection_config()
        assert config.HIGH_RISK_COUNT_TARGET == 0
        assert config.MEDIUM_RISK_COUNT_TARGET == 5
        assert config.PENETRATION_TEST_COVERAGE_TARGET >= 90.0

    def test_mfa_coverage_target_100_percent(self):
        """MFA coverage target should be 100%."""
        config = get_mfa_config()
        assert config.MFA_COVERAGE_TARGET == 100.0

    def test_compliance_reporting_rbac_target_aligned(self):
        """Compliance reporting RBAC target should align with MFA target."""
        compliance_config = get_compliance_reporting_config()
        mfa_config = get_mfa_config()
        assert compliance_config.RBAC_COVERAGE_TARGET == mfa_config.MFA_COVERAGE_TARGET

    def test_integrity_check_coverage_100_percent(self):
        """Integrity check coverage target should be 100%."""
        config = get_integrity_verification_config()
        assert config.INTEGRITY_CHECK_COVERAGE_TARGET == 100.0
        assert config.ENCRYPTION_COVERAGE_TARGET == 100.0
