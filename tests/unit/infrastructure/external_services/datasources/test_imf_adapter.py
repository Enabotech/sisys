"""Story 4.1b — IMFAdapter 单元测试

验证 IMF 数据源适配器（SDMX_JSON，World Economic Outlook / DataMapper API）：
- 成功采集（values 嵌套结构解析）
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
from src.infrastructure.config.imf import IMFConfig
from src.infrastructure.external_services.datasources.imf_adapter import IMFAdapter

_API_URL = "https://www.imf.org/external/datamapper/api/v1"


def _make_adapter(handler: httpx.MockTransport | None = None) -> IMFAdapter:
    config = IMFConfig(api_url=_API_URL, timeout=5.0)
    transport = handler or httpx.MockTransport(lambda req: httpx.Response(200, json={"values": {}}))
    return IMFAdapter(
        config=config,
        client=httpx.AsyncClient(base_url=_API_URL, transport=transport, timeout=5.0),
        retry_min_wait=0.01,
        retry_max_wait=0.02,
    )


def _ok_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"values": {"NGDP_RPCH": {"CN": {"2023": 5.2, "2024": 5.0}}}})


class TestIMFAdapterSuccess:
    @pytest.mark.asyncio
    async def test_fetch_success(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(_ok_handler))
        result = await adapter.fetch(DataSourceQuery(source_name="imf", query="NGDP_RPCH", parameters=(("country", "CN"),)))
        assert result.source_name == "imf"
        payload = json.loads(result.payload)
        assert payload["values"]["NGDP_RPCH"]["CN"]["2024"] == 5.0
        assert result.source_timestamp.year == 2024
        await adapter.close()

    @pytest.mark.asyncio
    async def test_implements_port(self) -> None:
        assert isinstance(_make_adapter(), DataSourcePort)

    def test_get_metadata(self) -> None:
        assert _make_adapter().get_metadata().name == "imf"

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(_ok_handler))
        assert await adapter.health_check() is True
        await adapter.close()


class TestIMFAdapterFailures:
    @pytest.mark.asyncio
    async def test_5xx_retry_exhausted_raises_unavailable(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(500, json={})

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(DataSourceUnavailableError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="imf", query="NGDP_RPCH"))
        assert exc_info.value.code == "EXCEPTION_411"
        assert calls["n"] == 3
        await adapter.close()

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timeout", request=request)

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(TimeoutError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="imf", query="NGDP_RPCH"))
        assert exc_info.value.code == "EXCEPTION_302"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_429_raises_rate_limit(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(429, json={})))
        with pytest.raises(DataSourceRateLimitError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="imf", query="NGDP_RPCH"))
        assert exc_info.value.code == "EXCEPTION_412"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_invalid_json_raises_response_error_no_retry(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200, content=b"%%invalid%%")

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(DataSourceResponseError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="imf", query="NGDP_RPCH"))
        assert exc_info.value.code == "EXCEPTION_413"
        assert calls["n"] == 1
        await adapter.close()

    @pytest.mark.asyncio
    async def test_missing_values_field_raises_response_error(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(200, json={"error": "no data"})))
        with pytest.raises(DataSourceResponseError):
            await adapter.fetch(DataSourceQuery(source_name="imf", query="NGDP_RPCH"))
        await adapter.close()

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(503, json={})))
        for _ in range(2):
            with pytest.raises(DataSourceUnavailableError):
                await adapter.fetch(DataSourceQuery(source_name="imf", query="q"))
        with pytest.raises(DataSourceUnavailableError):
            await adapter.fetch(DataSourceQuery(source_name="imf", query="q"))
        await adapter.close()
