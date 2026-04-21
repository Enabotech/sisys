"""Tests for equilibrium CLI command models.

Tests Pydantic/dataclass models for CLI command validation.
Reference: Story 1.12 等保 2.0 Level 3 Compliance.
"""

from __future__ import annotations

from uuid import uuid4

from src.interfaces.cli.equilibrium_commands import (
    EQUILIBRIUM_COMMANDS,
    BackupCreateCommand,
    BackupRestoreCommand,
    ComplianceStatusCommand,
    IntegrityCheckCommand,
    MFAEnableCommand,
    MFAVerifyCommand,
    parse_equilibrium_command,
)


class TestMFAEnableCommand:
    """Tests for MFAEnableCommand model."""

    def test_valid_command_required_fields(self):
        """Should create with required fields."""
        user_id = str(uuid4())
        cmd = MFAEnableCommand(user_id=user_id)
        assert cmd.user_id == user_id
        assert cmd.username == ""

    def test_valid_command_all_fields(self):
        """Should create with all fields."""
        user_id = str(uuid4())
        cmd = MFAEnableCommand(user_id=user_id, username="testuser")
        assert cmd.username == "testuser"

    def test_to_args_basic(self):
        """Should convert to CLI arguments."""
        user_id = str(uuid4())
        cmd = MFAEnableCommand(user_id=user_id)
        args = cmd.to_args()
        assert args == ["system", "mfa", "enable", "--user-id", user_id]

    def test_to_args_with_username(self):
        """Should include username in CLI arguments."""
        user_id = str(uuid4())
        cmd = MFAEnableCommand(user_id=user_id, username="testuser")
        args = cmd.to_args()
        assert "--username" in args
        assert "testuser" in args


class TestMFAVerifyCommand:
    """Tests for MFAVerifyCommand model."""

    def test_valid_command(self):
        """Should create with required fields."""
        user_id = str(uuid4())
        cmd = MFAVerifyCommand(user_id=user_id, code="123456")
        assert cmd.user_id == user_id
        assert cmd.code == "123456"

    def test_to_args(self):
        """Should convert to CLI arguments."""
        user_id = str(uuid4())
        cmd = MFAVerifyCommand(user_id=user_id, code="123456")
        args = cmd.to_args()
        assert args == [
            "system",
            "mfa",
            "verify",
            "--user-id",
            user_id,
            "--code",
            "123456",
        ]


class TestComplianceStatusCommand:
    """Tests for ComplianceStatusCommand model."""

    def test_default_level(self):
        """Should use default level 3."""
        cmd = ComplianceStatusCommand()
        assert cmd.level == 3

    def test_custom_level(self):
        """Should accept custom level."""
        cmd = ComplianceStatusCommand(level=2)
        assert cmd.level == 2

    def test_to_args_default(self):
        """Should convert to CLI arguments with default level."""
        cmd = ComplianceStatusCommand()
        args = cmd.to_args()
        assert args == ["compliance", "status", "--level", "3"]

    def test_to_args_custom_level(self):
        """Should convert to CLI arguments with custom level."""
        cmd = ComplianceStatusCommand(level=2)
        args = cmd.to_args()
        assert args == ["compliance", "status", "--level", "2"]


class TestBackupCreateCommand:
    """Tests for BackupCreateCommand model."""

    def test_default_values(self):
        """Should use default values."""
        cmd = BackupCreateCommand()
        assert cmd.backup_type == "full"
        assert cmd.base_backup_id == ""
        assert cmd.description == ""

    def test_full_backup(self):
        """Should create full backup command."""
        cmd = BackupCreateCommand(backup_type="full")
        args = cmd.to_args()
        assert "--type" in args
        assert "full" in args

    def test_incremental_backup_with_base(self):
        """Should create incremental backup command with base."""
        base_id = str(uuid4())
        cmd = BackupCreateCommand(
            backup_type="incremental",
            base_backup_id=base_id,
            description="Test backup",
        )
        args = cmd.to_args()
        assert "incremental" in args
        assert "--base-backup-id" in args
        assert base_id in args
        assert "--description" in args
        assert "Test backup" in args

    def test_to_args_without_optional(self):
        """Should convert to CLI arguments without optional fields."""
        cmd = BackupCreateCommand()
        args = cmd.to_args()
        assert args == ["system", "backup", "create", "--type", "full"]
        assert "--base-backup-id" not in args
        assert "--description" not in args


