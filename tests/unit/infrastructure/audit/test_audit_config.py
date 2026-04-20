"""Test AuditConfig - Red Phase (Test First).

TDD Cycle: Red -> Green -> Refactor
Reference: Story 1.10 Task 0 - SDD Specification
Reference: Story 1.4-1.9 Config Pattern
"""

from __future__ import annotations

import os


class TestAuditConfigDefaults:
    """Test AuditConfig default values."""

    def test_create_config_with_defaults(self):
        """Can create config with default values."""
        from src.infrastructure.config.audit import AuditConfig

        config = AuditConfig()

        assert config.enabled is True
        assert config.storage_backend == "postgresql"
        assert config.retention_days == 2555  # 7 years
        assert config.archive_enabled is False
        assert config.worm_bucket == "audit-archives"
        assert config.outbox_poll_interval == 5
        assert config.outbox_batch_size == 100
        assert config.max_retries == 3
        assert config.checksum_algorithm == "sha256"
        assert config.page_size_default == 50
        assert config.page_size_max == 1000

    def test_create_config_with_custom_values(self):
        """Can create config with custom values."""
        from src.infrastructure.config.audit import AuditConfig

        config = AuditConfig(
            enabled=False,
            storage_backend="minio",
            retention_days=3650,
            archive_enabled=True,
        )

        assert config.enabled is False
        assert config.storage_backend == "minio"
        assert config.retention_days == 3650
        assert config.archive_enabled is True


class TestAuditConfigFromEnv:
    """Test AuditConfig.from_env() loading."""

    def test_from_env_loads_defaults_when_no_env(self):
        """from_env() returns defaults when no env vars set."""
        # Clear any existing env vars
        env_vars = [
            "AUDIT_ENABLED",
            "AUDIT_STORAGE_BACKEND",
            "AUDIT_RETENTION_DAYS",
            "AUDIT_ARCHIVE_ENABLED",
            "AUDIT_WORM_BUCKET",
        ]
        for var in env_vars:
            os.environ.pop(var, None)

        from src.infrastructure.config.audit import AuditConfig

        config = AuditConfig.from_env()

        assert config.enabled is True
        assert config.storage_backend == "postgresql"
        assert config.retention_days == 2555

    def test_from_env_loads_custom_values(self):
        """from_env() loads custom values from environment."""
        os.environ["AUDIT_ENABLED"] = "false"
        os.environ["AUDIT_STORAGE_BACKEND"] = "minio"
        os.environ["AUDIT_RETENTION_DAYS"] = "3650"
        os.environ["AUDIT_ARCHIVE_ENABLED"] = "true"
        os.environ["AUDIT_WORM_BUCKET"] = "custom-audit"
        os.environ["AUDIT_OUTBOX_POLL_INTERVAL"] = "10"
        os.environ["AUDIT_OUTBOX_BATCH_SIZE"] = "200"
        os.environ["AUDIT_MAX_RETRIES"] = "5"

        from src.infrastructure.config.audit import AuditConfig

        config = AuditConfig.from_env()

        assert config.enabled is False
        assert config.storage_backend == "minio"
        assert config.retention_days == 3650
        assert config.archive_enabled is True
        assert config.worm_bucket == "custom-audit"
        assert config.outbox_poll_interval == 10
        assert config.outbox_batch_size == 200
        assert config.max_retries == 5

    def test_from_env_parses_event_types(self):
        """from_env() parses comma-separated event types."""
        os.environ["AUDIT_EVENT_TYPES_ENABLED"] = "auth:login, auth:logout, doc:upload"

        from src.infrastructure.config.audit import AuditConfig

        config = AuditConfig.from_env()

        assert config.event_types_enabled == ["auth:login", "auth:logout", "doc:upload"]

    def test_from_env_handles_empty_event_types(self):
        """from_env() handles empty event types string."""
        os.environ["AUDIT_EVENT_TYPES_ENABLED"] = ""

        from src.infrastructure.config.audit import AuditConfig

        config = AuditConfig.from_env()

        assert config.event_types_enabled == []


class TestAuditConfigGlobalInstance:
    """Test get_audit_config() lazy loading."""

    def test_get_audit_config_returns_same_instance(self):
        """get_audit_config() returns singleton instance."""
        # Reset global
        import src.infrastructure.config.audit
        from src.infrastructure.config.audit import get_audit_config

        src.infrastructure.config.audit._audit_config = None

        config1 = get_audit_config()
        config2 = get_audit_config()

        assert config1 is config2
