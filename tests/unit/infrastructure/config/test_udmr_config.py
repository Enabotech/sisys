"""Unit tests for UDMRConfig and CloudModelConfig."""

from __future__ import annotations

import os
from typing import Any, cast
from unittest.mock import patch

import pytest

from src.domain.exceptions import ConfigurationError
from src.infrastructure.config.udmr import CloudModelConfig, UDMRConfig

# ===================================================================
# CloudModelConfig 测试
# ===================================================================


class TestCloudModelConfig:
    """CloudModelConfig 单元测试."""

    def test_default_values(self) -> None:
        """默认值应正确."""
        cfg = CloudModelConfig()
        assert cfg.api_type == "openai"
        assert cfg.endpoint == ""
        assert cfg.api_key == ""
        assert cfg.model == ""
        assert cfg.enabled is True
        assert cfg.max_tokens is None
        assert cfg.temperature == 0.7
        assert cfg.price_per_input_1k_tokens == 0.02
        assert cfg.price_per_output_1k_tokens == 0.02

    def test_frozen(self) -> None:
        """应为不可变 dataclass."""
        cfg = CloudModelConfig()
        with pytest.raises(AttributeError):
            cast(Any, cfg).api_type = "anthropic"

    def test_api_type_literal_values(self) -> None:
        """api_type 应接受合法值."""
        for t in ("openai", "anthropic", "openai_responses"):
            cfg = CloudModelConfig(api_type=t)
            assert cfg.api_type == t

    def test_custom_values(self) -> None:
        """自定义值应正确."""
        cfg = CloudModelConfig(
            api_type="anthropic",
            endpoint="https://api.minimax.chat/anthropic",
            api_key="TESTING_DUMMY_KEY",
            model="MiniMax-M2.7",
            enabled=False,
            max_tokens=4096,
            temperature=0.5,
        )
        assert cfg.api_type == "anthropic"
        assert cfg.endpoint == "https://api.minimax.chat/anthropic"
        assert cfg.api_key == "TESTING_DUMMY_KEY"
        assert cfg.model == "MiniMax-M2.7"
        assert cfg.enabled is False
        assert cfg.max_tokens == 4096
        assert cfg.temperature == 0.5


# ===================================================================
# UDMRConfig 测试
# ===================================================================


