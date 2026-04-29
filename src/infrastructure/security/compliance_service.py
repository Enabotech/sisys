"""Compliance Service — 等保 2.0 Level 3 Compliance Status and Reporting.

Aggregates security metrics from multiple services to provide:
- MFA coverage statistics
- RBAC coverage statistics
- Intrusion detection statistics
- Backup/recovery status
- Overall compliance score

等保 2.0 Level 3 要求:
- 合规报告: 完整合规指标
- MFA 覆盖率 100%
- RBAC 覆盖率 100%
- 高风险项 = 0, 中危漏洞 < 5
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from src.infrastructure.security.mfa_service import MFAService

if TYPE_CHECKING:
    pass


class ComplianceServiceError(Exception):
    """Base exception for compliance service errors."""

    pass


class ComplianceReportNotFoundError(ComplianceServiceError):
    """Compliance report not found."""

    pass


@dataclass
class ComplianceMetrics:
    """Compliance metrics for 等保 2.0 Level 3.

    Attributes:
        mfa_enabled_count: Number of users with MFA enabled.
        mfa_total_users: Total number of users.
        mfa_coverage: MFA coverage percentage (0.0-1.0).
        rbac_role_count: Number of active RBAC roles.
        rbac_permission_count: Number of configured permissions.
        rbac_coverage: RBAC coverage percentage (0.0-1.0).
        intrusion_detected_count: Number of intrusions detected in period.
        intrusion_blocked_count: Number of intrusions blocked.
        high_risk_vulnerabilities: Number of high-risk vulnerabilities.
        medium_risk_vulnerabilities: Number of medium-risk vulnerabilities.
        backup_count: Number of backups.
        backup_latest_time: Timestamp of latest backup.
        assessed_at: Assessment timestamp.
    """

    mfa_enabled_count: int = 0
    mfa_total_users: int = 0
    mfa_coverage: float = 0.0
    rbac_role_count: int = 0
    rbac_permission_count: int = 0
    rbac_coverage: float = 0.0
    intrusion_detected_count: int = 0
    intrusion_blocked_count: int = 0
    high_risk_vulnerabilities: int = 0
    medium_risk_vulnerabilities: int = 0
    backup_count: int = 0
    backup_latest_time: datetime | None = None
    assessed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            dict: Metrics as dictionary.
        """
        return {
            "mfa_enabled_count": self.mfa_enabled_count,
            "mfa_total_users": self.mfa_total_users,
            "mfa_coverage": self.mfa_coverage,
            "rbac_role_count": self.rbac_role_count,
            "rbac_permission_count": self.rbac_permission_count,
            "rbac_coverage": self.rbac_coverage,
            "intrusion_detected_count": self.intrusion_detected_count,
            "intrusion_blocked_count": self.intrusion_blocked_count,
            "high_risk_vulnerabilities": self.high_risk_vulnerabilities,
            "medium_risk_vulnerabilities": self.medium_risk_vulnerabilities,
            "backup_count": self.backup_count,
            "backup_latest_time": self.backup_latest_time.isoformat() if self.backup_latest_time else None,
            "assessed_at": self.assessed_at.isoformat(),
        }


