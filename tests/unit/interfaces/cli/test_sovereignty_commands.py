"""Tests for sovereignty CLI command models.

Tests Pydantic/dataclass models for CLI command validation.
Reference: Story 1.11 Data Sovereignty Isolation.
"""

from __future__ import annotations

from src.infrastructure.security.models import ApprovalStatus, WhitelistStatus
from src.interfaces.cli.sovereignty_commands import (
    ApprovalApproveCommand,
    ApprovalListCommand,
    ApprovalRejectCommand,
    ComplianceStatusCommand,
    WhitelistAddCommand,
    WhitelistListCommand,
    WhitelistRevokeCommand,
)


class TestWhitelistAddCommand:
    """Tests for WhitelistAddCommand model."""

    def test_valid_command_required_fields(self):
        """Should create with required fields."""
        cmd = WhitelistAddCommand(
            endpoint="https://api.example.com",
            provider="ExampleAPI",
        )
        assert cmd.endpoint == "https://api.example.com"
        assert cmd.provider == "ExampleAPI"
        assert cmd.purpose == ""
        assert cmd.risk_level == "medium"
        assert cmd.expiry_days == 0

    def test_valid_command_all_fields(self):
        """Should create with all fields."""
        cmd = WhitelistAddCommand(
            endpoint="https://api.example.com",
            provider="ExampleAPI",
            purpose="Data sync",
            risk_level="high",
            expiry_days=30,
        )
        assert cmd.purpose == "Data sync"
        assert cmd.risk_level == "high"
        assert cmd.expiry_days == 30

    def test_to_args_basic(self):
        """Should convert to CLI arguments."""
        cmd = WhitelistAddCommand(
            endpoint="https://api.example.com",
            provider="ExampleAPI",
        )
        args = cmd.to_args()
        assert args == [
            "system",
            "whitelist",
            "add",
            "--endpoint",
            "https://api.example.com",
            "--provider",
            "ExampleAPI",
        ]

    def test_to_args_with_purpose(self):
        """Should include purpose in CLI arguments."""
        cmd = WhitelistAddCommand(
            endpoint="https://api.example.com",
            provider="ExampleAPI",
            purpose="Data sync",
        )
        args = cmd.to_args()
        assert "--purpose" in args
        assert "Data sync" in args

    def test_to_args_with_custom_risk_level(self):
        """Should include risk level when not default."""
        cmd = WhitelistAddCommand(
            endpoint="https://api.example.com",
            provider="ExampleAPI",
            risk_level="critical",
        )
        args = cmd.to_args()
        assert "--risk-level" in args
        assert "critical" in args

    def test_to_args_with_expiry_days(self):
        """Should include expiry days when set."""
        cmd = WhitelistAddCommand(
            endpoint="https://api.example.com",
            provider="ExampleAPI",
            expiry_days=90,
        )
        args = cmd.to_args()
        assert "--expiry-days" in args
        assert "90" in args

    def test_to_args_default_risk_level_not_included(self):
        """Should not include default risk level."""
        cmd = WhitelistAddCommand(
            endpoint="https://api.example.com",
            provider="ExampleAPI",
        )
        args = cmd.to_args()
        assert "--risk-level" not in args


class TestWhitelistRevokeCommand:
    """Tests for WhitelistRevokeCommand model."""

    def test_valid_command(self):
        """Should create revoke command."""
        cmd = WhitelistRevokeCommand(
            rule_id="550e8400-e29b-41d4-a716-446655440000",
            reason="Policy violation",
        )
        assert cmd.rule_id == "550e8400-e29b-41d4-a716-446655440000"
        assert cmd.reason == "Policy violation"

    def test_to_args_without_reason(self):
        """Should convert to CLI arguments without reason."""
        cmd = WhitelistRevokeCommand(rule_id="550e8400-e29b-41d4-a716-446655440000")
        args = cmd.to_args()
        assert args == [
            "system",
            "whitelist",
            "revoke",
            "--rule-id",
            "550e8400-e29b-41d4-a716-446655440000",
        ]

    def test_to_args_with_reason(self):
        """Should include reason in CLI arguments."""
        cmd = WhitelistRevokeCommand(
            rule_id="550e8400-e29b-41d4-a716-446655440000",
            reason="Policy violation",
        )
        args = cmd.to_args()
        assert "--reason" in args
        assert "Policy violation" in args


