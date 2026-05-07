"""Unit tests for AutoTriggerConfig."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from src.infrastructure.config.auto_trigger import AutoTriggerConfig


class TestAutoTriggerConfigDefaults:
    """Test AutoTriggerConfig default values."""

    def test_default_trigger_enabled(self) -> None:
        """Should have default trigger_enabled=True."""
        config = AutoTriggerConfig()
        assert config.trigger_enabled is True

    def test_default_heartbeat_interval(self) -> None:
        """Should have default heartbeat_interval_seconds=60."""
        config = AutoTriggerConfig()
        assert config.heartbeat_interval_seconds == 60

    def test_default_max_retries(self) -> None:
        """Should have default trigger_max_retries=3."""
        config = AutoTriggerConfig()
        assert config.trigger_max_retries == 3


class TestAutoTriggerConfigFromEnv:
    """Test AutoTriggerConfig.from_env method."""

    def test_from_env_defaults(self) -> None:
        """Should use default values when env vars not set."""
        with patch.dict(os.environ, {}, clear=True):
            config = AutoTriggerConfig.from_env()
        assert config.trigger_enabled is True
        assert config.heartbeat_interval_seconds == 60
        assert config.trigger_max_retries == 3

    def test_from_env_trigger_disabled(self) -> None:
        """Should parse TRIGGER_ENABLED=false."""
        env = {"TRIGGER_ENABLED": "false"}
        with patch.dict(os.environ, env, clear=True):
            config = AutoTriggerConfig.from_env()
        assert config.trigger_enabled is False

    def test_from_env_trigger_enabled_variations(self) -> None:
        """Should accept true/1/yes/on as enabled."""
        for value in ("true", "TRUE", "1", "yes", "YES", "on"):
            env = {"TRIGGER_ENABLED": value}
            with patch.dict(os.environ, env, clear=True):
                config = AutoTriggerConfig.from_env()
            assert config.trigger_enabled is True, f"Failed for {value}"

    def test_from_env_trigger_disabled_variations(self) -> None:
        """Should accept false/0/no/off as disabled."""
        for value in ("false", "FALSE", "0", "no", "NO", "off"):
            env = {"TRIGGER_ENABLED": value}
            with patch.dict(os.environ, env, clear=True):
                config = AutoTriggerConfig.from_env()
            assert config.trigger_enabled is False, f"Failed for {value}"

    def test_from_env_custom_heartbeat_interval(self) -> None:
        """Should parse custom HEARTBEAT_INTERVAL_SECONDS."""
        env = {"HEARTBEAT_INTERVAL_SECONDS": "120"}
        with patch.dict(os.environ, env, clear=True):
            config = AutoTriggerConfig.from_env()
        assert config.heartbeat_interval_seconds == 120

    def test_from_env_invalid_heartbeat_interval_raises(self) -> None:
        """Should raise ValueError for invalid HEARTBEAT_INTERVAL_SECONDS."""
        env = {"HEARTBEAT_INTERVAL_SECONDS": "not_a_number"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="Invalid HEARTBEAT_INTERVAL_SECONDS"):
                AutoTriggerConfig.from_env()

    def test_from_env_zero_heartbeat_interval_raises(self) -> None:
        """Should raise ValueError when HEARTBEAT_INTERVAL_SECONDS is zero."""
        env = {"HEARTBEAT_INTERVAL_SECONDS": "0"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="Invalid HEARTBEAT_INTERVAL_SECONDS"):
                AutoTriggerConfig.from_env()

    def test_from_env_negative_heartbeat_interval_raises(self) -> None:
        """Should raise ValueError when HEARTBEAT_INTERVAL_SECONDS is negative."""
        env = {"HEARTBEAT_INTERVAL_SECONDS": "-10"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="Invalid HEARTBEAT_INTERVAL_SECONDS"):
                AutoTriggerConfig.from_env()

    def test_from_env_custom_max_retries(self) -> None:
        """Should parse custom TRIGGER_MAX_RETRIES."""
        env = {"TRIGGER_MAX_RETRIES": "5"}
        with patch.dict(os.environ, env, clear=True):
            config = AutoTriggerConfig.from_env()
        assert config.trigger_max_retries == 5

    def test_from_env_zero_max_retries(self) -> None:
        """Should allow TRIGGER_MAX_RETRIES=0."""
        env = {"TRIGGER_MAX_RETRIES": "0"}
        with patch.dict(os.environ, env, clear=True):
            config = AutoTriggerConfig.from_env()
        assert config.trigger_max_retries == 0

    def test_from_env_negative_max_retries_raises(self) -> None:
        """Should raise ValueError when TRIGGER_MAX_RETRIES is negative."""
        env = {"TRIGGER_MAX_RETRIES": "-1"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="Invalid TRIGGER_MAX_RETRIES"):
                AutoTriggerConfig.from_env()

    def test_from_env_invalid_max_retries_raises(self) -> None:
        """Should raise ValueError for invalid TRIGGER_MAX_RETRIES."""
        env = {"TRIGGER_MAX_RETRIES": "not_a_number"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="Invalid TRIGGER_MAX_RETRIES"):
                AutoTriggerConfig.from_env()
