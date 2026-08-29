"""LLMConfig.from_env 边界路径补充测试。

测试各环境变量非法值的防御性回退逻辑。
"""

from __future__ import annotations

import os
from unittest import mock

from src.domain.ports.llm_client import LLMConfig


class TestLLMConfigFromEnvEdgeCases:
    """LLMConfig.from_env 边界用例补充。"""

    def test_invalid_api_type_fallback(self) -> None:
        """非法 api_type 应回退到 'openai'。"""
        env = {
            "LLM_API_TYPE": "invalid_type",
            "LLM_MODEL": "test-model",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            config = LLMConfig.from_env()
            assert config.api_type == "openai"

    def test_invalid_max_tokens_fallback(self) -> None:
        """非法 max_tokens 应回退到 None。"""
        env = {
            "LLM_MAX_TOKENS": "not_a_number",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            config = LLMConfig.from_env()
            assert config.max_tokens is None

    def test_invalid_timeout_fallback(self) -> None:
        """非法 timeout 应回退到 600.0。"""
        env = {
            "LLM_TIMEOUT": "bad_timeout",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            config = LLMConfig.from_env()
            assert config.timeout == 600.0

    def test_invalid_temperature_fallback(self) -> None:
        """非法 temperature 应回退到 0.7。"""
        env = {
            "LLM_TEMPERATURE": "bad_temp",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            config = LLMConfig.from_env()
            assert config.temperature == 0.7

    def test_repr_masks_api_key(self) -> None:
        """__repr__ 中 api_key 应被掩码。"""
        config = LLMConfig(api_type="openai", model="m", api_key="secret123")
        r = repr(config)
        assert "secret123" not in r
        assert "***" in r

    def test_repr_none_api_key(self) -> None:
        """api_key 为 None 时 __repr__ 输出 None。"""
        config = LLMConfig(api_type="openai", model="m", api_key=None)
        r = repr(config)
        assert "None" in r
        assert "***" not in r

    def test_valid_max_tokens_from_env(self) -> None:
        """合法 max_tokens 应被正确解析。"""
        env = {"LLM_MAX_TOKENS": "2048"}
        with mock.patch.dict(os.environ, env, clear=True):
            config = LLMConfig.from_env()
            assert config.max_tokens == 2048
