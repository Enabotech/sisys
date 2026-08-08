"""LitellmLLMClient 异常映射单元测试

验证 litellm 原始异常 → 领域异常 的映射正确性。
所有异常映射通过 _map_llm_error() 方法实现。
"""

from __future__ import annotations

import pytest

from src.domain.exceptions import (
    LLMAPIError,
    LLMConfigError,
    LLMResponseError,
    ServiceUnavailableError,
    TimeoutError,
)
from src.domain.ports.llm_client import LLMConfig
from src.infrastructure.external_services.llm.litellm_llm_client import (
    LitellmLLMClient,
)


@pytest.fixture
def client() -> LitellmLLMClient:
    """测试用 LitellmLLMClient 实例"""
    return LitellmLLMClient()


@pytest.fixture
def config() -> LLMConfig:
    """测试用 LLMConfig 实例"""
    return LLMConfig(
        api_type="openai",
        model="test-model",
        endpoint="http://test-endpoint:8000",
        api_key="test-key",  # pragma: allowlist secret
    )


class TestErrorMapping:
    """LiteLLM 异常 → 领域异常映射测试"""

    def test_api_connection_error(self, client: LitellmLLMClient, config: LLMConfig) -> None:
        """验证 APIConnectionError → ServiceUnavailableError"""
        from litellm.exceptions import APIConnectionError

        error = client._map_llm_error(APIConnectionError("connection failed", "openai", "test"), config)
        assert isinstance(error, ServiceUnavailableError)
        assert error.code == "EXCEPTION_303"

    def test_timeout_error(self, client: LitellmLLMClient, config: LLMConfig) -> None:
        """验证 LiteLLMTimeout → TimeoutError"""
        from litellm.exceptions import Timeout as LiteLLMTimeout

        error = client._map_llm_error(LiteLLMTimeout("request timeout", "openai", "test"), config)
        assert isinstance(error, TimeoutError)
        assert error.code == "EXCEPTION_302"

    def test_authentication_error(self, client: LitellmLLMClient, config: LLMConfig) -> None:
        """验证 AuthenticationError → LLMAPIError(401)"""
        from litellm.exceptions import AuthenticationError

        error = client._map_llm_error(AuthenticationError("auth failed", "openai", "test"), config)
        assert isinstance(error, LLMAPIError)
        assert error.code == "EXCEPTION_330"
        assert error.context.get("status_code") == 401

    def test_rate_limit_error(self, client: LitellmLLMClient, config: LLMConfig) -> None:
        """验证 RateLimitError → LLMAPIError(429)"""
        from litellm.exceptions import RateLimitError

        error = client._map_llm_error(RateLimitError("rate limited", "openai", "test"), config)
        assert isinstance(error, LLMAPIError)
        assert error.code == "EXCEPTION_330"
        assert error.context.get("status_code") == 429

    def test_bad_request_error(self, client: LitellmLLMClient, config: LLMConfig) -> None:
        """验证 BadRequestError → LLMAPIError(400)"""
        from litellm.exceptions import BadRequestError

        error = client._map_llm_error(BadRequestError("bad request", "openai", "test"), config)
        assert isinstance(error, LLMAPIError)
        assert error.code == "EXCEPTION_330"
        assert error.context.get("status_code") == 400

    def test_internal_server_error(self, client: LitellmLLMClient, config: LLMConfig) -> None:
        """验证 InternalServerError → LLMAPIError(500)"""
        from litellm.exceptions import InternalServerError

        error = client._map_llm_error(InternalServerError("internal error", "openai", "test"), config)
        assert isinstance(error, LLMAPIError)
        assert error.code == "EXCEPTION_330"
        assert error.context.get("status_code") == 500

    def test_json_parse_error(self, client: LitellmLLMClient, config: LLMConfig) -> None:
        """验证 JSON 解析错误 → LLMResponseError"""
        # 通过 structured_generate 的 JSON 解析环节验证
        import asyncio
        from unittest.mock import MagicMock, patch

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "not valid json"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "test-model"
        mock_response.usage = None

        with patch(
            "src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion",
            return_value=mock_response,
        ):
            with pytest.raises(LLMResponseError) as exc_info:
                asyncio.run(client.structured_generate("test", dict, config=config))
            assert exc_info.value.code == "EXCEPTION_331"

    def test_config_error_api_key_missing(self, client: LitellmLLMClient, config: LLMConfig) -> None:
        """验证 API Key 缺失 → LLMConfigError"""
        # 模拟 API Key 缺失的异常
        exc = ValueError("api_key is required for authentication")
        error = client._map_llm_error(exc, config)
        # 根据实现，api_key 缺失的异常应映射为 LLMConfigError
        assert isinstance(error, LLMConfigError), f"期望 LLMConfigError，实际为 {type(error).__name__}"
        assert error.code == "EXCEPTION_332", f"期望编码 EXCEPTION_332，实际为 {error.code}"
        assert error.context.get("config_key") == "api_key", "应携带 config_key 上下文"

    def test_unknown_error_fallback(self, client: LitellmLLMClient, config: LLMConfig) -> None:
        """验证未知异常兜底为 LLMAPIError"""
        exc = RuntimeError("unexpected error")
        error = client._map_llm_error(exc, config)
        assert isinstance(error, LLMAPIError)
        assert error.code == "EXCEPTION_330"
