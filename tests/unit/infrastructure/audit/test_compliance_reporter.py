"""Test ComplianceReporter - Red Phase (Test First).

TDD Cycle: Red -> Green -> Refactor
Reference: Story 1.10 Task 5 - Compliance Validation (等保 2.0 + SOX)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest import mock

import pytest


class TestComplianceReporterGenerateDengbaoReport:
    """Test generate_dengbao_report() method."""

    @pytest.mark.asyncio
    async def test_generate_dengbao_report_returns_compliance_report(self):
        """generate_dengbao_report() returns a ComplianceReport."""
        from src.infrastructure.audit.compliance_reporter import ComplianceReporter

        mock_audit_service = mock.AsyncMock()
        mock_audit_service.get_stats.return_value = {
            "total_entries": 100,
            "by_action_type": {
                "authentication:login": 50,
                "authentication:logout": 45,
                "authentication:failed": 5,
            },
        }
        mock_audit_service.query.return_value = {
            "items": [{"log_id": "1", "timestamp": datetime.now(UTC).isoformat()}],
            "total_pages": 1,
        }

        reporter = ComplianceReporter(audit_service=mock_audit_service)

        report = await reporter.generate_dengbao_report()

        assert report.report_type == "dengbao_audit"
        assert report.generated_at is not None
        assert "start" in report.time_range
        assert "end" in report.time_range
        assert "summary" in report.to_dict()
        assert "details" in report.to_dict()

    @pytest.mark.asyncio
    async def test_generate_dengbao_report_includes_auth_events(self):
        """Report includes authentication event analysis."""
        from src.infrastructure.audit.compliance_reporter import ComplianceReporter

        mock_audit_service = mock.AsyncMock()
        mock_audit_service.get_stats.return_value = {
            "total_entries": 100,
            "by_action_type": {
                "authentication:login": 50,
                "authentication:logout": 45,
                "authentication:failed": 5,
                "authentication:locked": 2,
            },
        }
        mock_audit_service.query.return_value = {"items": [], "total_pages": 1}

        reporter = ComplianceReporter(audit_service=mock_audit_service)

        report = await reporter.generate_dengbao_report()

        auth_events = report.details["authentication"]
        assert auth_events["total_logins"] == 50
        assert auth_events["total_logouts"] == 45
        assert auth_events["failed_attempts"] == 5
        assert auth_events["account_locks"] == 2

    @pytest.mark.asyncio
    async def test_generate_dengbao_report_includes_permission_events(self):
        """Report includes permission change analysis."""
        from src.infrastructure.audit.compliance_reporter import ComplianceReporter

        mock_audit_service = mock.AsyncMock()
        mock_audit_service.get_stats.return_value = {
            "total_entries": 100,
            "by_action_type": {
                "authorization:grant": 10,
                "authorization:revoke": 5,
                "authorization:access": 2,
            },
        }
        mock_audit_service.query.return_value = {"items": [], "total_pages": 1}

        reporter = ComplianceReporter(audit_service=mock_audit_service)

        report = await reporter.generate_dengbao_report()

        permission_events = report.details["authorization"]
        assert permission_events["total_grants"] == 10
        assert permission_events["total_revocations"] == 5
        assert permission_events["access_denials"] == 2

    @pytest.mark.asyncio
    async def test_generate_dengbao_report_calculates_completeness(self):
        """Report calculates completeness scores."""
        from src.infrastructure.audit.compliance_reporter import ComplianceReporter

        mock_audit_service = mock.AsyncMock()
        mock_audit_service.get_stats.return_value = {
            "total_entries": 100,
            "by_action_type": {
                "authentication:login": 100,
                "authentication:logout": 95,
            },
        }
        mock_audit_service.query.return_value = {"items": [], "total_pages": 1}

        reporter = ComplianceReporter(audit_service=mock_audit_service)

        report = await reporter.generate_dengbao_report()

        assert "login_event_completeness" in report.summary
        assert "permission_change_completeness" in report.summary
        assert "overall_score" in report.summary
        assert "passed" in report.summary

    @pytest.mark.asyncio
    async def test_generate_dengbao_report_with_time_range(self):
        """Report respects custom time range."""
        from src.infrastructure.audit.compliance_reporter import ComplianceReporter

        mock_audit_service = mock.AsyncMock()
        mock_audit_service.get_stats.return_value = {"total_entries": 0, "by_action_type": {}}
        mock_audit_service.query.return_value = {"items": [], "total_pages": 1}

        reporter = ComplianceReporter(audit_service=mock_audit_service)

        start = datetime.now(UTC) - timedelta(days=7)
        end = datetime.now(UTC)

        report = await reporter.generate_dengbao_report(start_time=start, end_time=end)

        assert start.isoformat() in report.time_range["start"]
        assert end.isoformat() in report.time_range["end"]


class TestComplianceReporterGenerateSoxReport:
    """Test generate_sox_report() method."""

    @pytest.mark.asyncio
    async def test_generate_sox_report_returns_compliance_report(self):
        """generate_sox_report() returns a ComplianceReport."""
        from src.infrastructure.audit.compliance_reporter import ComplianceReporter

        mock_audit_service = mock.AsyncMock()
        mock_audit_service.get_stats.return_value = {"total_entries": 100, "by_action_type": {}}
        mock_audit_service.query.return_value = {"items": [], "total_pages": 1}

        reporter = ComplianceReporter(audit_service=mock_audit_service)

        report = await reporter.generate_sox_report()

        assert report.report_type == "sox_compliance"
        assert "summary" in report.to_dict()
        assert "details" in report.to_dict()

    @pytest.mark.asyncio
    async def test_generate_sox_report_includes_financial_events(self):
        """Report includes financial event analysis."""
        from src.infrastructure.audit.compliance_reporter import ComplianceReporter

        mock_audit_service = mock.AsyncMock()
        mock_audit_service.get_stats.return_value = {
            "total_entries": 100,
            "by_action_type": {
                "correction:approve": 5,
                "correction:reject": 2,
                "correction:apply": 3,
                "checkpoint:create": 10,
            },
        }
        mock_audit_service.query.return_value = {"items": [], "total_pages": 1}

        reporter = ComplianceReporter(audit_service=mock_audit_service)

        report = await reporter.generate_sox_report()

        financial = report.details["financial_events"]
        assert financial["correction_events"] == 10
        assert financial["checkpoint_events"] == 10

    @pytest.mark.asyncio
    async def test_generate_sox_report_checks_retention(self):
        """Report includes retention compliance check."""
        from src.infrastructure.audit.compliance_reporter import ComplianceReporter

        mock_audit_service = mock.AsyncMock()
        mock_audit_service.get_stats.return_value = {"total_entries": 100, "by_action_type": {}}
        mock_audit_service.query.return_value = {"items": [], "total_pages": 1}

        reporter = ComplianceReporter(audit_service=mock_audit_service)

        report = await reporter.generate_sox_report()

        assert "retention_compliance" in report.summary
        assert report.summary["retention_compliance"] == 1.0


class TestComplianceReport:
    """Test ComplianceReport data class."""

    def test_compliance_report_to_dict(self):
        """ComplianceReport.to_dict() returns complete report."""
        from src.infrastructure.audit.compliance_reporter import ComplianceReport

        now = datetime.now(UTC)
        report = ComplianceReport(
            report_type="test",
            generated_at=now,
            time_range={"start": now.isoformat(), "end": now.isoformat()},
            summary={"score": 0.95},
            details={"count": 100},
        )

        d = report.to_dict()

        assert d["report_type"] == "test"
        assert d["generated_at"] == now.isoformat()
        assert d["time_range"]["start"] == now.isoformat()
        assert d["summary"]["score"] == 0.95
        assert d["details"]["count"] == 100


class TestComplianceReporterAnalyzeMethods:
    """Test internal analysis methods."""

    def test_analyze_auth_events(self):
        """_analyze_auth_events correctly analyzes auth stats."""
        from src.infrastructure.audit.compliance_reporter import ComplianceReporter

        mock_audit_service = mock.Mock()
        reporter = ComplianceReporter(audit_service=mock_audit_service)

        stats = {
            "by_action_type": {
                "authentication:login": 100,
                "authentication:logout": 90,
                "authentication:failed": 10,
                "authentication:locked": 3,
            },
        }

        result = reporter._analyze_auth_events(stats)

        assert result["total_logins"] == 100
        assert result["total_logouts"] == 90
        assert result["failed_attempts"] == 10
        assert result["account_locks"] == 3
        assert result["login_logout_ratio"] == 0.9

    def test_analyze_permission_events(self):
        """_analyze_permission_events correctly analyzes permission stats."""
        from src.infrastructure.audit.compliance_reporter import ComplianceReporter

        mock_audit_service = mock.Mock()
        reporter = ComplianceReporter(audit_service=mock_audit_service)

        stats = {
            "by_action_type": {
                "authorization:grant": 20,
                "authorization:revoke": 5,
                "authorization:access": 3,
            },
        }

        result = reporter._analyze_permission_events(stats)

        assert result["total_grants"] == 20
        assert result["total_revocations"] == 5
        assert result["access_denials"] == 3
        assert result["total_changes"] == 25

    def test_analyze_sensitive_events(self):
        """_analyze_sensitive_events correctly identifies sensitive operations."""
        from src.infrastructure.audit.compliance_reporter import ComplianceReporter

        mock_audit_service = mock.Mock()
        reporter = ComplianceReporter(audit_service=mock_audit_service)

        stats = {
            "by_action_type": {
                "document:upload": 50,
                "document:delete": 5,
                "system:config_change": 10,
                "correction:approve": 3,
            },
        }

        result = reporter._analyze_sensitive_events(stats)

        assert result["total_sensitive_operations"] == 68
        assert result["by_type"]["document:upload"] == 50
        assert result["by_type"]["document:delete"] == 5

    def test_calculate_completeness(self):
        """_calculate_completeness returns correct scores."""
        from src.infrastructure.audit.compliance_reporter import ComplianceReporter

        mock_audit_service = mock.Mock()
        reporter = ComplianceReporter(audit_service=mock_audit_service)

        # Normal case
        assert reporter._calculate_completeness(95, 100) == 0.95

        # Exceeds minimum
        assert reporter._calculate_completeness(150, 100) == 1.0

        # Zero minimum
        assert reporter._calculate_completeness(50, 0) == 1.0