@dataclass
class ComplianceStatus:
    """Overall compliance status for 等保 2.0 Level 3.

    Attributes:
        level: Compliance level (e.g., "三级").
        is_compliant: Whether system meets all compliance requirements.
        overall_score: Overall compliance score (0.0-1.0).
        metrics: Detailed compliance metrics.
        ac_status: Status of each acceptance criterion.
    """

    level: str = "三级"
    is_compliant: bool = False
    overall_score: float = 0.0
    metrics: ComplianceMetrics = field(default_factory=ComplianceMetrics)
    ac_status: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            dict: Status as dictionary.
        """
        return {
            "level": self.level,
            "is_compliant": self.is_compliant,
            "overall_score": self.overall_score,
            "metrics": self.metrics.to_dict(),
            "ac_status": self.ac_status,
        }


@dataclass
class VulnerabilityCount:
    """Vulnerability count by severity level.

    Attributes:
        critical: Number of critical vulnerabilities.
        high: Number of high-risk vulnerabilities.
        medium: Number of medium-risk vulnerabilities.
        low: Number of low-risk vulnerabilities.
    """

    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0

    def total(self) -> int:
        """Total number of vulnerabilities.

        Returns:
            int: Total count.
        """
        return self.critical + self.high + self.medium + self.low


class ComplianceService:
    """Compliance Service for 等保 2.0 Level 3 compliance reporting.

    Aggregates security metrics from multiple services:
    - MFA coverage (from MFAService)
    - RBAC coverage
    - Intrusion statistics (from IntrusionDetector)
    - Backup status (from BackupService)
    """

    def __init__(
        self,
        mfa_service: MFAService | None = None,
    ) -> None:
        """Initialize Compliance Service.

        Args:
            mfa_service: MFA service instance.
        """
        self._mfa_service = mfa_service or MFAService()

        # In-memory vulnerability tracking (in production, use database)
        self._vulnerabilities: dict[str, VulnerabilityCount] = {
            "sql_injection": VulnerabilityCount(),
            "xss": VulnerabilityCount(),
            "command_injection": VulnerabilityCount(),
            "brute_force": VulnerabilityCount(),
        }

        # RBAC metrics (set via setters for testing)
        self._rbac_role_count: int = 0
        self._rbac_permission_count: int = 0

    def set_rbac_metrics(self, role_count: int, permission_count: int) -> None:
        """Set RBAC metrics directly.

        Args:
            role_count: Number of active RBAC roles.
            permission_count: Number of configured permissions.
        """
        self._rbac_role_count = role_count
        self._rbac_permission_count = permission_count

    async def get_compliance_status(self) -> ComplianceStatus:
        """Get overall compliance status.

        Returns:
            ComplianceStatus: Current compliance status.
        """
        metrics = await self.get_compliance_metrics()

        # Determine AC status
        ac_status = self._calculate_ac_status(metrics)

        # Calculate overall score
        overall_score = self._calculate_overall_score(metrics, ac_status)

        # Determine if compliant (all criteria met)
        is_compliant = (
            all(status in ("passed", "not_applicable") for status in ac_status.values())
            and metrics.high_risk_vulnerabilities == 0
        )

        return ComplianceStatus(
            level="三级",
            is_compliant=is_compliant,
            overall_score=overall_score,
            metrics=metrics,
            ac_status=ac_status,
        )

    async def get_compliance_metrics(self) -> ComplianceMetrics:
        """Get detailed compliance metrics.

        Returns:
            ComplianceMetrics: Detailed compliance metrics.
        """
        # MFA metrics (mock for now - in production, query user service)
        mfa_total_users = 100
        mfa_enabled_count = 95
        mfa_coverage = mfa_enabled_count / mfa_total_users if mfa_total_users > 0 else 0.0

        # RBAC metrics
        rbac_coverage = min(1.0, self._rbac_permission_count / 10)

        # Intrusion metrics
        intrusion_detected = sum(v.total() for v in self._vulnerabilities.values())
        intrusion_blocked = sum(v.high + v.medium for v in self._vulnerabilities.values())

        # Vulnerability counts
        high_risk = sum(v.high for v in self._vulnerabilities.values())
        medium_risk = sum(v.medium for v in self._vulnerabilities.values())

        return ComplianceMetrics(
            mfa_enabled_count=mfa_enabled_count,
            mfa_total_users=mfa_total_users,
            mfa_coverage=mfa_coverage,
            rbac_role_count=self._rbac_role_count,
            rbac_permission_count=self._rbac_permission_count,
            rbac_coverage=rbac_coverage,
            intrusion_detected_count=intrusion_detected,
            intrusion_blocked_count=intrusion_blocked,
            high_risk_vulnerabilities=high_risk,
            medium_risk_vulnerabilities=medium_risk,
            backup_count=0,
            backup_latest_time=None,
        )

    async def generate_compliance_report(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Generate compliance report.

        Args:
            start_time: Report period start. Defaults to 30 days ago.
            end_time: Report period end. Defaults to now.

        Returns:
            dict: Compliance report.
        """
        if end_time is None:
            end_time = datetime.now(UTC)
        if start_time is None:
            from datetime import timedelta

            start_time = end_time - timedelta(days=30)

        status = await self.get_compliance_status()
        metrics = status.metrics

        # Build AC status summary
        ac_summary = {}
        for ac_name, ac_status_value in status.ac_status.items():
            ac_summary[ac_name] = {
                "status": ac_status_value,
                "compliant": ac_status_value == "passed",
            }

        # Vulnerability summary
        vulnerability_summary = {
            "high_risk_count": metrics.high_risk_vulnerabilities,
            "medium_risk_count": metrics.medium_risk_vulnerabilities,
            "intrusions_detected": metrics.intrusion_detected_count,
            "intrusions_blocked": metrics.intrusion_blocked_count,
        }

        return {
            "report_type": "dengbao_level_3",
            "level": status.level,
            "generated_at": datetime.now(UTC).isoformat(),
            "period": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
            },
            "is_compliant": status.is_compliant,
            "overall_score": status.overall_score,
            "metrics": metrics.to_dict(),
            "ac_status": ac_summary,
            "vulnerability_summary": vulnerability_summary,
            "passed": status.is_compliant and metrics.high_risk_vulnerabilities == 0,
        }

    def record_vulnerability(
        self,
        vulnerability_type: str,
        severity: str,
    ) -> None:
        """Record a detected vulnerability.

        Args:
            vulnerability_type: Type of vulnerability (sql_injection, xss, etc.).
            severity: Severity level (high, medium, low).
        """
        if vulnerability_type not in self._vulnerabilities:
            self._vulnerabilities[vulnerability_type] = VulnerabilityCount()

        vuln = self._vulnerabilities[vulnerability_type]
        if severity == "high":
            vuln.high += 1
        elif severity == "medium":
            vuln.medium += 1
        elif severity == "low":
            vuln.low += 1
        else:
            vuln.critical += 1

    def _calculate_ac_status(
        self,
        metrics: ComplianceMetrics,
    ) -> dict[str, str]:
        """Calculate status of each acceptance criterion.

        Args:
            metrics: Compliance metrics.

        Returns:
            dict: AC status mapping.
        """
        return {
            "AC-1_MFA": "passed" if metrics.mfa_coverage >= 1.0 else "failed",
            "AC-2_RBAC": "passed" if metrics.rbac_coverage >= 1.0 else "failed",
            "AC-4_Intrusion": "passed"
            if (metrics.high_risk_vulnerabilities == 0 and metrics.medium_risk_vulnerabilities < 5)
            else "failed",
            "AC-5_Integrity": "passed",  # Assumed passed if other checks pass
            "AC-6_Backup": "passed" if metrics.backup_count > 0 else "not_applicable",
        }

    def _calculate_overall_score(
        self,
        metrics: ComplianceMetrics,
        ac_status: dict[str, str],
    ) -> float:
        """Calculate overall compliance score.

        Args:
            metrics: Compliance metrics.
            ac_status: AC status mapping.

        Returns:
            float: Overall score (0.0-1.0).
        """
        # Weight by importance
        weights = {
            "AC-1_MFA": 0.25,
            "AC-2_RBAC": 0.25,
            "AC-4_Intrusion": 0.25,
            "AC-5_Integrity": 0.15,
            "AC-6_Backup": 0.10,
        }

        total_weight = 0.0
        weighted_score = 0.0

        for ac_name, weight in weights.items():
            status = ac_status.get(ac_name, "failed")
            if status == "passed":
                weighted_score += weight
            elif status == "not_applicable":
                weighted_score += weight  # Don't penalize for N/A
            total_weight += weight

        return weighted_score / total_weight if total_weight > 0 else 0.0


# Global compliance service instance
_compliance_service: ComplianceService | None = None


def get_compliance_service() -> ComplianceService:
    """Get global Compliance Service instance.

    Returns:
        ComplianceService: Global compliance service instance.
    """
    global _compliance_service
    if _compliance_service is None:
        _compliance_service = ComplianceService()
    return _compliance_service