class TestWhitelistListCommand:
    """Tests for WhitelistListCommand model."""

    def test_default_status(self):
        """Should create with no status filter."""
        cmd = WhitelistListCommand()
        assert cmd.status is None

    def test_with_status_filter(self):
        """Should create with status filter."""
        cmd = WhitelistListCommand(status=WhitelistStatus.ACTIVE)
        assert cmd.status == WhitelistStatus.ACTIVE

    def test_to_args_no_status(self):
        """Should convert to CLI arguments without status."""
        cmd = WhitelistListCommand()
        args = cmd.to_args()
        assert args == ["system", "whitelist", "list"]
        assert "--status" not in args

    def test_to_args_with_status(self):
        """Should include status in CLI arguments."""
        cmd = WhitelistListCommand(status=WhitelistStatus.ACTIVE)
        args = cmd.to_args()
        assert "--status" in args
        assert "active" in args


class TestApprovalListCommand:
    """Tests for ApprovalListCommand model."""

    def test_default_status(self):
        """Should create with no status filter."""
        cmd = ApprovalListCommand()
        assert cmd.status is None

    def test_with_pending_status(self):
        """Should create with pending status filter."""
        cmd = ApprovalListCommand(status=ApprovalStatus.PENDING)
        assert cmd.status == ApprovalStatus.PENDING

    def test_to_args_no_status(self):
        """Should convert to CLI arguments without status."""
        cmd = ApprovalListCommand()
        args = cmd.to_args()
        assert args == ["system", "approval", "list"]
        assert "--status" not in args

    def test_to_args_with_status(self):
        """Should include status in CLI arguments."""
        cmd = ApprovalListCommand(status=ApprovalStatus.PENDING)
        args = cmd.to_args()
        assert "--status" in args
        assert "pending" in args


class TestApprovalApproveCommand:
    """Tests for ApprovalApproveCommand model."""

    def test_valid_command(self):
        """Should create approve command."""
        cmd = ApprovalApproveCommand(request_id="550e8400-e29b-41d4-a716-446655440000")
        assert cmd.request_id == "550e8400-e29b-41d4-a716-446655440000"

    def test_to_args(self):
        """Should convert to CLI arguments."""
        cmd = ApprovalApproveCommand(request_id="550e8400-e29b-41d4-a716-446655440000")
        args = cmd.to_args()
        assert args == [
            "system",
            "approval",
            "approve",
            "--request-id",
            "550e8400-e29b-41d4-a716-446655440000",
        ]


class TestApprovalRejectCommand:
    """Tests for ApprovalRejectCommand model."""

    def test_valid_command(self):
        """Should create reject command."""
        cmd = ApprovalRejectCommand(
            request_id="550e8400-e29b-41d4-a716-446655440000",
            reason="Policy violation",
        )
        assert cmd.request_id == "550e8400-e29b-41d4-a716-446655440000"
        assert cmd.reason == "Policy violation"

    def test_to_args(self):
        """Should convert to CLI arguments."""
        cmd = ApprovalRejectCommand(
            request_id="550e8400-e29b-41d4-a716-446655440000",
            reason="Policy violation",
        )
        args = cmd.to_args()
        assert args == [
            "system",
            "approval",
            "reject",
            "--request-id",
            "550e8400-e29b-41d4-a716-446655440000",
            "--reason",
            "Policy violation",
        ]


class TestComplianceStatusCommand:
    """Tests for ComplianceStatusCommand model."""

    def test_valid_command(self):
        """Should create compliance status command."""
        cmd = ComplianceStatusCommand(data_id="550e8400-e29b-41d4-a716-446655440000")
        assert cmd.data_id == "550e8400-e29b-41d4-a716-446655440000"

    def test_to_args(self):
        """Should convert to CLI arguments."""
        cmd = ComplianceStatusCommand(data_id="550e8400-e29b-41d4-a716-446655440000")
        args = cmd.to_args()
        assert args == [
            "compliance",
            "status",
            "--data-id",
            "550e8400-e29b-41d4-a716-446655440000",
        ]
