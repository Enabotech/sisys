"""Unit tests for UDMRConfig infrastructure configuration."""

from __future__ import annotations

import os
from unittest.mock import patch

from src.infrastructure.config.udmr import CloudModelConfig, UDMRConfig


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
        }
        with patch.dict(os.environ, env, clear=True):
            config = UDMRConfig.from_env()
        assert config.enabled is False
        assert config.local_first is False
        assert config.local_timeout == 60
        assert config.local_model == "llama3:8b"

    def test_cloud_configs_default(self) -> None:
        """Should have correct default cloud configs."""
        with patch.dict(os.environ, {}, clear=True):
            config = UDMRConfig.from_env()
        assert len(config.cloud_configs) == 3
        models = [c.model for c in config.cloud_configs]
        assert "qwen-turbo" in models
        assert "qwen-plus" in models
        assert "claude-3-haiku" in models

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


class TestCloudModelConfig:
    """Test suite for CloudModelConfig."""

    def test_cloud_model_config_is_frozen(self) -> None:
        """CloudModelConfig should be a frozen dataclass."""
        assert getattr(getattr(CloudModelConfig, "__dataclass_params__"), "frozen") is True

    def test_cloud_model_config_default_values(self) -> None:
        """CloudModelConfig should have correct default values."""
        config = CloudModelConfig()
        assert config.api_type == "openai"
        assert config.endpoint == ""
        assert config.api_key == ""
        assert config.model == ""
        assert config.enabled is True

    def test_cloud_model_config_custom_values(self) -> None:
        """CloudModelConfig should accept custom values."""
        config = CloudModelConfig(
            api_type="anthropic",
            endpoint="https://api.anthropic.com",
            api_key="sk-ant-key",
            model="claude-3-5-sonnet",
            enabled=False,
        )
        assert config.api_type == "anthropic"
        assert config.endpoint == "https://api.anthropic.com"
        assert config.api_key == "sk-ant-key"
        assert config.model == "claude-3-5-sonnet"
        assert config.enabled is False

    def test_cloud_model_config_equality(self) -> None:
        """CloudModelConfig instances with same values should be equal."""
        config1 = CloudModelConfig(api_type="openai", endpoint="https://api.openai.com", model="gpt-4")
        config2 = CloudModelConfig(api_type="openai", endpoint="https://api.openai.com", model="gpt-4")
        assert config1 == config2


class TestUDMRConfigCloudConfigs:
    """Test suite for UDMRConfig cloud_configs field."""

    def test_from_env_parses_single_cloud_config(self) -> None:
        """Should parse single cloud config from environment variables."""
        env = {
            "UDMR_CLOUD_0_API_TYPE": "custom",
            "UDMR_CLOUD_0_ENDPOINT": "https://api.minimax.chat/v1",
            "UDMR_CLOUD_0_API_KEY": "test-key",
            "UDMR_CLOUD_0_MODEL": "MiniMax-M2.7",
            "UDMR_CLOUD_0_ENABLED": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            config = UDMRConfig.from_env()
        assert len(config.cloud_configs) == 1
        cloud = config.cloud_configs[0]
        assert cloud.api_type == "custom"
        assert cloud.endpoint == "https://api.minimax.chat/v1"
        assert cloud.api_key == "test-key"
        assert cloud.model == "MiniMax-M2.7"
        assert cloud.enabled is True

    def test_from_env_parses_multiple_cloud_configs(self) -> None:
        """Should parse multiple cloud configs from environment variables."""
        env = {
            "UDMR_CLOUD_0_API_TYPE": "custom",
            "UDMR_CLOUD_0_ENDPOINT": "https://api.minimax.chat/v1",
            "UDMR_CLOUD_0_API_KEY": "minimax-key",
            "UDMR_CLOUD_0_MODEL": "MiniMax-M2.7",
            "UDMR_CLOUD_0_ENABLED": "true",
            "UDMR_CLOUD_1_API_TYPE": "openai",
            "UDMR_CLOUD_1_ENDPOINT": "https://api.deepseek.com/v1",
            "UDMR_CLOUD_1_API_KEY": "deepseek-key",
            "UDMR_CLOUD_1_MODEL": "deepseek-chat",
            "UDMR_CLOUD_1_ENABLED": "true",
            "UDMR_CLOUD_2_API_TYPE": "custom",
            "UDMR_CLOUD_2_ENDPOINT": "https://open.bigmodel.cn/api/paas/v4",
            "UDMR_CLOUD_2_API_KEY": "glm-key",
            "UDMR_CLOUD_2_MODEL": "glm-5.1",
            "UDMR_CLOUD_2_ENABLED": "false",
        }
        with patch.dict(os.environ, env, clear=True):
            config = UDMRConfig.from_env()
        assert len(config.cloud_configs) == 3

        assert config.cloud_configs[0].api_type == "custom"
        assert config.cloud_configs[0].model == "MiniMax-M2.7"
        assert config.cloud_configs[0].enabled is True

        assert config.cloud_configs[1].api_type == "openai"
        assert config.cloud_configs[1].model == "deepseek-chat"
        assert config.cloud_configs[1].enabled is True

        assert config.cloud_configs[2].api_type == "custom"
        assert config.cloud_configs[2].model == "glm-5.1"
        assert config.cloud_configs[2].enabled is False

    def test_from_env_disabled_cloud_config(self) -> None:
        """Should parse disabled cloud config correctly."""
        env = {
            "UDMR_CLOUD_0_API_TYPE": "openai",
            "UDMR_CLOUD_0_ENDPOINT": "https://api.openai.com/v1",
            "UDMR_CLOUD_0_API_KEY": "key",
            "UDMR_CLOUD_0_MODEL": "gpt-4",
            "UDMR_CLOUD_0_ENABLED": "false",
        }
        with patch.dict(os.environ, env, clear=True):
            config = UDMRConfig.from_env()
        assert len(config.cloud_configs) == 1
        assert config.cloud_configs[0].enabled is False

    def test_from_env_skips_gaps_in_cloud_config_indices(self) -> None:
        """Should stop at first missing cloud config index."""
        env = {
            "UDMR_CLOUD_0_API_TYPE": "openai",
            "UDMR_CLOUD_0_MODEL": "gpt-4",
            "UDMR_CLOUD_0_ENABLED": "true",
            "UDMR_CLOUD_2_API_TYPE": "anthropic",
            "UDMR_CLOUD_2_MODEL": "claude-3",
            "UDMR_CLOUD_2_ENABLED": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            config = UDMRConfig.from_env()
        assert len(config.cloud_configs) == 1
        assert config.cloud_configs[0].model == "gpt-4"

    def test_cloud_configs_filter_enabled(self) -> None:
        """Should filter enabled cloud configs correctly."""
        env = {
            "UDMR_CLOUD_0_API_TYPE": "openai",
            "UDMR_CLOUD_0_MODEL": "gpt-4",
            "UDMR_CLOUD_0_ENABLED": "true",
            "UDMR_CLOUD_1_API_TYPE": "anthropic",
            "UDMR_CLOUD_1_MODEL": "claude-3",
            "UDMR_CLOUD_1_ENABLED": "false",
        }
        with patch.dict(os.environ, env, clear=True):
            config = UDMRConfig.from_env()
        enabled_models = [c.model for c in config.cloud_configs if c.enabled]
        assert enabled_models == ["gpt-4"]