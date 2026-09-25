"""Story 4.1b — NewsAPIAdapter 单元测试

验证 NewsAPI 数据源适配器（REST_JSON + API Key，免费 100 次/天）：
- 成功采集（GET /v2/everything，Key 走 X-Api-Key 请求头，URL 零泄露）
- 配置缺失 API Key → ConfigurationError(101)
- 429 → 412（配额敏感，熔断 2 次/600s 早断开）/ 5xx → 411 / 超时 → 302 / 解析失败 → 413

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
from src.infrastructure.config.newsapi import NewsAPIConfig
from src.infrastructure.external_services.datasources.newsapi_adapter import NewsAPIAdapter

_API_URL = "https://newsapi.org"
_SENTINEL_KEY = "newsapi-test-sentinel-key-456"


def _make_adapter(handler: httpx.MockTransport | None = None) -> NewsAPIAdapter:
    config = NewsAPIConfig(api_key=_SENTINEL_KEY, api_url=_API_URL, timeout=5.0)
    transport = handler or httpx.MockTransport(lambda req: httpx.Response(200, json={"status": "ok", "articles": []}))
    return NewsAPIAdapter(
        config=config,
        client=httpx.AsyncClient(base_url=_API_URL, transport=transport, timeout=5.0),
        retry_min_wait=0.01,
        retry_max_wait=0.02,
    )


def _ok_handler(request: httpx.Request) -> httpx.Response:
    assert request.headers.get("X-Api-Key") == _SENTINEL_KEY  # Key 走请求头
    assert _SENTINEL_KEY not in str(request.url)  # URL 零泄露
    return httpx.Response(
        200,
        json={
            "status": "ok",
            "totalResults": 1,
            "articles": [{"title": "新能源政策", "url": "https://n.com/1", "publishedAt": "2026-09-01T08:00:00Z"}],
        },
    )


class TestNewsAPIAdapterConfig:
    def test_missing_key_raises_configuration_error(self) -> None:
        with pytest.raises(ConfigurationError) as exc_info:
            NewsAPIAdapter(config=NewsAPIConfig(api_key=""))
        assert exc_info.value.code == "EXCEPTION_101"

    def test_config_repr_masks_key(self) -> None:
        assert _SENTINEL_KEY not in repr(NewsAPIConfig(api_key=_SENTINEL_KEY))


class TestNewsAPIAdapterSuccess:
    @pytest.mark.asyncio
    async def test_fetch_success(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(_ok_handler))
        result = await adapter.fetch(DataSourceQuery(source_name="newsapi", query="新能源"))
        payload = json.loads(result.payload)
        assert payload["articles"][0]["title"] == "新能源政策"
        assert result.source_timestamp.year == 2026
        assert result.confidence > 0.0
        await adapter.close()

    @pytest.mark.asyncio
    async def test_implements_port(self) -> None:
        assert isinstance(_make_adapter(), DataSourcePort)

    def test_get_metadata(self) -> None:
        assert _make_adapter().get_metadata().name == "newsapi"

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(_ok_handler))
        assert await adapter.health_check() is True
        await adapter.close()


class TestNewsAPIAdapterFailures:
    @pytest.mark.asyncio
    async def test_429_raises_rate_limit(self) -> None:
        """免费 100 次/天限额场景：429 → EXCEPTION_412。"""
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(429, json={"message": "rate limited"})))
        with pytest.raises(DataSourceRateLimitError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="newsapi", query="q"))
        assert exc_info.value.code == "EXCEPTION_412"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_5xx_retry_exhausted_raises_unavailable(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(502, json={})

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(DataSourceUnavailableError):
            await adapter.fetch(DataSourceQuery(source_name="newsapi", query="q"))
        assert calls["n"] == 3
        await adapter.close()

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timeout", request=request)

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(TimeoutError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="newsapi", query="q"))
        assert exc_info.value.code == "EXCEPTION_302"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_invalid_json_raises_response_error_no_retry(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200, content=b"<xml>")

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(DataSourceResponseError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="newsapi", query="q"))
        assert exc_info.value.code == "EXCEPTION_413"
        assert calls["n"] == 1
        await adapter.close()

    @pytest.mark.asyncio
    async def test_missing_articles_field_raises_response_error(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(200, json={"status": "ok"})))
        with pytest.raises(DataSourceResponseError):
            await adapter.fetch(DataSourceQuery(source_name="newsapi", query="q"))
        await adapter.close()

    @pytest.mark.asyncio
    async def test_circuit_breaker_early_open(self) -> None:
        """NewsAPI 熔断差异化配置：2 次 fetch 失败即断开（配额敏感），断开期间不发起 HTTP。

        注：熔断计数按"采集会话"记（每次 fetch 重试耗尽后记 1 次失败），
        failure_threshold=2 → 两次 fetch 失败后断开（对齐 Story AC-2 差异化配置语义）。
        """
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(503, json={})

        adapter = _make_adapter(httpx.MockTransport(handler))
        # 两次 fetch（各重试 3 次耗尽）→ 熔断计数 2 达阈值
        for _ in range(2):
            with pytest.raises(DataSourceUnavailableError):
                await adapter.fetch(DataSourceQuery(source_name="newsapi", query="q"))
        calls_before = calls["n"]
        # 第三次 fetch：熔断器已断开，零 HTTP 调用快速失败
        with pytest.raises(DataSourceUnavailableError):
            await adapter.fetch(DataSourceQuery(source_name="newsapi", query="q"))
        assert calls["n"] == calls_before
        await adapter.close()