class TestBackupRestoreCommand:
    """Tests for BackupRestoreCommand model."""

    def test_valid_command(self):
        """Should create with required fields."""
        backup_id = str(uuid4())
        cmd = BackupRestoreCommand(backup_id=backup_id)
        assert cmd.backup_id == backup_id
        assert cmd.target_path == ""

    def test_with_target_path(self):
        """Should create with target path."""
        backup_id = str(uuid4())
        cmd = BackupRestoreCommand(backup_id=backup_id, target_path="/tmp/restored")
        assert cmd.target_path == "/tmp/restored"

    def test_to_args_basic(self):
        """Should convert to CLI arguments."""
        backup_id = str(uuid4())
        cmd = BackupRestoreCommand(backup_id=backup_id)
        args = cmd.to_args()
        assert args == ["system", "backup", "restore", "--backup-id", backup_id]

    def test_to_args_with_target_path(self):
        """Should include target path in CLI arguments."""
        backup_id = str(uuid4())
        cmd = BackupRestoreCommand(backup_id=backup_id, target_path="/tmp/restored")
        args = cmd.to_args()
        assert "--target-path" in args
        assert "/tmp/restored" in args


class TestIntegrityCheckCommand:
    """Tests for IntegrityCheckCommand model."""

    def test_default_values(self):
        """Should use default values."""
        cmd = IntegrityCheckCommand()
        assert cmd.data_type == "document"
        assert cmd.data_id == ""

    def test_with_data_id(self):
        """Should create with data_id."""
        data_id = str(uuid4())
        cmd = IntegrityCheckCommand(data_id=data_id)
        assert cmd.data_id == data_id

    def test_to_args_default(self):
        """Should convert to CLI arguments with defaults."""
        cmd = IntegrityCheckCommand()
        args = cmd.to_args()
        assert args == ["system", "integrity", "check", "--data-type", "document"]
        assert "--data-id" not in args

    def test_to_args_with_data_id(self):
        """Should include data_id in CLI arguments."""
        data_id = str(uuid4())
        cmd = IntegrityCheckCommand(data_id=data_id)
        args = cmd.to_args()
        assert "--data-id" in args
        assert data_id in args


class TestCommandRegistry:
    """Tests for command registry and parsing."""

    def test_command_registry_has_all_commands(self):
        """Should have all expected commands."""
        assert "mfa_enable" in EQUILIBRIUM_COMMANDS
        assert "mfa_verify" in EQUILIBRIUM_COMMANDS
        assert "compliance_status" in EQUILIBRIUM_COMMANDS
        assert "backup_create" in EQUILIBRIUM_COMMANDS
        assert "backup_restore" in EQUILIBRIUM_COMMANDS
        assert "integrity_check" in EQUILIBRIUM_COMMANDS

    def test_parse_mfa_enable(self):
        """Should parse mfa_enable command."""
        user_id = str(uuid4())
        cmd = parse_equilibrium_command("mfa_enable", {"user_id": user_id})
        assert isinstance(cmd, MFAEnableCommand)
        assert cmd.user_id == user_id

    def test_parse_mfa_verify(self):
        """Should parse mfa_verify command."""
        user_id = str(uuid4())
        cmd = parse_equilibrium_command(
            "mfa_verify",
            {"user_id": user_id, "code": "123456"},
        )
        assert isinstance(cmd, MFAVerifyCommand)
        assert cmd.code == "123456"

    def test_parse_compliance_status(self):
        """Should parse compliance_status command."""
        cmd = parse_equilibrium_command("compliance_status", {"level": 3})
        assert isinstance(cmd, ComplianceStatusCommand)
        assert cmd.level == 3

    def test_parse_backup_create_full(self):
        """Should parse backup_create command for full."""
        cmd = parse_equilibrium_command("backup_create", {"backup_type": "full"})
        assert isinstance(cmd, BackupCreateCommand)
        assert cmd.backup_type == "full"

    def test_parse_backup_create_incremental(self):
        """Should parse backup_create command for incremental."""
        base_id = str(uuid4())
        cmd = parse_equilibrium_command(
            "backup_create",
            {"backup_type": "incremental", "base_backup_id": base_id},
        )
        assert isinstance(cmd, BackupCreateCommand)
        assert cmd.backup_type == "incremental"
        assert cmd.base_backup_id == base_id

    def test_parse_backup_restore(self):
        """Should parse backup_restore command."""
        backup_id = str(uuid4())
        cmd = parse_equilibrium_command(
            "backup_restore",
            {"backup_id": backup_id, "target_path": "/tmp/restored"},
        )
        assert isinstance(cmd, BackupRestoreCommand)
        assert cmd.backup_id == backup_id

    def test_parse_integrity_check(self):
        """Should parse integrity_check command."""
        data_id = str(uuid4())
        cmd = parse_equilibrium_command(
            "integrity_check",
            {"data_type": "document", "data_id": data_id},
        )
        assert isinstance(cmd, IntegrityCheckCommand)
        assert cmd.data_id == data_id

    def test_parse_unknown_command_raises(self):
        """Should raise ValueError for unknown command."""
        from pytest import raises

        with raises(ValueError, match="Unknown command"):
            parse_equilibrium_command("unknown_command", {})
