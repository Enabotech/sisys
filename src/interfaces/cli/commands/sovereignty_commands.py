"""CLI Contract: Data Sovereignty Commands.

Reference: Story 1.11 Data Sovereignty Isolation.

CLI Commands:
- sisys system whitelist add --endpoint <url> --provider <name> --purpose <desc>
- sisys system whitelist revoke --rule-id <id>
- sisys system whitelist list --status <status>
- sisys system approval list --status <status>
- sisys system approval approve --request-id <id>
- sisys system approval reject --request-id <id> --reason <reason>
- sisys compliance status --data-id <id>

Usage Examples:
    sisys system whitelist add --endpoint https://api.example.com --provider ExampleAPI --purpose "数据同步"
    sisys system whitelist revoke --rule-id 550e8400-e29b-41d4-a716-446655440000
    sisys system whitelist list --status active
    sisys system approval list --status pending
    sisys system approval approve --request-id 550e8400-e29b-41d4-a716-446655440000
    sisys system approval reject --request-id 550e8400-e29b-41d4-a716-446655440000 --reason "不合规"
    sisys compliance status --data-id 550e8400-e29b-41d4-a716-446655440000
"""

from __future__ import annotations

from dataclasses import dataclass

from src.infrastructure.security.models import ApprovalStatus, WhitelistStatus


@dataclass
class WhitelistAddCommand:
    """Command: sisys system whitelist add.

    Add a new external API call whitelist rule.

    Attributes:
        endpoint: External API endpoint URL pattern.
        provider: Service provider name.
        purpose: Purpose/description of the external call.
        risk_level: Risk level (low, medium, high, critical). Default: medium.
        expiry_days: Number of days until rule expires. Default: 0 (no expiration).
    """

    endpoint: str
    provider: str
    purpose: str = ""
    risk_level: str = "medium"
    expiry_days: int = 0

    def to_args(self) -> list[str]:
        """Convert to CLI argument list.

        Returns:
            list[str]: CLI arguments.
        """
        args = [
            "system",
            "whitelist",
            "add",
            "--endpoint",
            self.endpoint,
            "--provider",
            self.provider,
        ]
        if self.purpose:
            args.extend(["--purpose", self.purpose])
        if self.risk_level != "medium":
            args.extend(["--risk-level", self.risk_level])
        if self.expiry_days > 0:
            args.extend(["--expiry-days", str(self.expiry_days)])
        return args


@dataclass
class WhitelistRevokeCommand:
    """Command: sisys system whitelist revoke.

    Revoke an existing whitelist rule.

    Attributes:
        rule_id: UUID of the whitelist rule to revoke.
        reason: Reason for revoking the rule.
    """

    rule_id: str
    reason: str = ""

    def to_args(self) -> list[str]:
        """Convert to CLI argument list.

        Returns:
            list[str]: CLI arguments.
        """
        args = [
            "system",
            "whitelist",
            "revoke",
            "--rule-id",
            self.rule_id,
        ]
        if self.reason:
            args.extend(["--reason", self.reason])
        return args


@dataclass
class WhitelistListCommand:
    """Command: sisys system whitelist list.

    List whitelist rules with optional status filter.

    Attributes:
        status: Filter by status (active, pending, revoked, expired).
    """

    status: WhitelistStatus | None = None

    def to_args(self) -> list[str]:
        """Convert to CLI argument list.

        Returns:
            list[str]: CLI arguments.
        """
        args = ["system", "whitelist", "list"]
        if self.status:
            args.extend(["--status", self.status.value])
        return args


@dataclass
class ApprovalListCommand:
    """Command: sisys system approval list.

    List cross-border approval requests with optional status filter.

    Attributes:
        status: Filter by status (pending, approved, rejected, expired).
    """

    status: ApprovalStatus | None = None

    def to_args(self) -> list[str]:
        """Convert to CLI argument list.

        Returns:
            list[str]: CLI arguments.
        """
        args = ["system", "approval", "list"]
        if self.status:
            args.extend(["--status", self.status.value])
        return args


@dataclass
class ApprovalApproveCommand:
    """Command: sisys system approval approve.

    Approve a cross-border transfer request.

    Attributes:
        request_id: UUID of the approval request to approve.
    """

    request_id: str

    def to_args(self) -> list[str]:
        """Convert to CLI argument list.

        Returns:
            list[str]: CLI arguments.
        """
        return [
            "system",
            "approval",
            "approve",
            "--request-id",
            self.request_id,
        ]


@dataclass
class ApprovalRejectCommand:
    """Command: sisys system approval reject.

    Reject a cross-border transfer request.

    Attributes:
        request_id: UUID of the approval request to reject.
        reason: Rejection reason (required).
    """

    request_id: str
    reason: str

    def to_args(self) -> list[str]:
        """Convert to CLI argument list.

        Returns:
            list[str]: CLI arguments.
        """
        return [
            "system",
            "approval",
            "reject",
            "--request-id",
            self.request_id,
            "--reason",
            self.reason,
        ]


@dataclass
class ComplianceStatusCommand:
    """Command: sisys compliance status.

    Query compliance status for a specific data item.

    Attributes:
        data_id: UUID of the data item to check.
    """

    data_id: str

    def to_args(self) -> list[str]:
        """Convert to CLI argument list.

        Returns:
            list[str]: CLI arguments.
        """
        return [
            "compliance",
            "status",
            "--data-id",
            self.data_id,
        ]
