"""Tests for AutoExecuteConfig configuration."""

import os
from unittest.mock import patch

from src.infrastructure.config.auto_execute import AutoExecuteConfig


class TestAutoExecuteConfig:
    """TDD tests for AutoExecuteConfig."""

    def test_default_values(self) -> None:
        """RED: AutoExecuteConfig should have sensible defaults."""
        config = AutoExecuteConfig()

        assert config.enabled is True
        assert config.sandbox_type == "docker"
        assert config.snapshot_ttl_seconds == 86400  # 24 hours
        assert config.resource_limits is None

    def test_from_env_with_defaults(self) -> None:
        """RED: from_env should return defaults when env vars not set."""
        with patch.dict(os.environ, {}, clear=True):
            config = AutoExecuteConfig.from_env()

        assert config.enabled is True
        assert config.sandbox_type == "docker"
        assert config.snapshot_ttl_seconds == 86400

    def test_from_env_parses_enabled(self) -> None:
        """RED: from_env should parse EXECUTE_ENABLED env var."""
        with patch.dict(os.environ, {"EXECUTE_ENABLED": "false"}):
            config = AutoExecuteConfig.from_env()

        assert config.enabled is False

    def test_from_env_parses_sandbox_type(self) -> None:
        """RED: from_env should parse SANDBOX_TYPE env var."""
        with patch.dict(os.environ, {"SANDBOX_TYPE": "gvisor"}):
            config = AutoExecuteConfig.from_env()

        assert config.sandbox_type == "gvisor"

    def test_from_env_parses_snapshot_ttl(self) -> None:
        """RED: from_env should parse SNAPSHOT_TTL_SECONDS env var."""
        with patch.dict(os.environ, {"SNAPSHOT_TTL_SECONDS": "3600"}):
            config = AutoExecuteConfig.from_env()

        assert config.snapshot_ttl_seconds == 3600

    def test_from_env_parses_resource_limits(self) -> None:
        """RED: from_env should parse RESOURCE_LIMITS as JSON."""
        with patch.dict(os.environ, {"RESOURCE_LIMITS": '{"cpu": 2, "memory": "1g"}'}):
            config = AutoExecuteConfig.from_env()

        assert config.resource_limits is not None
        assert config.resource_limits["cpu"] == 2
        assert config.resource_limits["memory"] == "1g"

    def test_validate_accepts_valid_config(self) -> None:
        """RED: validate should return True for valid config."""
        config = AutoExecuteConfig(
            enabled=True,
            sandbox_type="docker",
            snapshot_ttl_seconds=86400,
        )

        assert config.validate() is True

    def test_validate_rejects_invalid_sandbox_type(self) -> None:
        """RED: validate should return False for invalid sandbox_type."""
        config = AutoExecuteConfig(sandbox_type="invalid")

        assert config.validate() is False

    def test_validate_rejects_ttl_too_short(self) -> None:
        """RED: validate should return False for TTL < 60 seconds."""
        config = AutoExecuteConfig(snapshot_ttl_seconds=30)

        assert config.validate() is False

    def test_validate_rejects_ttl_too_long(self) -> None:
        """RED: validate should return False for TTL > 30 days."""
        config = AutoExecuteConfig(snapshot_ttl_seconds=3000000)  # > 30 days

        assert config.validate() is False
