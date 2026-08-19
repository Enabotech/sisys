"""LLM 客户端集成测试

使用真实 aiohttp HTTP 服务器模拟 LLM API，验证 LitellmLLMClient 与 litellm 的完整集成边界：
- litellm.acompletion() 正常响应 → 正确解析为 LLMResponse
- litellm.acompletion() HTTP 错误 → 自动映射为领域异常
- 熔断器 + 重试协同工作（通过真实 HTTP 状态码触发）
- CloudModelConfig → LLMConfig 转换

使用真实 HTTP 服务器（aiohttp），而非 mock litellm.acompletion()，确保：
1. 验证 litellm 的 HTTP 请求构建逻辑（URL、headers、body）
2. 验证 litellm 的响应解析逻辑（status code、JSON body）
3. 验证 litellm 的异常处理逻辑（HTTP 错误 → litellm 异常 → 领域异常）

Mock 原因：LLM API 是外部 SaaS 服务，有成本/限流/不可控，无法在集成测试中调用真实 API。
使用本地 HTTP 服务器模拟 API 端点，在保持可重复性的同时验证完整的 HTTP 交互链路。
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from aiohttp import web
from pydantic import BaseModel

from src.domain.exceptions import LLMAPIError, LLMResponseError, ServiceUnavailableError, TimeoutError
from src.domain.ports.llm_client import LLMConfig, LLMResponse
from src.infrastructure.config.udmr import CloudModelConfig
from src.infrastructure.external_services.embedding.circuit_breaker import CircuitBreaker
from src.infrastructure.external_services.llm.litellm_llm_client import LitellmLLMClient

# ===================================================================
# 模拟 LLM API HTTP 服务器
# ===================================================================


def _make_openai_response(
    content: str = "Hello, world!",
    finish_reason: str = "stop",
    model: str = "test-model",
    prompt_tokens: int = 10,
    completion_tokens: int = 20,
) -> dict[str, Any]:
    """构建 OpenAI 兼容的 chat completion 非 streaming 响应"""
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": 1234567890,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                },
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


class MockLLMHandler:
    """模拟 LLM API 的 HTTP 请求处理器

    每个测试通过 set_*() 方法控制服务器行为。
    """

    def __init__(self) -> None:
        self._default_response: dict[str, Any] = _make_openai_response()
        self._sequence: list[tuple[int, dict[str, Any] | None, str | None]] | None = None
        self._call_index: int = 0
        self._delay: float = 0.0
        self.requests: list[dict[str, Any]] = []

    def set_success(self, content: str = "Hello, world!", finish_reason: str = "stop") -> None:
        """设置服务器始终返回成功响应"""
        self._default_response = _make_openai_response(content=content, finish_reason=finish_reason)
        self._sequence = None
        self._call_index = 0
        self._delay = 0.0

    def set_http_error(self, status: int, body: str | None = None) -> None:
        """设置服务器始终返回 HTTP 错误"""
        self._default_response = {}
        self._sequence = [(status, None, body or '{"error": {"message": "test error"}}')]
        self._call_index = 0
        self._delay = 0.0

    def set_error_then_success(self, error_count: int, error_status: int = 500) -> None:
        """设置前 N 次返回 HTTP 错误，之后返回成功"""
        seq: list[tuple[int, dict[str, Any] | None, str | None]] = []
        for _ in range(error_count):
            seq.append((error_status, None, '{"error": {"message": "server error"}}'))
        seq.append((200, _make_openai_response(content="success"), None))
        self._sequence = seq
        self._call_index = 0
        self._delay = 0.0

    def set_empty_choices(self) -> None:
        """设置服务器返回无 choices 的响应"""
        resp_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
        self._default_response = {
            "id": resp_id,
            "object": "chat.completion",
            "created": 1234567890,
            "model": "test-model",
            "choices": [],
            "usage": {},
        }
        self._sequence = None
        self._call_index = 0
        self._delay = 0.0

    def set_delay(self, delay: float) -> None:
        """设置响应延迟（秒），用于触发超时"""
        self._delay = delay

    def _get_response(self) -> tuple[int, dict[str, Any] | None, str | None]:
        """获取当前调用的响应配置"""
        if self._sequence is not None:
            idx = min(self._call_index, len(self._sequence) - 1)
            return self._sequence[idx]
        return 200, self._default_response, None

    async def handle(self, request: web.Request) -> web.Response:
        """处理 POST /chat/completions 请求"""
        body = await request.json()
        self.requests.append(body)

        if self._delay > 0:
            await asyncio.sleep(self._delay)

        status, resp_body, error_body = self._get_response()
        self._call_index += 1

        if error_body is not None:
            return web.Response(
                status=status,
                body=error_body.encode("utf-8") if isinstance(error_body, str) else error_body,
                content_type="application/json",
            )

        return web.json_response(resp_body or {}, status=status)


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
async def mock_llm_server():
    """启动本地 HTTP 服务器模拟 LLM API，返回 (handler, port)"""
    handler = MockLLMHandler()
    app = web.Application()
    app.router.add_post("/chat/completions", handler.handle)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()

    # 获取实际端口号
    port = site._server.sockets[0].getsockname()[1]

    yield handler, port

    await runner.cleanup()


@pytest.fixture
def llm_config(mock_llm_server: tuple[MockLLMHandler, int]) -> LLMConfig:
    """LLM 配置，指向本地模拟服务器"""
    _, port = mock_llm_server
    return LLMConfig(
        api_type="openai",
        model="test-model",
        endpoint=f"http://127.0.0.1:{port}",
        api_key="test-key",  # pragma: allowlist secret
        timeout=30.0,
    )


@pytest.fixture
async def client(mock_llm_server: tuple[MockLLMHandler, int], llm_config: LLMConfig) -> AsyncGenerator[LitellmLLMClient, None]:
    """LLM 客户端，带熔断器和重试配置"""
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0, name="test-llm")
    c = LitellmLLMClient(
        config=llm_config,
        circuit_breaker=cb,
        retry_max_attempts=1,
        retry_min_wait=0.1,
        retry_max_wait=0.2,
    )
    yield c
    await c.close()


# ===================================================================
# 全局清理：停止 LiteLLM 日志工作线程
# ===================================================================


@pytest.fixture(autouse=True)
async def _stop_litellm_worker():
    """每个测试结束后停止 LiteLLM 全局日志工作线程

    LiteLLM 的 LoggingWorker 是模块级单例，在首次调用 acompletion() 时
    创建后台 _worker_loop 协程。若不在测试间清理，该协程会在事件循环关闭后
    被 GC 时触发 PytestUnraisableExceptionWarning("RuntimeError: Event loop is closed")。

    清理顺序：
    1. 先停止工作线程，取消 _worker_loop 与 _running_tasks
    2. 再清空队列中未被处理的日志协程句柄（已被 stop() 取消，直接丢弃）
    """
    yield
    try:
        from litellm.litellm_core_utils.logging_worker import GLOBAL_LOGGING_WORKER

        # 第 1 步：先停止工作线程，取消 _worker_loop 和 _running_tasks
        await GLOBAL_LOGGING_WORKER.stop()
        # 第 2 步：清空队列中未被 worker 出队的协程句柄，避免悬挂引用
        # 直接丢弃而非 await（stop() 已取消这些协程，无需等待完成）
        queue = getattr(GLOBAL_LOGGING_WORKER, "_queue", None)
        if queue is not None:
            for _ in range(200):
                try:
                    queue.get_nowait()
                    queue.task_done()
                except asyncio.QueueEmpty:
                    break
    except Exception:
        pass


# ===================================================================
# 集成测试
# ===================================================================


class TestIntegrationLLMClient:
    """LLM 客户端集成测试（与 litellm 的 HTTP 集成边界）"""

    async def test_full_generate_flow(self, mock_llm_server: tuple[MockLLMHandler, int], client: LitellmLLMClient) -> None:
        """验证完整 generate() 调用流程：真实 HTTP 请求 → litellm 解析 → LLMResponse"""
        handler, _ = mock_llm_server
        handler.set_success()

        result = await client.generate(prompt="Hello")

        assert isinstance(result, LLMResponse)
        assert result.content == "Hello, world!"
        assert result.finish_reason == "stop"
        assert result.usage == {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        assert result.model == "test-model"

        # 验证 litellm 实际发送了 HTTP 请求到正确端点
        assert len(handler.requests) == 1
        req_body = handler.requests[0]
        assert req_body["model"] == "test-model"
        assert req_body["messages"][0]["role"] == "user"
        assert req_body["messages"][0]["content"] == "Hello"

    async def test_circuit_breaker_opens_after_failures(
        self, mock_llm_server: tuple[MockLLMHandler, int], client: LitellmLLMClient
    ) -> None:
        """验证连续失败后熔断器断开（通过 MockLLMHandler 返回 HTTP 500 触发）"""
        handler, _ = mock_llm_server
        handler.set_http_error(500)

        for _ in range(3):
            with pytest.raises(LLMAPIError):
                await client.generate(prompt="Hello")
        assert client._circuit_breaker.state.name == "OPEN"

    async def test_circuit_breaker_open_fast_fails(
        self, mock_llm_server: tuple[MockLLMHandler, int], client: LitellmLLMClient
    ) -> None:
        """验证熔断器断开后快速失败，不发起 HTTP 请求"""
        handler, _ = mock_llm_server
        handler.set_http_error(500)

        # 触发 3 次失败使熔断器断开
        for _ in range(3):
            try:
                await client.generate(prompt="Hello")
            except Exception:
                pass
        assert client._circuit_breaker.state.name == "OPEN"

        # 熔断器断开后，before_call() 直接抛出异常，不经过 litellm
        with pytest.raises(ServiceUnavailableError):
            await client.generate(prompt="Hello")

    async def test_structured_generate_flow(
        self, mock_llm_server: tuple[MockLLMHandler, int], client: LitellmLLMClient
    ) -> None:
        """验证完整 structured_generate() 调用流程"""

        class TestSchema(BaseModel):
            title: str = ""
            summary: str = ""
            score: float = 0.0

        handler, _ = mock_llm_server
        handler.set_success(content=json.dumps({"title": "测试", "summary": "摘要", "score": 0.9}))

        result = await client.structured_generate("test", TestSchema)

        assert isinstance(result, TestSchema)
        assert result.title == "测试"
        assert result.summary == "摘要"
        assert result.score == 0.9

    async def test_empty_response_choices_raises_response_error(
        self, mock_llm_server: tuple[MockLLMHandler, int], client: LitellmLLMClient
    ) -> None:
        """验证空 choices 抛出 LLMResponseError"""
        handler, _ = mock_llm_server
        handler.set_empty_choices()

        with pytest.raises(LLMResponseError) as exc_info:
            await client.generate(prompt="Hello")
        assert exc_info.value.code == "EXCEPTION_331"

    async def test_retry_on_internal_server_error(
        self, mock_llm_server: tuple[MockLLMHandler, int], llm_config: LLMConfig
    ) -> None:
        """验证 500 错误触发重试，最终成功"""
        handler, _ = mock_llm_server
        handler.set_error_then_success(error_count=2, error_status=500)

        cb = CircuitBreaker(failure_threshold=10, recovery_timeout=1.0, name="test-retry")
        retry_client = LitellmLLMClient(
            config=llm_config,
            circuit_breaker=cb,
            retry_max_attempts=3,
            retry_min_wait=0.1,
            retry_max_wait=0.2,
        )

        result = await retry_client.generate(prompt="Hello")

        assert isinstance(result, LLMResponse)
        assert result.content == "success"
        # 3 次调用：2 次失败 + 1 次成功
        assert len(handler.requests) == 3, "应重试 2 次后第 3 次成功"

    async def test_retry_exhausted_throws_exception(
        self, mock_llm_server: tuple[MockLLMHandler, int], llm_config: LLMConfig
    ) -> None:
        """验证重试耗尽后抛出领域异常（通过真实 HTTP 500 响应触发）"""
        handler, _ = mock_llm_server
        handler.set_http_error(500)

        cb = CircuitBreaker(failure_threshold=10, recovery_timeout=1.0, name="test-retry")
        retry_client = LitellmLLMClient(
            config=llm_config,
            circuit_breaker=cb,
            retry_max_attempts=3,
            retry_min_wait=0.1,
            retry_max_wait=0.2,
        )

        with pytest.raises((LLMAPIError, ServiceUnavailableError)):
            await retry_client.generate(prompt="Hello")
        # 验证异常被正确抛出（litellm 内部重试 + tenacity 重试后最终仍失败）

    async def test_timeout_error_chain(self, mock_llm_server: tuple[MockLLMHandler, int], llm_config: LLMConfig) -> None:
        """验证超时异常映射链路（服务器延迟响应 → httpx 超时 → litellm Timeout → TimeoutError）"""
        handler, _ = mock_llm_server
        handler.set_success()
        handler.set_delay(1.0)  # 服务器延迟 1 秒（> 0.5s 客户端超时，可靠触发 Timeout）

        # 配置极短超时触发 httpx ReadTimeout
        timeout_config = LLMConfig(
            api_type="openai",
            model="test-model",
            endpoint=llm_config.endpoint,
            api_key="test-key",  # pragma: allowlist secret
            timeout=0.5,  # 500ms 超时
        )
        cb = CircuitBreaker(failure_threshold=10, recovery_timeout=1.0, name="test-timeout")
        timeout_client = LitellmLLMClient(
            config=timeout_config,
            circuit_breaker=cb,
            retry_max_attempts=1,
            retry_min_wait=0.1,
            retry_max_wait=0.2,
        )

        with pytest.raises(TimeoutError) as exc_info:
            await timeout_client.generate(prompt="Hello")
        assert exc_info.value.code == "EXCEPTION_302"

    async def test_auth_error_chain(self, mock_llm_server: tuple[MockLLMHandler, int], client: LitellmLLMClient) -> None:
        """验证认证异常映射链路（HTTP 401 → litellm AuthenticationError → LLMAPIError）"""
        handler, _ = mock_llm_server
        handler.set_http_error(401, '{"error": {"message": "auth failed"}}')

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

    async def test_close_flow(self, mock_llm_server: tuple[MockLLMHandler, int], llm_config: LLMConfig) -> None:
        """验证 close() 流程"""
        client = LitellmLLMClient(config=llm_config)
        await client.close()
        assert client._closed is True
        with pytest.raises(ServiceUnavailableError):
            await client.generate(prompt="Hello")
