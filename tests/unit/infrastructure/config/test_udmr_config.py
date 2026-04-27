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
