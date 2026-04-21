"""等保 2.0 Level 3 Compliance Configuration.

Configuration settings for 等保 2.0 Level 3 compliance features:
- MFA/TOTP settings
- Intrusion detection thresholds
- Backup/recovery schedules
- Integrity verification settings

等保 2.0 Level 3 要求:
- 身份鉴别: MFA覆盖率100%
- 访问控制: RBAC覆盖率100%
- 安全审计: 审计日志完整性100%
- 入侵防范: 渗透测试覆盖率≥90%
- 数据完整性: 加密覆盖率100%
- 备份恢复: 恢复时间<1小时

Reference: Story 1.12 等保 2.0 三级基础要求
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MFAConfig:
    """MFA/TOTP Configuration."""

    # TOTP settings
    TOTP_DIGITS: int = 6
    TOTP_PERIOD_SECONDS: int = 30
    TOTP_ISSUER: str = "SISYS"

    # Challenge settings
    CHALLENGE_TTL_MINUTES: int = 5
    MAX_VERIFICATION_ATTEMPTS: int = 3

    # Coverage requirement
    MFA_COVERAGE_TARGET: float = 100.0


@dataclass
class IntrusionDetectionConfig:
    """Intrusion Detection Configuration."""

    # Rate limiting
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_MAX_REQUESTS: int = 100

    # Brute force detection
    BRUTE_FORCE_WINDOW_SECONDS: int = 300
    BRUTE_FORCE_MAX_ATTEMPTS: int = 5
    BRUTE_FORCE_BLOCK_DURATION_SECONDS: int = 300

    # Threat scoring thresholds
    THREAT_LEVEL_BENIGN: float = 0.0
    THREAT_LEVEL_SUSPICIOUS: float = 30.0
    THREAT_LEVEL_MALICIOUS: float = 60.0
    THREAT_LEVEL_CRITICAL: float = 80.0

    # Attack severity scores
    SCORE_SQL_INJECTION: float = 40.0
    SCORE_XSS: float = 30.0
    SCORE_COMMAND_INJECTION: float = 50.0
    SCORE_PATH_TRAVERSAL: float = 30.0
    SCORE_PROMPT_INJECTION: float = 35.0
    SCORE_CSRF: float = 20.0
    SCORE_DATA_EXFILTRATION: float = 45.0
    SCORE_RATE_LIMIT_VIOLATION: float = 30.0
    SCORE_BRUTE_FORCE: float = 50.0

    # Coverage requirements
    PENETRATION_TEST_COVERAGE_TARGET: float = 90.0
    HIGH_RISK_COUNT_TARGET: int = 0
    MEDIUM_RISK_COUNT_TARGET: int = 5


@dataclass
class BackupRecoveryConfig:
    """Backup and Recovery Configuration."""

    # Backup settings
    STORAGE_PATH: str = "/var/sisys/backups"
    FULL_BACKUP_SCHEDULE: str = "daily"  # daily, weekly
    INCREMENTAL_BACKUP_SCHEDULE: str = "hourly"

    # Recovery settings
    MAX_RECOVERY_TIME_MINUTES: int = 60
    ESTIMATED_RECOVERY_SPEED_MBPS: float = 10.0

    # Retention
    FULL_BACKUP_RETENTION_DAYS: int = 30
    INCREMENTAL_BACKUP_RETENTION_DAYS: int = 7

    # Coverage requirements
    BACKUP_COVERAGE_TARGET: float = 100.0
    RECOVERY_TIME_TARGET_MINUTES: int = 60


@dataclass
class IntegrityVerificationConfig:
    """Integrity Verification Configuration."""

    # Hash algorithms
    DEFAULT_HASH_ALGORITHM: str = "SHA256"
    SUPPORTED_ALGORITHMS: list[str] = field(default_factory=lambda: ["SHA256", "SHA512", "MD5"])

    # Signature settings
    RSA_KEY_SIZE_BITS: int = 2048
    SIGNATURE_ALGORITHM: str = "RSASSA-PKCS1-v1_5-SHA256"

    # Coverage requirements
    ENCRYPTION_COVERAGE_TARGET: float = 100.0
    INTEGRITY_CHECK_COVERAGE_TARGET: float = 100.0


@dataclass
class ComplianceReportingConfig:
    """Compliance Reporting Configuration."""

    # Reporting
    REPORT_GENERATION_SCHEDULE: str = "weekly"
    REPORT_FORMATS: list[str] = field(default_factory=lambda: ["pdf", "html", "json"])

    # Audit
    AUDIT_LOG_INTEGRITY_TARGET: float = 100.0
    RBAC_COVERAGE_TARGET: float = 100.0

    # Status
    DEFAULT_COMPLIANCE_LEVEL: int = 3  # 等保 2.0 Level 3


# Global configuration instances
_mfa_config: MFAConfig | None = None
_intrusion_config: IntrusionDetectionConfig | None = None
_backup_config: BackupRecoveryConfig | None = None
_integrity_config: IntegrityVerificationConfig | None = None
_reporting_config: ComplianceReportingConfig | None = None


def get_mfa_config() -> MFAConfig:
    """Get global MFA configuration.

    Returns:
        MFAConfig: Global MFA configuration.
    """
    global _mfa_config
    if _mfa_config is None:
        _mfa_config = MFAConfig()
    return _mfa_config


def get_intrusion_detection_config() -> IntrusionDetectionConfig:
    """Get global intrusion detection configuration.

    Returns:
        IntrusionDetectionConfig: Global intrusion detection configuration.
    """
    global _intrusion_config
    if _intrusion_config is None:
        _intrusion_config = IntrusionDetectionConfig()
    return _intrusion_config


def get_backup_recovery_config() -> BackupRecoveryConfig:
    """Get global backup/recovery configuration.

    Returns:
        BackupRecoveryConfig: Global backup/recovery configuration.
    """
    global _backup_config
    if _backup_config is None:
        _backup_config = BackupRecoveryConfig()
    return _backup_config


def get_integrity_verification_config() -> IntegrityVerificationConfig:
    """Get global integrity verification configuration.

    Returns:
        IntegrityVerificationConfig: Global integrity verification configuration.
    """
    global _integrity_config
    if _integrity_config is None:
        _integrity_config = IntegrityVerificationConfig(SUPPORTED_ALGORITHMS=["SHA256", "SHA512", "MD5"])
    return _integrity_config


def get_compliance_reporting_config() -> ComplianceReportingConfig:
    """Get global compliance reporting configuration.

    Returns:
        ComplianceReportingConfig: Global compliance reporting configuration.
    """
    global _reporting_config
    if _reporting_config is None:
        _reporting_config = ComplianceReportingConfig(REPORT_FORMATS=["pdf", "html", "json"])
    return _reporting_config
