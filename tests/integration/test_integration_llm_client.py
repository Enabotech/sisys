"""LLM 客户端集成测试

验证 LitellmLLMClient 与 litellm 第三方库的集成边界：
- litellm.acompletion() 返回正常响应 → 正确解析为 LLMResponse
- litellm.acompletion() 抛出异常 → 正确映射为领域异常
- 熔断器 + 重试协同工作（通过真实的 litellm 异常触发）
- CloudModelConfig → LLMConfig 转换

litellm 是第三方依赖边界，集成测试通过 @patch 模拟 litellm.acompletion()，
验证我们的代码与 litellm 接口契约的正确集成。
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from src.domain.exceptions import LLMAPIError, LLMResponseError, ServiceUnavailableError, TimeoutError
from src.domain.ports.llm_client import LLMConfig, LLMResponse
from src.infrastructure.config.udmr import CloudModelConfig
from src.infrastructure.external_services.embedding.circuit_breaker import CircuitBreaker
from src.infrastructure.external_services.llm.litellm_llm_client import LitellmLLMClient


def _make_mock_litellm_response(
    content: str = "Hello, world!",
    finish_reason: str = "stop",
    model: str = "test-model",
) -> MagicMock:
    """构建模拟的 LiteLLM 响应对象"""
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_choice.finish_reason = finish_reason

    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 10
    mock_usage.completion_tokens = 20
    mock_usage.total_tokens = 30

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage
    mock_response.model = model
    return mock_response


@pytest.fixture
def llm_config() -> LLMConfig:
    return LLMConfig(
        api_type="openai",
        model="test-model",
        endpoint="http://test-endpoint:8000",
        api_key="test-key",  # pragma: allowlist secret
        timeout=30.0,
    )


@pytest.fixture
def client(llm_config: LLMConfig) -> LitellmLLMClient:
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0, name="test-llm")
    return LitellmLLMClient(
        config=llm_config,
        circuit_breaker=cb,
        retry_max_attempts=1,
        retry_min_wait=0.1,
        retry_max_wait=0.2,
    )


class TestIntegrationLLMClient:
    """LLM 客户端集成测试（与 litellm 的集成边界）"""

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_full_generate_flow(self, mock_acompletion: MagicMock, client: LitellmLLMClient) -> None:
        """验证完整 generate() 调用流程"""
        mock_acompletion.return_value = _make_mock_litellm_response()

        result = await client.generate(prompt="Hello")

        assert isinstance(result, LLMResponse)
        assert result.content == "Hello, world!"
        assert result.finish_reason == "stop"
        assert result.usage == {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        assert result.model == "test-model"

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_circuit_breaker_opens_after_failures(self, mock_acompletion: MagicMock, client: LitellmLLMClient) -> None:
        """验证连续失败后熔断器断开"""
        from litellm.exceptions import InternalServerError

        mock_acompletion.side_effect = InternalServerError("error", "openai", "test")
        for _ in range(3):
            with pytest.raises(LLMAPIError):
                await client.generate(prompt="Hello")
        assert client._circuit_breaker.state.name == "OPEN"

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_circuit_breaker_open_fast_fails(self, mock_acompletion: MagicMock, client: LitellmLLMClient) -> None:
        """验证熔断器断开后快速失败，不调用 litellm"""
        from litellm.exceptions import InternalServerError

        mock_acompletion.side_effect = InternalServerError("error", "openai", "test")
        for _ in range(3):
            try:
                await client.generate(prompt="Hello")
            except Exception:
                pass
        assert client._circuit_breaker.state.name == "OPEN"

        mock_acompletion.reset_mock()
        with pytest.raises(ServiceUnavailableError):
            await client.generate(prompt="Hello")
        mock_acompletion.assert_not_called()

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_structured_generate_flow(self, mock_acompletion: MagicMock, client: LitellmLLMClient) -> None:
        """验证完整 structured_generate() 调用流程"""

        class TestSchema(BaseModel):
            title: str = ""
            summary: str = ""
            score: float = 0.0

        mock_acompletion.return_value = _make_mock_litellm_response(
            content=json.dumps({"title": "测试", "summary": "摘要", "score": 0.9})
        )
        result = await client.structured_generate("test", TestSchema)

        assert isinstance(result, TestSchema)
        assert result.title == "测试"
        assert result.summary == "摘要"
        assert result.score == 0.9

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_empty_response_choices_raises_response_error(
        self, mock_acompletion: MagicMock, client: LitellmLLMClient
    ) -> None:
        """验证空 choices 抛出 LLMResponseError"""
        mock_response = MagicMock()
        mock_response.choices = []
        mock_acompletion.return_value = mock_response

        with pytest.raises(LLMResponseError) as exc_info:
            await client.generate(prompt="Hello")
        assert exc_info.value.code == "EXCEPTION_331"

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_retry_on_internal_server_error(self, mock_acompletion: MagicMock, llm_config: LLMConfig) -> None:
        """验证 500 错误触发重试，最终成功"""
        from litellm.exceptions import InternalServerError

        cb = CircuitBreaker(failure_threshold=10, recovery_timeout=1.0, name="test-retry")
        retry_client = LitellmLLMClient(
            config=llm_config,
            circuit_breaker=cb,
            retry_max_attempts=3,
            retry_min_wait=0.1,
            retry_max_wait=0.2,
        )
        mock_acompletion.side_effect = [
            InternalServerError("e1", "openai", "test"),
            InternalServerError("e2", "openai", "test"),
            _make_mock_litellm_response(),
        ]
        result = await retry_client.generate(prompt="Hello")
        assert isinstance(result, LLMResponse)
        assert mock_acompletion.call_count == 3

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_retry_exhausted_throws_exception(self, mock_acompletion: MagicMock, llm_config: LLMConfig) -> None:
        """验证重试耗尽后抛出领域异常"""
        from litellm.exceptions import InternalServerError

        cb = CircuitBreaker(failure_threshold=10, recovery_timeout=1.0, name="test-retry")
        retry_client = LitellmLLMClient(
            config=llm_config,
            circuit_breaker=cb,
            retry_max_attempts=3,
            retry_min_wait=0.1,
            retry_max_wait=0.2,
        )
        mock_acompletion.side_effect = InternalServerError("e", "openai", "test")
        with pytest.raises((LLMAPIError, ServiceUnavailableError)):
            await retry_client.generate(prompt="Hello")
        assert mock_acompletion.call_count == 3

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_timeout_error_chain(self, mock_acompletion: MagicMock, client: LitellmLLMClient) -> None:
        """验证超时异常映射链路"""
        from litellm.exceptions import Timeout as LiteLLMTimeout

        mock_acompletion.side_effect = LiteLLMTimeout("timeout", "openai", "test")
        with pytest.raises(TimeoutError) as exc_info:
            await client.generate(prompt="Hello")
        assert exc_info.value.code == "EXCEPTION_302"

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_auth_error_chain(self, mock_acompletion: MagicMock, client: LitellmLLMClient) -> None:
        """验证认证异常映射链路"""
        from litellm.exceptions import AuthenticationError

        mock_acompletion.side_effect = AuthenticationError("auth failed", "openai", "test")
        with pytest.raises(LLMAPIError) as exc_info:
            await client.generate(prompt="Hello")
        assert exc_info.value.code == "EXCEPTION_330"
        assert exc_info.value.context.get("status_code") == 401

    def test_cloud_model_config_to_llm_config(self, client: LitellmLLMClient) -> None:
        """验证 CloudModelConfig → LLMConfig 转换"""
        cloud_cfg = CloudModelConfig(
            api_type="anthropic",
            model="claude-3-opus",
            endpoint="https://api.anthropic.com",
            api_key="sk-ant-test",  # pragma: allowlist secret
            temperature=0.3,
            max_tokens=1000,
            enabled=True,
        )
        llm_config = client._build_llm_config_from_cloud_model(cloud_cfg)
        assert isinstance(llm_config, LLMConfig)
        assert llm_config.api_type == "anthropic"
        assert llm_config.model == "claude-3-opus"
        assert llm_config.max_tokens == 1000

    async def test_close_flow(self, client: LitellmLLMClient) -> None:
        """验证 close() 流程"""
        await client.close()
        assert client._closed is True
        with pytest.raises(ServiceUnavailableError):
            await client.generate(prompt="Hello")
