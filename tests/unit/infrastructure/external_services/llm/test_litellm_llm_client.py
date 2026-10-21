"""LitellmLLMClient 单元测试

使用 AsyncMock 和 patch 模拟 litellm.acompletion() 调用，
验证 generate/structured_generate/熔断器/重试/UDMR 集成。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, Field

from src.domain.exceptions import (
    LLMAPIError,
    LLMResponseError,
    ServiceUnavailableError,
    TimeoutError,
)
from src.domain.ports.llm_client import LLMConfig, LLMResponse
from src.infrastructure.external_services.embedding.circuit_breaker import (
    CircuitBreaker,
)
from src.infrastructure.external_services.llm.litellm_llm_client import (
    LitellmLLMClient,
    _extract_first_json_object,
    _is_retryable_llm_error,
    _strip_markdown_fence,
)

# ===================================================================
# 测试用 Schema
# ===================================================================


@dataclass(frozen=True)
class _TestSchema:
    """测试用结构化输出 Schema"""

    title: str = ""
    summary: str = ""
    score: float = 0.0


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def llm_config() -> LLMConfig:
    """测试用 LLMConfig 实例"""
    return LLMConfig(
        api_type="openai",
        model="test-model",
        endpoint="http://test-endpoint:8000",
        api_key="test-key",  # pragma: allowlist secret
        temperature=0.7,
        max_tokens=100,
        timeout=30.0,
    )


@pytest.fixture
def circuit_breaker() -> CircuitBreaker:
    """测试用熔断器实例（小阈值，快速测试）"""
    return CircuitBreaker(
        failure_threshold=3,
        recovery_timeout=1.0,
        half_open_max_calls=1,
        name="test-llm",
    )


@pytest.fixture
def client(llm_config: LLMConfig, circuit_breaker: CircuitBreaker) -> LitellmLLMClient:
    """测试用 LitellmLLMClient 实例"""
    return LitellmLLMClient(
        config=llm_config,
        circuit_breaker=circuit_breaker,
        retry_max_attempts=3,
        retry_min_wait=0.1,
        retry_max_wait=0.2,
    )


def _make_mock_litellm_response(
    content: str = "Hello, world!",
    finish_reason: str = "stop",
    model: str = "test-model",
    prompt_tokens: int = 10,
    completion_tokens: int = 20,
) -> MagicMock:
    """构建模拟的 LiteLLM 响应对象"""
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_choice.finish_reason = finish_reason

    mock_usage = MagicMock()
    mock_usage.prompt_tokens = prompt_tokens
    mock_usage.completion_tokens = completion_tokens
    mock_usage.total_tokens = prompt_tokens + completion_tokens

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage
    mock_response.model = model
    return mock_response


# ===================================================================
# _is_retryable_llm_error 测试
# ===================================================================


class TestIsRetryableLLMError:
    """可重试错误判断测试"""

    def test_timeout_is_retryable(self) -> None:
        """验证超时可重试"""
        from litellm.exceptions import Timeout as LiteLLMTimeout

        assert _is_retryable_llm_error(LiteLLMTimeout("timeout", "openai", "test"))

    def test_connection_error_is_retryable(self) -> None:
        """验证连接错误可重试"""
        from litellm.exceptions import APIConnectionError

        assert _is_retryable_llm_error(APIConnectionError("connection error", "openai", "test"))

    def test_internal_server_error_is_retryable(self) -> None:
        """验证服务端错误可重试"""
        from litellm.exceptions import InternalServerError

        assert _is_retryable_llm_error(InternalServerError("500 error", "openai", "test"))

    def test_auth_error_not_retryable(self) -> None:
        """验证认证错误不可重试"""
        from litellm.exceptions import AuthenticationError

        assert not _is_retryable_llm_error(AuthenticationError("auth error", "openai", "test"))

    def test_rate_limit_error_not_retryable(self) -> None:
        """验证限流错误不可重试"""
        from litellm.exceptions import RateLimitError

        assert not _is_retryable_llm_error(RateLimitError("rate limit", "openai", "test"))

    def test_bad_request_error_not_retryable(self) -> None:
        """验证请求错误不可重试"""
        from litellm.exceptions import BadRequestError

        assert not _is_retryable_llm_error(BadRequestError("bad request", "openai", "test"))


# ===================================================================
# 熔断器测试
# ===================================================================


class TestCircuitBreaker:
    """熔断器状态转换测试"""

    def test_closed_to_open(self, circuit_breaker: CircuitBreaker) -> None:
        """验证 Closed → Open：连续失败超过阈值"""
        assert circuit_breaker.state.name == "CLOSED"
        for _ in range(3):
            circuit_breaker.on_failure()
        assert circuit_breaker.state.name == "OPEN"

    def test_open_to_half_open(self, circuit_breaker: CircuitBreaker) -> None:
        """验证 Open → Half-Open：等待恢复超时后"""
        for _ in range(3):
            circuit_breaker.on_failure()
        assert circuit_breaker.state.name == "OPEN"

        # 等待恢复超时
        import time

        time.sleep(1.1)

        circuit_breaker.before_call()
        assert circuit_breaker.state.name == "HALF_OPEN"

    def test_half_open_to_closed(self, circuit_breaker: CircuitBreaker) -> None:
        """验证 Half-Open → Closed：探测成功"""
        for _ in range(3):
            circuit_breaker.on_failure()
        assert circuit_breaker.state.name == "OPEN"

        import time

        time.sleep(1.1)

        circuit_breaker.before_call()
        assert circuit_breaker.state.name == "HALF_OPEN"

        circuit_breaker.on_success()
        assert circuit_breaker.state.name == "CLOSED"

    def test_half_open_to_open_on_failure(self, circuit_breaker: CircuitBreaker) -> None:
        """验证 Half-Open → Open：探测失败"""
        for _ in range(3):
            circuit_breaker.on_failure()
        import time

        time.sleep(1.1)
        circuit_breaker.before_call()
        assert circuit_breaker.state.name == "HALF_OPEN"

        circuit_breaker.on_failure()
        assert circuit_breaker.state.name == "OPEN"


# ===================================================================
# LitellmLLMClient.generate() 测试
# ===================================================================


class TestGenerate:
    """generate() 方法测试"""

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_happy_path(self, mock_acompletion: MagicMock, client: LitellmLLMClient) -> None:
        """验证 generate() 成功返回 LLMResponse"""
        mock_response = _make_mock_litellm_response()
        mock_acompletion.return_value = mock_response

        result = await client.generate(prompt="Hello")

        assert isinstance(result, LLMResponse)
        assert result.content == "Hello, world!"
        assert result.finish_reason == "stop"
        assert result.usage == {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        assert result.model == "test-model"

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_with_custom_config(self, mock_acompletion: MagicMock, client: LitellmLLMClient) -> None:
        """验证 generate() 使用自定义配置"""
        custom_config = LLMConfig(
            api_type="anthropic",
            model="claude-3-opus",
            endpoint="https://api.anthropic.com",
            api_key="sk-ant-test",  # pragma: allowlist secret
            temperature=0.5,
            max_tokens=200,
            timeout=60.0,
        )
        mock_response = _make_mock_litellm_response()
        mock_acompletion.return_value = mock_response

        result = await client.generate(prompt="Hello", config=custom_config)

        assert isinstance(result, LLMResponse)
        assert result.content == "Hello, world!"

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_closed_client_raises_error(self, mock_acompletion: MagicMock, client: LitellmLLMClient) -> None:
        """验证客户端关闭后抛出 ServiceUnavailableError"""
        await client.close()

        with pytest.raises(ServiceUnavailableError):
            await client.generate(prompt="Hello")

    def test_check_closed_raises(self, client: LitellmLLMClient) -> None:
        """验证 _check_closed() 在关闭后抛出异常"""
        import asyncio

        asyncio.run(client.close())

        with pytest.raises(ServiceUnavailableError):
            client._check_closed()

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_empty_response_choices(self, mock_acompletion: MagicMock, client: LitellmLLMClient) -> None:
        """验证空 choices 抛出 LLMResponseError"""
        mock_response = MagicMock()
        mock_response.choices = []
        mock_acompletion.return_value = mock_response

        with pytest.raises(LLMResponseError) as exc_info:
            await client.generate(prompt="Hello")
        assert exc_info.value.code == "EXCEPTION_331"

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_missing_message_content(self, mock_acompletion: MagicMock, client: LitellmLLMClient) -> None:
        """验证缺少 message.content 抛出 LLMResponseError"""
        mock_choice = MagicMock()
        mock_choice.message = MagicMock()
        del mock_choice.message.content
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_acompletion.return_value = mock_response

        with pytest.raises(LLMResponseError) as exc_info:
            await client.generate(prompt="Hello")
        assert exc_info.value.code == "EXCEPTION_331"


# ===================================================================
# 熔断器集成测试
# ===================================================================


class TestCircuitBreakerIntegration:
    """熔断器与 generate() 集成测试"""

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_circuit_breaker_open_fast_fail(
        self,
        mock_acompletion: MagicMock,
        client: LitellmLLMClient,
        circuit_breaker: CircuitBreaker,
    ) -> None:
        """验证熔断器断开时快速失败，不发起 HTTP 请求"""
        # 连续失败 3 次使熔断器断开
        for _ in range(3):
            mock_acompletion.side_effect = Exception("API error")
            try:
                await client.generate(prompt="Hello")
            except Exception:
                pass

        # 熔断器应已断开
        assert circuit_breaker.state.name == "OPEN"

        # 再次调用应快速失败，不调用 litellm.acompletion()
        mock_acompletion.reset_mock()
        with pytest.raises(ServiceUnavailableError):
            await client.generate(prompt="Hello")
        mock_acompletion.assert_not_called()

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_circuit_breaker_half_open_recovery(
        self,
        mock_acompletion: MagicMock,
        client: LitellmLLMClient,
        circuit_breaker: CircuitBreaker,
    ) -> None:
        """验证熔断器半开后探测成功恢复"""
        # 使熔断器断开
        for _ in range(3):
            mock_acompletion.side_effect = Exception("API error")
            try:
                await client.generate(prompt="Hello")
            except Exception:
                pass

        assert circuit_breaker.state.name == "OPEN"

        # 等待恢复超时
        import time

        time.sleep(1.1)

        # 下一次调用应进入半开状态并成功
        mock_acompletion.side_effect = None
        mock_acompletion.return_value = _make_mock_litellm_response()

        result = await client.generate(prompt="Hello")
        assert isinstance(result, LLMResponse)
        assert circuit_breaker.state.name == "CLOSED"


# ===================================================================
# 重试测试
# ===================================================================


class TestRetry:
    """指数退避重试测试"""

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_retry_on_internal_server_error(
        self,
        mock_acompletion: MagicMock,
        client: LitellmLLMClient,
    ) -> None:
        """验证 500 错误触发重试"""
        from litellm.exceptions import InternalServerError

        mock_acompletion.side_effect = [
            InternalServerError("Error 1", "openai", "test"),
            InternalServerError("Error 2", "openai", "test"),
            _make_mock_litellm_response(),
        ]

        result = await client.generate(prompt="Hello")
        assert isinstance(result, LLMResponse)
        assert mock_acompletion.call_count == 3

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_retry_on_timeout(
        self,
        mock_acompletion: MagicMock,
        client: LitellmLLMClient,
    ) -> None:
        """验证超时触发重试"""
        from litellm.exceptions import Timeout as LiteLLMTimeout

        mock_acompletion.side_effect = [
            LiteLLMTimeout("timeout 1", "openai", "test"),
            LiteLLMTimeout("timeout 2", "openai", "test"),
            _make_mock_litellm_response(),
        ]

        result = await client.generate(prompt="Hello")
        assert isinstance(result, LLMResponse)
        assert mock_acompletion.call_count == 3

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_retry_exhausted_throws_exception(
        self,
        mock_acompletion: MagicMock,
        client: LitellmLLMClient,
    ) -> None:
        """验证重试耗尽后抛出领域异常"""
        from litellm.exceptions import InternalServerError

        mock_acompletion.side_effect = InternalServerError("Server error", "openai", "test")

        with pytest.raises(LLMAPIError) as exc_info:
            await client.generate(prompt="Hello")
        assert exc_info.value.code == "EXCEPTION_330"
        assert mock_acompletion.call_count == 3

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_non_retryable_error(
        self,
        mock_acompletion: MagicMock,
        client: LitellmLLMClient,
    ) -> None:
        """验证非重试错误（400）不触发重试"""
        from litellm.exceptions import BadRequestError

        mock_acompletion.side_effect = BadRequestError("Bad request", "openai", "test")

        with pytest.raises(LLMAPIError) as exc_info:
            await client.generate(prompt="Hello")
        assert exc_info.value.code == "EXCEPTION_330"
        # 只调用一次（不重试）
        assert mock_acompletion.call_count == 1

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_retry_on_connection_error(
        self,
        mock_acompletion: MagicMock,
        client: LitellmLLMClient,
    ) -> None:
        """验证网络连接错误触发重试"""
        from litellm.exceptions import APIConnectionError

        mock_acompletion.side_effect = [
            APIConnectionError("connection error", "openai", "test"),
            _make_mock_litellm_response(),
        ]

        result = await client.generate(prompt="Hello")
        assert isinstance(result, LLMResponse)
        assert mock_acompletion.call_count == 2


# ===================================================================
# structured_generate() 测试
# ===================================================================


class TestStructuredGenerate:
    """structured_generate() 方法测试"""

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_happy_path(
        self,
        mock_acompletion: MagicMock,
        client: LitellmLLMClient,
    ) -> None:
        """验证 structured_generate() 成功返回 Schema 对象"""
        content = json.dumps({"title": "测试标题", "summary": "测试摘要", "score": 0.95})
        mock_response = _make_mock_litellm_response(content=content)
        mock_acompletion.return_value = mock_response

        result = await client.structured_generate(
            prompt="Generate structured output",
            response_schema=_TestSchema,
        )

        assert isinstance(result, _TestSchema)
        assert result.title == "测试标题"
        assert result.summary == "测试摘要"
        assert result.score == 0.95

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_invalid_json_raises_response_error(
        self,
        mock_acompletion: MagicMock,
        client: LitellmLLMClient,
    ) -> None:
        """验证无效 JSON 抛出 LLMResponseError"""
        mock_response = _make_mock_litellm_response(content="not valid json")
        mock_acompletion.return_value = mock_response

        with pytest.raises(LLMResponseError) as exc_info:
            await client.structured_generate(
                prompt="Generate structured output",
                response_schema=_TestSchema,
            )
        assert exc_info.value.code == "EXCEPTION_331"


# ===================================================================
# _build_llm_config_from_cloud_model 测试
# ===================================================================


class TestBuildConfigFromCloudModel:
    """CloudModelConfig → LLMConfig 转换测试"""

    def test_convert_cloud_model_config(self, client: LitellmLLMClient) -> None:
        """验证 CloudModelConfig → LLMConfig 字段映射正确"""
        from src.infrastructure.config.udmr import CloudModelConfig

        cloud_cfg = CloudModelConfig(
            api_type="openai",
            model="deepseek-v4-flash",
            endpoint="https://api.deepseek.com",
            api_key="sk-test",  # pragma: allowlist secret
            temperature=0.5,
            max_tokens=200,
            enabled=True,
        )

        llm_config = client._build_llm_config_from_cloud_model(cloud_cfg)

        assert isinstance(llm_config, LLMConfig)
        assert llm_config.api_type == "openai"
        assert llm_config.model == "deepseek-v4-flash"
        assert llm_config.endpoint == "https://api.deepseek.com"
        assert llm_config.api_key == "sk-test"  # pragma: allowlist secret
        assert llm_config.temperature == 0.5
        assert llm_config.max_tokens == 200

    def test_convert_anthropic_config(self, client: LitellmLLMClient) -> None:
        """验证 Anthropic 类型配置转换"""
        from src.infrastructure.config.udmr import CloudModelConfig

        cloud_cfg = CloudModelConfig(
            api_type="anthropic",
            model="claude-3-opus",
            endpoint="https://api.anthropic.com",
            api_key="sk-ant",  # pragma: allowlist secret
            temperature=0.3,
            max_tokens=1000,
            enabled=True,
        )

        llm_config = client._build_llm_config_from_cloud_model(cloud_cfg)

        assert llm_config.api_type == "anthropic"
        assert llm_config.model == "claude-3-opus"
        assert llm_config.max_tokens == 1000


# ===================================================================
# _build_acompletion_kwargs 测试
# ===================================================================


class TestBuildAcompletionKwargs:
    """_build_acompletion_kwargs() 测试"""

    def test_basic_kwargs(self, client: LitellmLLMClient, llm_config: LLMConfig) -> None:
        """验证基本参数构建"""
        kwargs = client._build_acompletion_kwargs("Hello", llm_config)
        assert kwargs["model"] == "test-model"
        assert kwargs["messages"] == [{"role": "user", "content": "Hello"}]
        assert kwargs["temperature"] == 0.7
        assert kwargs["base_url"] == "http://test-endpoint:8000"
        assert kwargs["api_key"] == "test-key"  # pragma: allowlist secret
        assert kwargs["max_tokens"] == 100
        assert kwargs["timeout"] == 30.0

    def test_default_config(self, client: LitellmLLMClient) -> None:
        """验证使用默认配置"""
        kwargs = client._build_acompletion_kwargs("Hello")
        assert kwargs["model"] == "test-model"


# ===================================================================
# _map_llm_error 测试
# ===================================================================


class TestMapLLMError:
    """异常映射测试"""

    def test_timeout_to_timeout_error(self, client: LitellmLLMClient, llm_config: LLMConfig) -> None:
        """验证 LiteLLMTimeout → TimeoutError"""
        from litellm.exceptions import Timeout as LiteLLMTimeout

        error = client._map_llm_error(LiteLLMTimeout("timeout", "openai", "test"), llm_config)
        assert isinstance(error, TimeoutError)

    def test_connection_error_to_service_unavailable(self, client: LitellmLLMClient, llm_config: LLMConfig) -> None:
        """验证 APIConnectionError → ServiceUnavailableError"""
        from litellm.exceptions import APIConnectionError

        error = client._map_llm_error(APIConnectionError("connection error", "openai", "test"), llm_config)
        assert isinstance(error, ServiceUnavailableError)

    def test_auth_error_to_llm_api_error(self, client: LitellmLLMClient, llm_config: LLMConfig) -> None:
        """验证 AuthenticationError → LLMAPIError(401)"""
        from litellm.exceptions import AuthenticationError

        error = client._map_llm_error(AuthenticationError("auth error", "openai", "test"), llm_config)
        assert isinstance(error, LLMAPIError)
        assert error.context.get("status_code") == 401

    def test_rate_limit_to_llm_api_error(self, client: LitellmLLMClient, llm_config: LLMConfig) -> None:
        """验证 RateLimitError → LLMAPIError(429)"""
        from litellm.exceptions import RateLimitError

        error = client._map_llm_error(RateLimitError("rate limit", "openai", "test"), llm_config)
        assert isinstance(error, LLMAPIError)
        assert error.context.get("status_code") == 429

    def test_bad_request_to_llm_api_error(self, client: LitellmLLMClient, llm_config: LLMConfig) -> None:
        """验证 BadRequestError → LLMAPIError(400)"""
        from litellm.exceptions import BadRequestError

        error = client._map_llm_error(BadRequestError("bad request", "openai", "test"), llm_config)
        assert isinstance(error, LLMAPIError)
        assert error.context.get("status_code") == 400

    def test_internal_server_error_to_llm_api_error(self, client: LitellmLLMClient, llm_config: LLMConfig) -> None:
        """验证 InternalServerError → LLMAPIError(500)"""
        from litellm.exceptions import InternalServerError

        error = client._map_llm_error(InternalServerError("500 error", "openai", "test"), llm_config)
        assert isinstance(error, LLMAPIError)
        assert error.context.get("status_code") == 500


# ===================================================================
# JSON 解析鲁棒性辅助函数测试（Round 6 根因修复）
# 修复 JSONDecodeError: Extra data 场景（LLM 在 JSON 后追加解释文本）
# ===================================================================


class TestStripMarkdownFence:
    """_strip_markdown_fence 单元测试"""

    def test_no_fence_returns_as_is(self) -> None:
        """无围栏内容原样返回"""
        content = '{"key": "value"}'
        assert _strip_markdown_fence(content) == content

    def test_strips_outer_fence(self) -> None:
        """剥离外层 ```json ... ``` 围栏"""
        content = '```json\n{"key": "value"}\n```'
        assert _strip_markdown_fence(content) == '{"key": "value"}'

    def test_strips_bare_fence(self) -> None:
        """剥离 ``` ... ```（无语言标记）"""
        content = '```\n{"key": "value"}\n```'
        assert _strip_markdown_fence(content) == '{"key": "value"}'


class TestExtractFirstJsonObject:
    """_extract_first_json_object 单元测试（修复 JSONDecodeError: Extra data 根因）"""

    def test_extracts_pure_json(self) -> None:
        """纯 JSON 字符串正确返回"""
        content = '{"entities": [{"name": "BLM"}]}'
        result = _extract_first_json_object(content)
        assert result == content

    def test_extracts_json_with_trailing_text(self) -> None:
        """根因场景：JSON 后跟解释文本（触发 JSONDecodeError: Extra data）"""
        content = '{"entities": [{"name": "BLM"}]}\n\n以上是抽取结果，希望对你有帮助。'
        result = _extract_first_json_object(content)
        assert result == '{"entities": [{"name": "BLM"}]}'

    def test_extracts_json_with_leading_text(self) -> None:
        """JSON 前有引导文本"""
        content = '下面是抽取结果：\n{"entities": [{"name": "BLM"}]}'
        result = _extract_first_json_object(content)
        assert result == '{"entities": [{"name": "BLM"}]}'

    def test_extracts_first_of_multiple_json_blocks(self) -> None:
        """多个 JSON 对象只取第一个"""
        content = '{"a": 1}\n{"b": 2}'
        result = _extract_first_json_object(content)
        assert result == '{"a": 1}'

    def test_handles_nested_objects(self) -> None:
        """嵌套对象深度计算正确"""
        content = '{"a": {"b": {"c": {"d": [1, 2, 3]}}}}'
        result = _extract_first_json_object(content)
        assert result == content

    def test_handles_braces_inside_strings(self) -> None:
        """字符串内的花括号不干扰配对计数（边界测试）"""
        content = '{"text": "hello {world}", "num": 42}'
        result = _extract_first_json_object(content)
        assert result == content

    def test_returns_none_for_no_json(self) -> None:
        """无 JSON 返回 None"""
        content = "no json here"
        assert _extract_first_json_object(content) is None

    def test_returns_none_for_empty_content(self) -> None:
        """空内容返回 None"""
        assert _extract_first_json_object("") is None
        assert _extract_first_json_object(None) is None

    def test_handles_json_array(self) -> None:
        """支持 JSON 数组（虽然场景主要是对象）"""
        content = '[1, 2, {"a": 3}]'
        result = _extract_first_json_object(content)
        assert result == content


# ===================================================================
# anthropic 通道结构化输出（Story 5-3 补——litellm response_format 转换缺陷绕过）
# ===================================================================


class _NestedStep(BaseModel):
    """嵌套 Schema 步结构（模块级定义——精确类型注解使 isinstance 收窄生效）。"""

    description: str = Field(min_length=1)
    tool_name: str = ""


class _NestedPlan(BaseModel):
    """嵌套 Schema（list[Step] 形态——生产 PlanSchema 同构）。

    复现 GLM-5.3 anthropic 端点 500 的 Schema 形态（嵌套 object list）。
    """

    steps: list[_NestedStep] = Field(min_length=1)


def _make_nested_pydantic_schema() -> type[_NestedPlan]:
    """构造嵌套 Schema（list[Step] 形态——生产 PlanSchema 同构）。"""
    return _NestedPlan


def _make_anthropic_config() -> LLMConfig:
    """anthropic 协议配置（生产 UDMR_CLOUD GLM-5.3 同款形态）。"""
    return LLMConfig(
        api_type="anthropic",
        model="glm-5.3-flash",
        endpoint="https://open.bigmodel.cn/api/anthropic",
        api_key="test-key",  # pragma: allowlist secret
        temperature=0.3,
        max_tokens=1024,
        timeout=30.0,
    )


def _make_tool_call_response(arguments_json: str) -> MagicMock:
    """构建带 tool_calls 的 LiteLLM 响应（anthropic tool_use 经 litellm 转换形态）。"""
    mock_response = _make_mock_litellm_response(content="")
    tool_call = MagicMock()
    tool_call.function.arguments = arguments_json
    tool_call.function.name = "Plan"
    mock_response.choices[0].message.tool_calls = [tool_call]
    return mock_response


class TestStructuredGenerateAnthropicChannel:
    """anthropic api_type 的结构化输出通道（tools 传法替代 response_format）。

    根因（2026-10-20 实测定谳）：litellm 1.83 对 anthropic 协议的
    response_format=json_schema 转换生成病态请求（嵌套 Schema 触发服务端
    500 StackOverflowError）；标准 anthropic tool 格式两通道（原始 httpx 与
    litellm tools 直传）均实证可靠——本通道按 api_type 分派请求构造与解析。
    """

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_anthropic_uses_tools_channel_not_response_format(
        self, mock_acompletion: MagicMock, client: LitellmLLMClient
    ) -> None:
        """anthropic 通道请求形态：标准 tools + tool_choice 强制；无 response_format。"""
        plan = _make_nested_pydantic_schema()
        mock_acompletion.return_value = _make_tool_call_response(
            json.dumps({"steps": [{"description": "第一步分析", "tool_name": ""}]})
        )
        anthropic_cfg = _make_anthropic_config()

        await client.structured_generate("规划任务", response_schema=plan, config=anthropic_cfg)

        kwargs = mock_acompletion.call_args.kwargs
        assert "response_format" not in kwargs, "anthropic 通道禁用 response_format（litellm 转换缺陷面）"
        assert "tools" in kwargs, "anthropic 通道应以标准 tools 传法承载 Schema"
        tool = kwargs["tools"][0]
        assert tool["type"] == "function"
        assert tool["function"]["name"] == _NestedPlan.__name__, "tool 名应为 Schema 类名（同源派生防改名破断言）"
        # parameters 应为 Schema 原生 JSON Schema
        assert tool["function"]["parameters"] == plan.model_json_schema()
        assert kwargs["tool_choice"] == {"type": "function", "function": {"name": _NestedPlan.__name__}}, (
            "强制调用该 tool（结构化确定性）"
        )

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_openai_keeps_response_format_channel(self, mock_acompletion: MagicMock, client: LitellmLLMClient) -> None:
        """openai 通道零回归：保持 response_format=json_schema 传法（原生直传无缺陷）。"""
        plan = _make_nested_pydantic_schema()
        mock_acompletion.return_value = _make_mock_litellm_response(
            content=json.dumps({"steps": [{"description": "第一步", "tool_name": ""}]})
        )

        await client.structured_generate("规划任务", response_schema=plan)  # fixture 为 openai config

        kwargs = mock_acompletion.call_args.kwargs
        assert "tools" not in kwargs, "openai 通道不应注入 tools"
        assert kwargs["response_format"]["type"] == "json_schema"
        assert kwargs["response_format"]["json_schema"]["schema"] == plan.model_json_schema()

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_tool_call_arguments_parsed_to_schema(self, mock_acompletion: MagicMock, client: LitellmLLMClient) -> None:
        """anthropic tool_use 响应解析：tool_calls[0].function.arguments → Schema 实例。"""
        plan = _make_nested_pydantic_schema()
        mock_acompletion.return_value = _make_tool_call_response(
            json.dumps(
                {
                    "steps": [
                        {"description": "行业宏观分析", "tool_name": "PESTEL 分析"},
                        {"description": "综合建议", "tool_name": ""},
                    ]
                }
            )
        )

        result = await client.structured_generate("规划任务", response_schema=plan, config=_make_anthropic_config())

        assert isinstance(result, plan)
        assert len(result.steps) == 2
        assert result.steps[0].tool_name == "PESTEL 分析"

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_content_fallback_when_no_tool_calls(self, mock_acompletion: MagicMock, client: LitellmLLMClient) -> None:
        """无 tool_calls 时回退 content 文本解析（模型偶发不调 tool 的容错面）。"""
        plan = _make_nested_pydantic_schema()
        mock_acompletion.return_value = _make_mock_litellm_response(
            content='```json\n{"steps": [{"description": "回退解析", "tool_name": ""}]}\n```'
        )

        result = await client.structured_generate("规划任务", response_schema=plan, config=_make_anthropic_config())

        assert isinstance(result, plan)
        assert result.steps[0].description == "回退解析"

    @patch("src.infrastructure.external_services.llm.litellm_llm_client.litellm.acompletion")
    async def test_tool_call_invalid_json_raises_331(self, mock_acompletion: MagicMock, client: LitellmLLMClient) -> None:
        """tool_use arguments 非法 JSON → LLMResponseError(331)（统一解析契约）。"""
        plan = _make_nested_pydantic_schema()
        mock_acompletion.return_value = _make_tool_call_response("not-valid-json")

        with pytest.raises(LLMResponseError) as exc_info:
            await client.structured_generate("规划任务", response_schema=plan, config=_make_anthropic_config())
        assert exc_info.value.code == "EXCEPTION_331"
