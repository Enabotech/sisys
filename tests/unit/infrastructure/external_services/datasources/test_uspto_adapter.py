"""Story 4.1b — USPTOAdapter 单元测试

验证 USPTO 数据源适配器（REST_JSON，专利数据库，公开免费）：
- 成功采集（POST /api/v1/patent/，PatentsView 结构解析）
- 5xx → 411 / 超时 → 302 / 429 → 412 / 解析失败 → 413（不重试）/ 熔断 → 411

测试模式：httpx.MockTransport 注入。
"""

from __future__ import annotations

import json

import httpx
import pytest

from src.domain.exceptions import (
    DataSourceRateLimitError,
    DataSourceResponseError,
    DataSourceUnavailableError,
    TimeoutError,
)
from src.domain.ports.data_source import DataSourcePort, DataSourceQuery
from src.infrastructure.config.uspto import USPTOConfig
from src.infrastructure.external_services.datasources.uspto_adapter import USPTOAdapter

_API_URL = "https://search.patentsview.org"


def _make_adapter(handler: httpx.MockTransport | None = None) -> USPTOAdapter:
    config = USPTOConfig(api_url=_API_URL, timeout=5.0)
    transport = handler or httpx.MockTransport(lambda req: httpx.Response(200, json={"patents": []}))
    return USPTOAdapter(
        config=config,
        client=httpx.AsyncClient(base_url=_API_URL, transport=transport, timeout=5.0),
        retry_min_wait=0.01,
        retry_max_wait=0.02,
    )


def _ok_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={"patents": [{"patent_id": "10000001", "patent_title": "Battery Tech", "patent_date": "2025-06-01"}]},
    )


class TestUSPTOAdapterSuccess:
    @pytest.mark.asyncio
    async def test_fetch_success(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(_ok_handler))
        result = await adapter.fetch(DataSourceQuery(source_name="uspto", query="battery", parameters=(("page_size", "10"),)))
        payload = json.loads(result.payload)
        assert payload["patents"][0]["patent_id"] == "10000001"
        assert result.source_timestamp.year == 2025
        await adapter.close()

    @pytest.mark.asyncio
    async def test_implements_port(self) -> None:
        assert isinstance(_make_adapter(), DataSourcePort)

    def test_get_metadata(self) -> None:
        assert _make_adapter().get_metadata().name == "uspto"

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(_ok_handler))
        assert await adapter.health_check() is True
        await adapter.close()


class TestUSPTOAdapterFailures:
    @pytest.mark.asyncio
    async def test_5xx_retry_exhausted_raises_unavailable(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(500, json={})

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(DataSourceUnavailableError):
            await adapter.fetch(DataSourceQuery(source_name="uspto", query="q"))
        assert calls["n"] == 3
        await adapter.close()

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timeout", request=request)

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(TimeoutError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="uspto", query="q"))
        assert exc_info.value.code == "EXCEPTION_302"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_429_raises_rate_limit(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(429, json={})))
        with pytest.raises(DataSourceRateLimitError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="uspto", query="q"))
        assert exc_info.value.code == "EXCEPTION_412"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_invalid_json_raises_response_error_no_retry(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200, content=b"not json")

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(DataSourceResponseError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="uspto", query="q"))
        assert exc_info.value.code == "EXCEPTION_413"
        assert calls["n"] == 1
        await adapter.close()

    @pytest.mark.asyncio
    async def test_missing_patents_field_raises_response_error(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(200, json={"error": "bad query"})))
        with pytest.raises(DataSourceResponseError):
            await adapter.fetch(DataSourceQuery(source_name="uspto", query="q"))
        await adapter.close()

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(503, json={})))
        for _ in range(2):
            with pytest.raises(DataSourceUnavailableError):
                await adapter.fetch(DataSourceQuery(source_name="uspto", query="q"))
        with pytest.raises(DataSourceUnavailableError):
            await adapter.fetch(DataSourceQuery(source_name="uspto", query="q"))
        await adapter.close()
