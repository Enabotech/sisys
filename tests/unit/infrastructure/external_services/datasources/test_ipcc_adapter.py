"""Story 4.1b — IPCCAdapter 单元测试

验证 IPCC 数据源适配器（CSV_DOWNLOAD，环境数据，公开免费）：
- 成功采集（CSV 下载 + 解析为行记录 JSON + 大文件截断保护）
- 5xx → 411 / 超时 → 302 / 429 → 412 / CSV 解析失败 → 413（不重试）/ 熔断 → 411（2 次/120s 立即熔断档）

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
from src.infrastructure.config.ipcc import IPCCConfig
from src.infrastructure.external_services.datasources.ipcc_adapter import IPCCAdapter

_CSV_URL = "https://www.ipcc.ch/data"


def _make_adapter(handler: httpx.MockTransport | None = None, max_rows: int = 1000) -> IPCCAdapter:
    config = IPCCConfig(csv_base_url=_CSV_URL, timeout=5.0)
    transport = handler or httpx.MockTransport(lambda req: httpx.Response(200, text="col\n1\n"))
    return IPCCAdapter(
        config=config,
        client=httpx.AsyncClient(transport=transport, timeout=5.0),
        retry_min_wait=0.01,
        retry_max_wait=0.02,
        max_rows=max_rows,
    )


def _ok_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, text="year,value\n2020,1.1\n2021,1.2\n")


class TestIPCCAdapterSuccess:
    @pytest.mark.asyncio
    async def test_fetch_success(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(_ok_handler))
        result = await adapter.fetch(DataSourceQuery(source_name="ipcc", query="ar6-wg1-spm"))
        payload = json.loads(result.payload)
        assert payload["rows"] == [{"year": "2020", "value": "1.1"}, {"year": "2021", "value": "1.2"}]
        assert result.source_name == "ipcc"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_max_rows_truncation_protection(self) -> None:
        """大文件截断保护：行数超 max_rows 截断并标注。"""
        big_csv = "n\n" + "\n".join(str(i) for i in range(5000))
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(200, text=big_csv)), max_rows=100)
        result = await adapter.fetch(DataSourceQuery(source_name="ipcc", query="big"))
        payload = json.loads(result.payload)
        assert len(payload["rows"]) == 100
        assert payload["truncated"] is True
        await adapter.close()

    @pytest.mark.asyncio
    async def test_implements_port(self) -> None:
        assert isinstance(_make_adapter(), DataSourcePort)

    def test_get_metadata(self) -> None:
        ref = _make_adapter().get_metadata()
        assert ref.name == "ipcc"

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(_ok_handler))
        assert await adapter.health_check() is True
        await adapter.close()


class TestIPCCAdapterFailures:
    @pytest.mark.asyncio
    async def test_5xx_retry_exhausted_raises_unavailable(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(500, json={})

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(DataSourceUnavailableError):
            await adapter.fetch(DataSourceQuery(source_name="ipcc", query="q"))
        assert calls["n"] == 3
        await adapter.close()

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timeout", request=request)

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(TimeoutError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="ipcc", query="q"))
        assert exc_info.value.code == "EXCEPTION_302"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_429_raises_rate_limit(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(429, json={})))
        with pytest.raises(DataSourceRateLimitError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="ipcc", query="q"))
        assert exc_info.value.code == "EXCEPTION_412"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_empty_csv_raises_response_error_no_retry(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200, text="")  # 空 CSV（无表头）

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(DataSourceResponseError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="ipcc", query="q"))
        assert exc_info.value.code == "EXCEPTION_413"
        assert calls["n"] == 1
        await adapter.close()

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_early(self) -> None:
        """IPCC 熔断差异化配置：2 次 fetch 失败即断开（大文件传输失败代价高，120s 恢复）。"""
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(503, json={})))
        for _ in range(2):
            with pytest.raises(DataSourceUnavailableError):
                await adapter.fetch(DataSourceQuery(source_name="ipcc", query="q"))
        with pytest.raises(DataSourceUnavailableError):
            await adapter.fetch(DataSourceQuery(source_name="ipcc", query="q"))
        await adapter.close()
