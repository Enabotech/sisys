"""CLI Commands: 等保 2.0 Level 3 Compliance Commands.

Reference: Story 1.12 等保 2.0 三级基础要求

CLI Commands:
- sisys system mfa enable --user-id <id>
- sisys system mfa verify --user-id <id> --code <code>
- sisys compliance status --level 3
- sisys system backup create --type full|incremental
- sisys system backup restore --backup-id <id>
- sisys system integrity check --data-type <type>

Usage Examples:
    sisys system mfa enable --user-id 550e8400-e29b-41d4-a716-446655440000
    sisys system mfa verify --user-id 550e8400-e29b-41d4-a716-446655440000 --code 123456
    sisys compliance status --level 3
    sisys system backup create --type full
    sisys system backup create --type incremental --base-backup-id 550e8400-e29b-41d4-a716-446655440000
    sisys system backup restore --backup-id 550e8400-e29b-41d4-a716-446655440000
    sisys system integrity check --data-type document
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class MFAEnableCommand:
    """Command: sisys system mfa enable.

    Enable MFA for a user.

    Attributes:
        user_id: UUID of the user.
        username: Username for authenticator app display (optional).
    """

    user_id: str
    username: str = ""

    def to_args(self) -> list[str]:
        """Convert to CLI argument list.

        Returns:
            list[str]: CLI arguments.
        """
        args = [
            "system",
            "mfa",
            "enable",
            "--user-id",
            self.user_id,
        ]
        if self.username:
            args.extend(["--username", self.username])
        return args


@dataclass
class MFAVerifyCommand:
    """Command: sisys system mfa verify.

    Verify MFA code for a user.

    Attributes:
        user_id: UUID of the user.
        code: TOTP code from authenticator app.
    """

    user_id: str
    code: str

    def to_args(self) -> list[str]:
        """Convert to CLI argument list.

        Returns:
            list[str]: CLI arguments.
        """
        return [
            "system",
            "mfa",
            "verify",
            "--user-id",
            self.user_id,
            "--code",
            self.code,
        ]


@dataclass
class ComplianceStatusCommand:
    """Command: sisys compliance status.

    Check compliance status.

    Attributes:
        level: Compliance level (default: 3 for 等保 2.0 三级).
    """

    level: int = 3

    def to_args(self) -> list[str]:
        """Convert to CLI argument list.

        Returns:
            list[str]: CLI arguments.
        """
        return [
            "compliance",
            "status",
            "--level",
            str(self.level),
        ]


@dataclass
class BackupCreateCommand:
    """Command: sisys system backup create.

    Create a backup.

    Attributes:
        backup_type: Type of backup (full or incremental).
        base_backup_id: UUID of base backup for incremental backup (optional).
        description: Optional backup description.
    """

    backup_type: str = "full"
    base_backup_id: str = ""
    description: str = ""

    def to_args(self) -> list[str]:
        """Convert to CLI argument list.

        Returns:
            list[str]: CLI arguments.
        """
        args = [
            "system",
            "backup",
            "create",
            "--type",
            self.backup_type,
        ]
        if self.base_backup_id:
            args.extend(["--base-backup-id", self.base_backup_id])
        if self.description:
            args.extend(["--description", self.description])
        return args


@dataclass
class BackupRestoreCommand:
    """Command: sisys system backup restore.

    Restore from a backup.

    Attributes:
        backup_id: UUID of backup to restore from.
        target_path: Target path for restored data (optional).
    """

    backup_id: str
    target_path: str = ""

    def to_args(self) -> list[str]:
        """Convert to CLI argument list.

        Returns:
            list[str]: CLI arguments.
        """
        args = [
            "system",
            "backup",
            "restore",
            "--backup-id",
            self.backup_id,
        ]
        if self.target_path:
            args.extend(["--target-path", self.target_path])
        return args


@dataclass
class IntegrityCheckCommand:
    """Command: sisys system integrity check.

    Check data integrity.

    Attributes:
        data_type: Type of data to check (document, config, etc.).
        data_id: UUID of specific data to check (optional).
    """

    data_type: str = "document"
    data_id: str = ""

    def to_args(self) -> list[str]:
        """Convert to CLI argument list.

        Returns:
            list[str]: CLI arguments.
        """
        args = [
            "system",
            "integrity",
            "check",
            "--data-type",
            self.data_type,
        ]
        if self.data_id:
            args.extend(["--data-id", self.data_id])
        return args


# Command registry for CLI parsing
EQUILIBRIUM_COMMANDS = {
    "mfa_enable": MFAEnableCommand,
    "mfa_verify": MFAVerifyCommand,
    "compliance_status": ComplianceStatusCommand,
    "backup_create": BackupCreateCommand,
    "backup_restore": BackupRestoreCommand,
    "integrity_check": IntegrityCheckCommand,
}


def parse_equilibrium_command(command_name: str, args: dict[str, Any]) -> Any:
    """Parse CLI arguments into command object.

    Args:
        command_name: Name of the command.
        args: CLI arguments dict.

    Returns:
        Command object instance.

    Raises:
        ValueError: If command not found or arguments invalid.
    """
    command_class = EQUILIBRIUM_COMMANDS.get(command_name)
    if command_class is None:
        raise ValueError(f"Unknown command: {command_name}")

    return command_class(**args)
