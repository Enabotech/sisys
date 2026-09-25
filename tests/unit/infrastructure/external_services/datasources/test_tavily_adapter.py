"""Story 4.1b — TavilyAdapter 单元测试

验证 Tavily 数据源适配器（REST_JSON + API Key）：
- 成功采集（POST /search，Key 走请求体，URL 零泄露）
- 配置缺失 API Key → ConfigurationError(101)（构造时快速失败）
- 429 → 412 / 5xx → 411 / 超时 → 302 / 解析失败 → 413（不重试）/ 熔断 → 411
- Key 安全：异常消息/to_dict/请求 URL 零 Key 泄露

测试模式：httpx.MockTransport 注入。
"""

from __future__ import annotations

import json

import httpx
import pytest

from src.domain.exceptions import (
    ConfigurationError,
    DataSourceRateLimitError,
    DataSourceResponseError,
    DataSourceUnavailableError,
    TimeoutError,
)
from src.domain.ports.data_source import DataSourcePort, DataSourceQuery
from src.infrastructure.config.tavily import TavilyConfig
from src.infrastructure.external_services.datasources.tavily_adapter import TavilyAdapter

_API_URL = "https://api.tavily.com"
_SENTINEL_KEY = "tvly-test-sentinel-key-123"


def _make_adapter(handler: httpx.MockTransport | None = None) -> TavilyAdapter:
    config = TavilyConfig(api_key=_SENTINEL_KEY, api_url=_API_URL, timeout=5.0)
    transport = handler or httpx.MockTransport(lambda req: httpx.Response(200, json={"results": []}))
    return TavilyAdapter(
        config=config,
        client=httpx.AsyncClient(base_url=_API_URL, transport=transport, timeout=5.0),
        retry_min_wait=0.01,
        retry_max_wait=0.02,
    )


def _ok_handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content.decode())
    assert body["api_key"] == _SENTINEL_KEY  # Key 走请求体
    assert _SENTINEL_KEY not in str(request.url)  # URL 零泄露
    return httpx.Response(
        200,
        json={"results": [{"title": "AI 趋势", "url": "https://x.com/a", "content": "...", "score": 0.9}], "answer": "..."},
    )


class TestTavilyAdapterConfig:
    def test_missing_key_raises_configuration_error(self) -> None:
        with pytest.raises(ConfigurationError) as exc_info:
            TavilyAdapter(config=TavilyConfig(api_key=""))
        assert exc_info.value.code == "EXCEPTION_101"
        # 消息不得泄露任何 Key 材料
        assert _SENTINEL_KEY not in str(exc_info.value)

    def test_config_repr_masks_key(self) -> None:
        config = TavilyConfig(api_key=_SENTINEL_KEY)
        assert _SENTINEL_KEY not in repr(config)
        assert _SENTINEL_KEY not in str(config)


class TestTavilyAdapterSuccess:
    @pytest.mark.asyncio
    async def test_fetch_success(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(_ok_handler))
        result = await adapter.fetch(DataSourceQuery(source_name="tavily", query="AI 战略趋势"))
        assert result.source_name == "tavily"
        payload = json.loads(result.payload)
        assert payload["results"][0]["title"] == "AI 趋势"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_implements_port(self) -> None:
        assert isinstance(_make_adapter(), DataSourcePort)

    def test_get_metadata(self) -> None:
        assert _make_adapter().get_metadata().name == "tavily"

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(_ok_handler))
        assert await adapter.health_check() is True
        await adapter.close()


class TestTavilyAdapterFailures:
    @pytest.mark.asyncio
    async def test_429_raises_rate_limit(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(429, json={})))
        with pytest.raises(DataSourceRateLimitError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="tavily", query="q"))
        assert exc_info.value.code == "EXCEPTION_412"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_5xx_retry_exhausted_raises_unavailable(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(503, json={})

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(DataSourceUnavailableError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="tavily", query="q"))
        assert exc_info.value.code == "EXCEPTION_411"
        assert calls["n"] == 3
        await adapter.close()

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timeout", request=request)

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(TimeoutError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="tavily", query="q"))
        assert exc_info.value.code == "EXCEPTION_302"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_invalid_json_raises_response_error_no_retry(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200, content=b"###")

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(DataSourceResponseError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="tavily", query="q"))
        assert exc_info.value.code == "EXCEPTION_413"
        assert calls["n"] == 1
        await adapter.close()

    @pytest.mark.asyncio
    async def test_missing_results_field_raises_response_error(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(200, json={"answer": "x"})))
        with pytest.raises(DataSourceResponseError):
            await adapter.fetch(DataSourceQuery(source_name="tavily", query="q"))
        await adapter.close()

    @pytest.mark.asyncio
    async def test_error_response_zero_key_leak(self) -> None:
        """错误路径零 Key 泄露：cause 链 + context + to_dict 均不含 Key。"""
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(500, json={"error": "boom"})))
        with pytest.raises(DataSourceUnavailableError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="tavily", query="q"))
        serialized = json.dumps(exc_info.value.to_dict(), ensure_ascii=False)
        assert _SENTINEL_KEY not in serialized
        assert _SENTINEL_KEY not in str(exc_info.value)
        await adapter.close()

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(503, json={})))
        for _ in range(2):
            with pytest.raises(DataSourceUnavailableError):
                await adapter.fetch(DataSourceQuery(source_name="tavily", query="q"))
        with pytest.raises(DataSourceUnavailableError):
            await adapter.fetch(DataSourceQuery(source_name="tavily", query="q"))
        await adapter.close()
