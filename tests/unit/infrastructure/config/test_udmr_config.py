"""Unit tests for UDMRConfig infrastructure configuration."""

from __future__ import annotations

import os
from unittest.mock import patch

from src.infrastructure.config.udmr import UDMRConfig


class TestUDMRConfig:
    """Test suite for UDMRConfig."""

    def test_from_env_default_values(self) -> None:
        """Should have correct default values when env vars not set."""
        with patch.dict(os.environ, {}, clear=True):
            config = UDMRConfig.from_env()
        assert config.enabled is True
        assert config.local_first is True
        assert config.local_timeout == 30
        assert "qwen2.5:7b" in config.local_model

    def test_from_env_custom_values(self) -> None:
        """Should read custom values from environment variables."""
        env = {
            "UDMR_ENABLED": "false",
            "UDMR_LOCAL_FIRST": "false",
            "UDMR_LOCAL_TIMEOUT": "60",
            "UDMR_LOCAL_MODEL": "llama3:8b",
            "UDMR_CLOUD_MODELS": "gpt-4,claude-3",
        }
        with patch.dict(os.environ, env, clear=True):
            config = UDMRConfig.from_env()
        assert config.enabled is False
        assert config.local_first is False
        assert config.local_timeout == 60
        assert config.local_model == "llama3:8b"
        assert config.cloud_models == ["gpt-4", "claude-3"]

    def test_cloud_models_default(self) -> None:
        """Should have correct default cloud models."""
        with patch.dict(os.environ, {}, clear=True):
            config = UDMRConfig.from_env()
        assert len(config.cloud_models) > 0

    def test_local_model_default(self) -> None:
        """Should have correct default local model."""
        with patch.dict(os.environ, {}, clear=True):
            config = UDMRConfig.from_env()
        assert config.local_model == "qwen2.5:7b"

    def test_from_env_negative_timeout_defaults_to_30(self) -> None:
        """Negative local_timeout should default to 30."""
        env = {"UDMR_LOCAL_TIMEOUT": "-5"}
        with patch.dict(os.environ, env, clear=True):
            config = UDMRConfig.from_env()
        assert config.local_timeout == 30

    def test_from_env_invalid_local_timeout_defaults_to_30(self) -> None:
        """Invalid UDMR_LOCAL_TIMEOUT should default to 30 (no error raised)."""
        env = {"UDMR_LOCAL_TIMEOUT": "not_a_number"}
        with patch.dict(os.environ, env, clear=True):
            config = UDMRConfig.from_env()
        assert config.local_timeout == 30

    def test_from_env_zero_timeout_is_allowed(self) -> None:
        """Zero local_timeout is allowed (only negative is clamped to default)."""
        env = {"UDMR_LOCAL_TIMEOUT": "0"}
        with patch.dict(os.environ, env, clear=True):
            config = UDMRConfig.from_env()
        assert config.local_timeout == 0