class TestUDMRConfig:
    """UDMRConfig 单元测试."""

    def test_default_values(self) -> None:
        """默认值应正确."""
        cfg = UDMRConfig()
        assert cfg.enabled is True
        assert cfg.local_first is False
        assert cfg.local_model == "qwen2.5:7b"
        assert cfg.llm_timeout == 600
        assert cfg.healthcheck_interval == 300
        assert cfg.cloud_configs == []

    def test_frozen(self) -> None:
        """应为不可变 dataclass."""
        cfg = UDMRConfig()
        with pytest.raises(AttributeError):
            cast(Any, cfg).enabled = False

    def test_from_env_defaults(self) -> None:
        """环境变量未设置时应使用默认值."""
        with patch.dict(os.environ, {}, clear=True):
            cfg = UDMRConfig.from_env()
        assert cfg.enabled is True
        assert cfg.local_first is False
        assert cfg.local_model == "qwen2.5:7b"
        assert cfg.llm_timeout == 600
        assert cfg.healthcheck_interval == 300
        assert cfg.cloud_configs == []

    def test_from_env_enabled_false(self) -> None:
        """UDMR_ENABLED=false."""
        with patch.dict(os.environ, {"UDMR_ENABLED": "false"}, clear=True):
            cfg = UDMRConfig.from_env()
        assert cfg.enabled is False

    def test_from_env_enabled_variations(self) -> None:
        """接受 true/1/yes/on 为启用."""
        for v in ("true", "1", "yes", "on"):
            with patch.dict(os.environ, {"UDMR_ENABLED": v}, clear=True):
                cfg = UDMRConfig.from_env()
            assert cfg.enabled is True, f"Failed for {v}"

    def test_from_env_disabled_variations(self) -> None:
        """接受 false/0/no/off 为禁用."""
        for v in ("false", "0", "no", "off"):
            with patch.dict(os.environ, {"UDMR_ENABLED": v}, clear=True):
                cfg = UDMRConfig.from_env()
            assert cfg.enabled is False, f"Failed for {v}"

    def test_from_env_local_first_true(self) -> None:
        """UDMR_LOCAL_FIRST=true."""
        with patch.dict(os.environ, {"UDMR_LOCAL_FIRST": "true"}, clear=True):
            cfg = UDMRConfig.from_env()
        assert cfg.local_first is True

    def test_from_env_custom_local_model(self) -> None:
        """UDMR_LOCAL_MODEL."""
        with patch.dict(os.environ, {"UDMR_LOCAL_MODEL": "llama3:8b"}, clear=True):
            cfg = UDMRConfig.from_env()
        assert cfg.local_model == "llama3:8b"

    def test_from_env_custom_timeout(self) -> None:
        """UDMR_LLM_TIMEOUT."""
        with patch.dict(os.environ, {"UDMR_LLM_TIMEOUT": "300"}, clear=True):
            cfg = UDMRConfig.from_env()
        assert cfg.llm_timeout == 300

    def test_from_env_invalid_timeout_raises(self) -> None:
        """无效 UDMR_LLM_TIMEOUT 应抛异常."""
        with patch.dict(os.environ, {"UDMR_LLM_TIMEOUT": "abc"}, clear=True):
            with pytest.raises(ConfigurationError, match="UDMR_LLM_TIMEOUT"):
                UDMRConfig.from_env()

    def test_from_env_zero_timeout_raises(self) -> None:
        """零超时应抛异常."""
        with patch.dict(os.environ, {"UDMR_LLM_TIMEOUT": "0"}, clear=True):
            with pytest.raises(ConfigurationError, match="UDMR_LLM_TIMEOUT"):
                UDMRConfig.from_env()

    def test_from_env_negative_timeout_raises(self) -> None:
        """负超时应抛异常."""
        with patch.dict(os.environ, {"UDMR_LLM_TIMEOUT": "-1"}, clear=True):
            with pytest.raises(ConfigurationError, match="UDMR_LLM_TIMEOUT"):
                UDMRConfig.from_env()

    def test_from_env_custom_healthcheck(self) -> None:
        """UDMR_HEALTHCHECK_INTERVAL."""
        with patch.dict(os.environ, {"UDMR_HEALTHCHECK_INTERVAL": "600"}, clear=True):
            cfg = UDMRConfig.from_env()
        assert cfg.healthcheck_interval == 600

    def test_from_env_invalid_healthcheck_raises(self) -> None:
        """无效健康检查间隔应抛异常."""
        with patch.dict(os.environ, {"UDMR_HEALTHCHECK_INTERVAL": "abc"}, clear=True):
            with pytest.raises(ConfigurationError, match="UDMR_HEALTHCHECK_INTERVAL"):
                UDMRConfig.from_env()

    def test_from_env_zero_healthcheck_raises(self) -> None:
        """零健康检查间隔应抛异常."""
        with patch.dict(os.environ, {"UDMR_HEALTHCHECK_INTERVAL": "0"}, clear=True):
            with pytest.raises(ConfigurationError, match="UDMR_HEALTHCHECK_INTERVAL"):
                UDMRConfig.from_env()

    def test_from_env_single_cloud_model(self) -> None:
        """解析单个云端模型配置."""
        env = {
            "UDMR_CLOUD_0_ENABLED": "true",
            "UDMR_CLOUD_0_API_TYPE": "anthropic",
            "UDMR_CLOUD_0_ENDPOINT": "https://api.minimax.chat/anthropic",
            "UDMR_CLOUD_0_API_KEY": "TESTING_DUMMY_KEY",
            "UDMR_CLOUD_0_MODEL": "MiniMax-M2.7",
            "UDMR_CLOUD_0_MAX_TOKENS": "4096",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = UDMRConfig.from_env()
        assert len(cfg.cloud_configs) == 1
        cloud = cfg.cloud_configs[0]
        assert cloud.api_type == "anthropic"
        assert cloud.endpoint == "https://api.minimax.chat/anthropic"
        assert cloud.api_key == "TESTING_DUMMY_KEY"
        assert cloud.model == "MiniMax-M2.7"
        assert cloud.enabled is True
        assert cloud.max_tokens == 4096

    def test_from_env_multiple_cloud_models(self) -> None:
        """解析多个云端模型配置."""
        env = {
            "UDMR_CLOUD_0_ENABLED": "true",
            "UDMR_CLOUD_0_API_TYPE": "anthropic",
            "UDMR_CLOUD_0_ENDPOINT": "https://api.minimax.chat/anthropic",
            "UDMR_CLOUD_0_API_KEY": "key0",
            "UDMR_CLOUD_0_MODEL": "MiniMax-M2.7",
            "UDMR_CLOUD_0_MAX_TOKENS": "4096",
            "UDMR_CLOUD_1_ENABLED": "true",
            "UDMR_CLOUD_1_API_TYPE": "openai",
            "UDMR_CLOUD_1_ENDPOINT": "https://api.deepseek.com",
            "UDMR_CLOUD_1_API_KEY": "key1",
            "UDMR_CLOUD_1_MODEL": "deepseek-chat",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = UDMRConfig.from_env()
        assert len(cfg.cloud_configs) == 2
        assert cfg.cloud_configs[0].api_type == "anthropic"
        assert cfg.cloud_configs[1].api_type == "openai"

    def test_from_env_anthropic_without_max_tokens_raises(self) -> None:
        """Anthropic 类型缺少 max_tokens 应抛异常."""
        env = {
            "UDMR_CLOUD_0_ENABLED": "true",
            "UDMR_CLOUD_0_API_TYPE": "anthropic",
            "UDMR_CLOUD_0_ENDPOINT": "https://api.minimax.chat/anthropic",
            "UDMR_CLOUD_0_API_KEY": "TESTING_DUMMY_KEY",
            "UDMR_CLOUD_0_MODEL": "MiniMax-M2.7",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigurationError, match="MAX_TOKENS"):
                UDMRConfig.from_env()

    def test_from_env_openai_without_max_tokens_ok(self) -> None:
        """OpenAI 类型不要求 max_tokens."""
        env = {
            "UDMR_CLOUD_0_ENABLED": "true",
            "UDMR_CLOUD_0_API_TYPE": "openai",
            "UDMR_CLOUD_0_ENDPOINT": "https://api.deepseek.com",
            "UDMR_CLOUD_0_API_KEY": "TESTING_DUMMY_KEY",
            "UDMR_CLOUD_0_MODEL": "deepseek-chat",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = UDMRConfig.from_env()
        assert len(cfg.cloud_configs) == 1
        assert cfg.cloud_configs[0].max_tokens is None

    def test_from_env_invalid_api_type_raises(self) -> None:
        """无效 api_type 应抛异常."""
        env = {
            "UDMR_CLOUD_0_ENABLED": "true",
            "UDMR_CLOUD_0_API_TYPE": "invalid",
            "UDMR_CLOUD_0_ENDPOINT": "https://example.com",
            "UDMR_CLOUD_0_API_KEY": "TESTING_DUMMY_KEY",
            "UDMR_CLOUD_0_MODEL": "test-model",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigurationError, match="API_TYPE"):
                UDMRConfig.from_env()

    def test_from_env_skip_disabled_cloud(self) -> None:
        """disabled 的云端模型不应出现在列表中."""
        env = {
            "UDMR_CLOUD_0_ENABLED": "false",
            "UDMR_CLOUD_0_API_TYPE": "openai",
            "UDMR_CLOUD_0_ENDPOINT": "https://example.com",
            "UDMR_CLOUD_0_API_KEY": "TESTING_DUMMY_KEY",
            "UDMR_CLOUD_0_MODEL": "test-model",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = UDMRConfig.from_env()
        assert len(cfg.cloud_configs) == 0

    def test_from_env_cloud_model_without_model_field_skipped(self) -> None:
        """缺少 model 字段的云端配置应跳过."""
        env = {
            "UDMR_CLOUD_0_ENABLED": "true",
            "UDMR_CLOUD_0_API_TYPE": "openai",
            "UDMR_CLOUD_0_ENDPOINT": "https://example.com",
            "UDMR_CLOUD_0_API_KEY": "TESTING_DUMMY_KEY",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = UDMRConfig.from_env()
        assert len(cfg.cloud_configs) == 0

    def test_from_env_custom_temperature(self) -> None:
        """自定义 temperature."""
        env = {
            "UDMR_CLOUD_0_ENABLED": "true",
            "UDMR_CLOUD_0_API_TYPE": "openai",
            "UDMR_CLOUD_0_ENDPOINT": "https://example.com",
            "UDMR_CLOUD_0_API_KEY": "TESTING_DUMMY_KEY",
            "UDMR_CLOUD_0_MODEL": "test",
            "UDMR_CLOUD_0_TEMPERATURE": "0.3",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = UDMRConfig.from_env()
        assert cfg.cloud_configs[0].temperature == 0.3


class TestCloudModelConfigPricing:
    """CloudModelConfig 定价字段测试（Story 1.19）."""

    def test_pricing_default_values(self) -> None:
        """定价默认值应为 ¥0.02/1K."""
        cfg = CloudModelConfig()
        assert cfg.price_per_input_1k_tokens == 0.02
        assert cfg.price_per_output_1k_tokens == 0.02

    def test_pricing_custom_values(self) -> None:
        """自定义定价应正确."""
        cfg = CloudModelConfig(
            api_type="openai",
            model="test",
            price_per_input_1k_tokens=0.03,
            price_per_output_1k_tokens=0.04,
        )
        assert cfg.price_per_input_1k_tokens == 0.03
        assert cfg.price_per_output_1k_tokens == 0.04

    def test_pricing_from_env(self) -> None:
        """从环境变量解析定价."""
        env = {
            "UDMR_CLOUD_0_ENABLED": "true",
            "UDMR_CLOUD_0_API_TYPE": "openai",
            "UDMR_CLOUD_0_ENDPOINT": "https://example.com",
            "UDMR_CLOUD_0_API_KEY": "TESTING_DUMMY_KEY",
            "UDMR_CLOUD_0_MODEL": "test-model",
            "UDMR_CLOUD_0_PRICE_INPUT": "0.03",
            "UDMR_CLOUD_0_PRICE_OUTPUT": "0.04",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = UDMRConfig.from_env()
        cloud = cfg.cloud_configs[0]
        assert cloud.price_per_input_1k_tokens == 0.03
        assert cloud.price_per_output_1k_tokens == 0.04

    def test_pricing_defaults_when_env_not_set(self) -> None:
        """环境变量未设置时使用默认定价."""
        env = {
            "UDMR_CLOUD_0_ENABLED": "true",
            "UDMR_CLOUD_0_API_TYPE": "openai",
            "UDMR_CLOUD_0_MODEL": "test-model",
            "UDMR_CLOUD_0_API_KEY": "TESTING_DUMMY_KEY",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = UDMRConfig.from_env()
        cloud = cfg.cloud_configs[0]
        assert cloud.price_per_input_1k_tokens == 0.02
        assert cloud.price_per_output_1k_tokens == 0.02

    def test_pricing_negative_raises(self) -> None:
        """负定价应抛出 ValueError."""
        env = {
            "UDMR_CLOUD_0_ENABLED": "true",
            "UDMR_CLOUD_0_API_TYPE": "openai",
            "UDMR_CLOUD_0_MODEL": "test-model",
            "UDMR_CLOUD_0_API_KEY": "TESTING_DUMMY_KEY",
            "UDMR_CLOUD_0_PRICE_INPUT": "-0.01",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigurationError, match="PRICE_INPUT"):
                UDMRConfig.from_env()

    def test_pricing_output_negative_raises(self) -> None:
        """负输出定价应抛出 ValueError."""
        env = {
            "UDMR_CLOUD_0_ENABLED": "true",
            "UDMR_CLOUD_0_API_TYPE": "openai",
            "UDMR_CLOUD_0_MODEL": "test-model",
            "UDMR_CLOUD_0_API_KEY": "TESTING_DUMMY_KEY",
            "UDMR_CLOUD_0_PRICE_OUTPUT": "-0.01",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigurationError, match="PRICE_OUTPUT"):
                UDMRConfig.from_env()


class TestCloudModelConfigParseErrors:
    """配置解析非法值错误路径测试.

    验证非数字字符串传入时快速失败，错误信息包含具体字段名和值，
    便于运维排查环境变量配置错误
    """

    def test_invalid_max_tokens_raises(self) -> None:
        """非法 max_tokens 值（非数字）应抛出 ValueError."""
        env = {
            "UDMR_CLOUD_0_ENABLED": "true",
            "UDMR_CLOUD_0_API_TYPE": "openai",
            "UDMR_CLOUD_0_ENDPOINT": "https://example.com",
            "UDMR_CLOUD_0_API_KEY": "TESTING_DUMMY_KEY",
            "UDMR_CLOUD_0_MODEL": "test-model",
            "UDMR_CLOUD_0_MAX_TOKENS": "not_a_number",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigurationError, match="MAX_TOKENS.*not_a_number"):
                UDMRConfig.from_env()

    def test_invalid_temperature_raises(self) -> None:
        """非法 temperature 值（非数字）应抛出 ValueError."""
        env = {
            "UDMR_CLOUD_0_ENABLED": "true",
            "UDMR_CLOUD_0_API_TYPE": "openai",
            "UDMR_CLOUD_0_ENDPOINT": "https://example.com",
            "UDMR_CLOUD_0_API_KEY": "TESTING_DUMMY_KEY",
            "UDMR_CLOUD_0_MODEL": "test-model",
            "UDMR_CLOUD_0_TEMPERATURE": "hot",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigurationError, match="TEMPERATURE.*hot"):
                UDMRConfig.from_env()

    def test_invalid_price_input_raises(self) -> None:
        """非法 price_input 值（非数字）应抛出 ValueError."""
        env = {
            "UDMR_CLOUD_0_ENABLED": "true",
            "UDMR_CLOUD_0_API_TYPE": "openai",
            "UDMR_CLOUD_0_MODEL": "test-model",
            "UDMR_CLOUD_0_API_KEY": "TESTING_DUMMY_KEY",
            "UDMR_CLOUD_0_PRICE_INPUT": "free",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigurationError, match="PRICE_INPUT.*free"):
                UDMRConfig.from_env()

    def test_invalid_price_output_raises(self) -> None:
        """非法 price_output 值（非数字）应抛出 ValueError."""
        env = {
            "UDMR_CLOUD_0_ENABLED": "true",
            "UDMR_CLOUD_0_API_TYPE": "openai",
            "UDMR_CLOUD_0_MODEL": "test-model",
            "UDMR_CLOUD_0_API_KEY": "TESTING_DUMMY_KEY",
            "UDMR_CLOUD_0_PRICE_OUTPUT": "$0.02",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigurationError, match="PRICE_OUTPUT"):
                UDMRConfig.from_env()
