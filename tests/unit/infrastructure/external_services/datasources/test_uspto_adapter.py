"""Story 4.1b — USPTOAdapter 单元测试

验证 USPTO 数据源适配器（REST_JSON，专利数据库，PatentsView v1 强制 X-Api-Key）：
- 成功采集（POST /api/v1/patent/，PatentsView 结构解析）
- X-Api-Key 鉴权头（R3-P1-3：配置 api_key 时携带；空/None 不携带）
- 5xx → 411 / 超时 → 302 / 429 → 412 / 解析失败 → 413（不重试）/ 熔断 → 411

测试模式：httpx.MockTransport 注入。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime

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


def _make_adapter(handler: httpx.MockTransport | None = None, api_key: str | None = None) -> USPTOAdapter:
    config = USPTOConfig(api_url=_API_URL, timeout=5.0, api_key=api_key)
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


class TestUSPTOApiKeyAuth:
    """X-Api-Key 鉴权头（R3-P1-3：PatentsView v1 端点强制鉴权）"""

    @pytest.mark.asyncio
    async def test_api_key_sent_in_header_when_configured(self) -> None:
        """配置 api_key 时请求携带 X-Api-Key 头（bool 真值判定）"""
        captured: list[httpx.Request] = []

        def capture_handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json={"patents": []})

        adapter = _make_adapter(httpx.MockTransport(capture_handler), api_key="test-key-123")
        await adapter.fetch(DataSourceQuery(source_name="uspto", query="battery"))
        assert captured[0].headers.get("X-Api-Key") == "test-key-123"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_empty_api_key_omits_header(self) -> None:
        """api_key 为空串/None 时不发送鉴权头（空串=未配置，与组合根 bool() 口径一致——
        防止 USPTO_API_KEY="" 时裸发空 Key 产生批量 401）"""

        def make_capture_handler(store: list[httpx.Request]) -> Callable[[httpx.Request], httpx.Response]:
            def handler(request: httpx.Request) -> httpx.Response:
                store.append(request)
                return httpx.Response(200, json={"patents": []})

            return handler

        for empty_key in ("", None):
            captured: list[httpx.Request] = []
            adapter = _make_adapter(httpx.MockTransport(make_capture_handler(captured)), api_key=empty_key)
            await adapter.fetch(DataSourceQuery(source_name="uspto", query="battery"))
            assert "X-Api-Key" not in captured[0].headers
            await adapter.close()

    def test_config_repr_redacts_api_key(self) -> None:
        """USPTOConfig __repr__ 不泄露 api_key（硬约束：配置类脱敏，对齐 newsapi/tavily）"""
        config = USPTOConfig(api_key="sk-super-secret-999")
        assert "sk-super-secret-999" not in repr(config)


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


class TestUSPTOTimestampNormalization:
    """R2-2-B5/H3 naive/aware 双分支归一。"""

    @pytest.mark.asyncio
    async def test_aware_offset_converted_to_utc_instant(self) -> None:
        """带偏移 patent_date 换算到 UTC 同一时刻。"""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"patents": [{"patent_id": "10000001", "patent_title": "T", "patent_date": "2025-06-01T08:00:00+08:00"}]},
            )

        adapter = _make_adapter(httpx.MockTransport(handler))
        result = await adapter.fetch(DataSourceQuery(source_name="uspto", query="battery"))
        assert result.source_timestamp == datetime(2025, 6, 1, 0, 0, tzinfo=UTC)
        await adapter.close()


class TestUSPTOAdapterFailures:
    @pytest.mark.asyncio
    async def test_non_integer_page_size_raises_validation_error(self) -> None:
        """page_size 非整数 → ValidationError(201)（R3-2 G4：内置 ValueError 逃逸
        领域异常体系的前置拦截——参数错误归 201 且在发请求前拦截）"""
        from src.domain.exceptions import ValidationError

        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(200, json={"patents": []})))
        with pytest.raises(ValidationError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="uspto", query="q", parameters=(("page_size", "xyz"),)))
        assert exc_info.value.code == "EXCEPTION_201"
        assert exc_info.value.context.get("field") == "page_size"
        await adapter.close()

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
