"""Data Sovereignty Configuration.

Reference: Story 1.11 Data Sovereignty Isolation.
Config pattern follows auth.py (XxxConfig + from_env() + get_xxx_config()).
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from datetime import timedelta

from ..security.models import DataResidency, SensitiveDataType


@dataclass
class DataSovereigntyConfig:
    """Data sovereignty configuration.

    Attributes:
        enabled: Whether data sovereignty enforcement is enabled.
        default_residency: Default data residency requirement.
        allowed_storage_regions: List of allowed storage regions (ISO 3166-1 alpha-2).
        denied_storage_regions: List of denied storage regions.
        cross_border_sla_hours: SLA for cross-border approval in hours (MVP: 48h).
        whitelist_max_rules: Maximum number of whitelist rules.
        whitelist_auto_expire_days: Auto-expire whitelist rules after N days (0 = disabled).
        detection_confidence_threshold: Minimum confidence for auto-detection (0.0-1.0).
        pipl_consent_required: Require explicit consent for PIPL data processing.
        biometric_strict_mode: Enhanced protection for biometric data.
        minor_age_threshold: Age threshold for minor protection (default: 14 in China).
        default_policies: Default sovereignty policies per data type.
    """

    enabled: bool = True
    default_residency: DataResidency = DataResidency.CHINA_DOMESTIC
    allowed_storage_regions: list[str] = field(default_factory=lambda: ["CN"])
    denied_storage_regions: list[str] = field(default_factory=lambda: [])
    cross_border_sla_hours: int = 48
    whitelist_max_rules: int = 100
    whitelist_auto_expire_days: int = 0
    detection_confidence_threshold: float = 0.95
    pipl_consent_required: bool = True
    biometric_strict_mode: bool = True
    minor_age_threshold: int = 14

    # Default policies per sensitive data type
    default_policies: dict[SensitiveDataType, dict] = field(
        default_factory=lambda: {
            SensitiveDataType.PII: {
                "residency": DataResidency.CHINA_DOMESTIC,
                "cross_border_allowed": False,
                "storage_allowed": ["CN"],
            },
            SensitiveDataType.TRADE_SECRET: {
                "residency": DataResidency.CHINA_DOMESTIC,
                "cross_border_allowed": False,
                "storage_allowed": ["CN"],
            },
            SensitiveDataType.FINANCIAL: {
                "residency": DataResidency.CHINA_DOMESTIC,
                "cross_border_allowed": False,
                "storage_allowed": ["CN"],
            },
            SensitiveDataType.BIOMETRIC: {
                "residency": DataResidency.CHINA_DOMESTIC,
                "cross_border_allowed": False,
                "storage_allowed": ["CN"],
            },
            SensitiveDataType.MINOR: {
                "residency": DataResidency.CHINA_DOMESTIC,
                "cross_border_allowed": False,
                "storage_allowed": ["CN"],
            },
            SensitiveDataType.HEALTH: {
                "residency": DataResidency.CHINA_DOMESTIC,
                "cross_border_allowed": False,
                "storage_allowed": ["CN"],
            },
            SensitiveDataType.IDENTITY_DOCUMENT: {
                "residency": DataResidency.CHINA_DOMESTIC,
                "cross_border_allowed": False,
                "storage_allowed": ["CN"],
            },
            SensitiveDataType.CUSTOM: {
                "residency": DataResidency.GLOBAL,
                "cross_border_allowed": True,
                "storage_allowed": ["CN", "HK", "MO", "TW", "US", "EU"],
            },
        }
    )

    # Regex patterns for PII detection
    pii_detection_patterns: dict[str, str] = field(
        default_factory=lambda: {
            "china_id": r"\b[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b",
            "phone_cn": r"\b1[3-9]\d{9}\b",
            "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
            # Bank account: require specific Chinese bank prefixes to avoid false positives
            "bank_account": r"\b(?:6222|6217|6235|6229|6011)\d{10,15}\b",
            "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
        }
    )

    # Keyword patterns for trade secret detection
    trade_secret_keywords: list[str] = field(
        default_factory=lambda: [
            "机密",
            "秘密",
            "绝密",
            "机密文件",
            "内部资料",
            "核心配方",
            "技术方案",
            "商业计划",
            "客户名单",
            "供应商名单",
            "定价策略",
            "净利润",
            "毛利率",
            "营业收入",
            "研发投入",
            "专利技术",
        ]
    )

    @classmethod
    def from_env(cls) -> DataSovereigntyConfig:
        """Load configuration from environment variables.

        Environment variables:
            SOVEREIGNTY_ENABLED: Enable data sovereignty enforcement (default: true).
            SOVEREIGNTY_DEFAULT_RESIDENCY: Default residency (china_domestic/global).
            SOVEREIGNTY_ALLOWED_REGIONS: Comma-separated allowed storage regions.
            SOVEREIGNTY_DENIED_REGIONS: Comma-separated denied storage regions.
            SOVEREIGNTY_CROSS_BORDER_SLA_HOURS: SLA in hours (default: 48).
            SOVEREIGNTY_WHITELIST_MAX_RULES: Max whitelist rules (default: 100).
            SOVEREIGNTY_WHITELIST_AUTO_EXPIRE_DAYS: Auto-expire after N days (default: 0).
            SOVEREIGNTY_DETECTION_CONFIDENCE: Min detection confidence (default: 0.95).
            SOVEREIGNTY_PIPL_CONSENT_REQUIRED: Require PIPL consent (default: true).
            SOVEREIGNTY_BIOMETRIC_STRICT_MODE: Enhanced biometric protection (default: true).
            SOVEREIGNTY_MINOR_AGE_THRESHOLD: Minor age threshold (default: 14).
        """
        allowed_regions_str = os.getenv("SOVEREIGNTY_ALLOWED_REGIONS", "CN")
        denied_regions_str = os.getenv("SOVEREIGNTY_DENIED_REGIONS", "")

        default_residency_str = os.getenv("SOVEREIGNTY_DEFAULT_RESIDENCY", "china_domestic")
        try:
            default_residency = DataResidency(default_residency_str)
        except ValueError:
            default_residency = DataResidency.CHINA_DOMESTIC

        return cls(
            enabled=os.getenv("SOVEREIGNTY_ENABLED", "true").lower() in ("true", "1", "yes"),
            default_residency=default_residency,
            allowed_storage_regions=[r.strip() for r in allowed_regions_str.split(",") if r.strip()],
            denied_storage_regions=[r.strip() for r in denied_regions_str.split(",") if r.strip()],
            cross_border_sla_hours=int(os.getenv("SOVEREIGNTY_CROSS_BORDER_SLA_HOURS", "48")),
            whitelist_max_rules=int(os.getenv("SOVEREIGNTY_WHITELIST_MAX_RULES", "100")),
            whitelist_auto_expire_days=int(os.getenv("SOVEREIGNTY_WHITELIST_AUTO_EXPIRE_DAYS", "0")),
            detection_confidence_threshold=float(os.getenv("SOVEREIGNTY_DETECTION_CONFIDENCE", "0.95")),
            pipl_consent_required=os.getenv("SOVEREIGNTY_PIPL_CONSENT_REQUIRED", "true").lower() in ("true", "1", "yes"),
            biometric_strict_mode=os.getenv("SOVEREIGNTY_BIOMETRIC_STRICT_MODE", "true").lower() in ("true", "1", "yes"),
            minor_age_threshold=int(os.getenv("SOVEREIGNTY_MINOR_AGE_THRESHOLD", "14")),
        )

    def get_sla_deadline(self) -> timedelta:
        """Get the SLA deadline as a timedelta.

        Returns:
            timedelta: SLA deadline duration.
        """
        return timedelta(hours=self.cross_border_sla_hours)


# Global config instance (lazy loading, thread-safe)
_sovereignty_config: DataSovereigntyConfig | None = None
_config_lock = threading.Lock()


def get_sovereignty_config() -> DataSovereigntyConfig:
    """Get the global DataSovereigntyConfig instance (lazy loading).

    Returns:
        DataSovereigntyConfig: The global data sovereignty configuration.
    """
    global _sovereignty_config
    if _sovereignty_config is None:
        with _config_lock:
            # Double-checked locking pattern
            if _sovereignty_config is None:
                _sovereignty_config = DataSovereigntyConfig.from_env()
    return _sovereignty_config
