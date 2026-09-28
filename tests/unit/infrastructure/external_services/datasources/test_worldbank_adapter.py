"""Story 4.1b — WorldBankAdapter 单元测试

验证 World Bank 数据源适配器（REST_JSON，无 API Key）：
- 成功采集（[meta, rows] 结构解析 + required_fields 校验 + freshness/confidence 元数据）
- 5xx 重试耗尽 → DataSourceUnavailableError(411)
- 超时 → TimeoutError(302)
- 429 → DataSourceRateLimitError(412)
- 响应解析失败 → DataSourceResponseError(413)，不重试
- 熔断器断开 → DataSourceUnavailableError(411)

测试模式：httpx.MockTransport 注入（范本 tests/unit/infrastructure/crawler/test_http_crawler_client.py）。
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
from src.infrastructure.config.worldbank import WorldBankConfig
from src.infrastructure.external_services.datasources.worldbank_adapter import WorldBankAdapter

_API_URL = "https://api.worldbank.org/v2"


def _make_adapter(handler: httpx.MockTransport | None = None) -> WorldBankAdapter:
    """构造注入 MockTransport 的适配器（测试工厂，快速重试）。"""
    config = WorldBankConfig(api_url=_API_URL, timeout=5.0)
    transport = handler or httpx.MockTransport(lambda req: httpx.Response(200, json=[{}, []]))
    return WorldBankAdapter(
        config=config,
        client=httpx.AsyncClient(base_url=_API_URL, transport=transport, timeout=5.0),
        retry_min_wait=0.01,
        retry_max_wait=0.02,
    )


def _ok_handler(request: httpx.Request) -> httpx.Response:
    rows = [{"indicator": {"id": "NY.GDP.MKTP.CD"}, "country": {"id": "CN"}, "value": 17794062650765.4, "date": "2024"}]
    return httpx.Response(200, json=[{"page": 1, "pages": 1}, rows])


class TestWorldBankAdapterSuccess:
    @pytest.mark.asyncio
    async def test_fetch_success(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(_ok_handler))
        result = await adapter.fetch(
            DataSourceQuery(source_name="world-bank", query="NY.GDP.MKTP.CD", parameters=(("country", "CN"),))
        )
        assert result.source_name == "world-bank"
        payload = json.loads(result.payload)
        assert payload[0]["value"] == 17794062650765.4
        assert result.source_timestamp.year == 2024
        assert 0.0 < result.confidence <= 1.0
        assert result.cache_hit is False
        await adapter.close()

    @pytest.mark.asyncio
    async def test_implements_port(self) -> None:
        assert isinstance(_make_adapter(), DataSourcePort)

    def test_get_metadata(self) -> None:
        ref = _make_adapter().get_metadata()
        assert ref.name == "world-bank"
        assert ref.ttl_seconds == WorldBankConfig().ttl_seconds

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(_ok_handler))
        assert await adapter.health_check() is True
        await adapter.close()


class TestWorldBankURLAndRedirect:
    """R2-2-B6/H4 路径段编码 + R2-2-B7/H5 3xx 映射。"""

    @pytest.mark.asyncio
    async def test_legitimate_indicator_code_url_unchanged(self) -> None:
        """合法指标代码（NY.GDP.MKTP.CD）经 quote 原样通过（回归保护）。"""
        captured: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(str(request.url))
            return _ok_handler(request)

        adapter = _make_adapter(httpx.MockTransport(handler))
        await adapter.fetch(DataSourceQuery(source_name="world-bank", query="NY.GDP.MKTP.CD", parameters=(("country", "CN"),)))
        assert "/country/CN/indicator/NY.GDP.MKTP.CD" in captured[0]
        await adapter.close()

    @pytest.mark.asyncio
    async def test_special_characters_encoded_in_path(self) -> None:
        """空格/斜杠/问号注入字符被 percent 编码（URL 语义不被破坏）。"""
        captured: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(str(request.url))
            return _ok_handler(request)

        adapter = _make_adapter(httpx.MockTransport(handler))
        await adapter.fetch(DataSourceQuery(source_name="world-bank", query="a b/c?d=e"))
        assert "a%20b%2Fc%3Fd%3De" in captured[0]
        assert "?d=e" not in captured[0].split("?")[0]  # 未注入查询串
        await adapter.close()

    @pytest.mark.asyncio
    async def test_dotdot_segment_rejected_413(self) -> None:
        """路径穿越序列（quote 对点号零防护）显式拒绝 → 413。"""
        adapter = _make_adapter()
        with pytest.raises(DataSourceResponseError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="world-bank", query="../admin"))
        assert exc_info.value.code == "EXCEPTION_413"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_redirect_3xx_raises_413_no_retry(self) -> None:
        """301 端点迁移 → 413（确定性配置漂移），不重试；location 仅入 context 禁入 message。"""
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(301, headers={"location": "https://api.worldbank.org/v2/new"})

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(DataSourceResponseError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="world-bank", query="NY.GDP.MKTP.CD"))
        assert exc_info.value.code == "EXCEPTION_413"
        assert calls["n"] == 1  # 不重试
        assert "location" not in exc_info.value.message
        assert exc_info.value.context.get("location") == "https://api.worldbank.org/v2/new"
        await adapter.close()


class TestWorldBankAdapterFailures:
    @pytest.mark.asyncio
    async def test_5xx_retry_exhausted_raises_unavailable(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(503, json={"error": "down"})

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(DataSourceUnavailableError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="world-bank", query="GDP"))
        assert exc_info.value.code == "EXCEPTION_411"
        assert calls["n"] == 3  # 重试 3 次（含首次）
        await adapter.close()

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("read timeout", request=request)

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(TimeoutError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="world-bank", query="GDP"))
        assert exc_info.value.code == "EXCEPTION_302"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_429_raises_rate_limit(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(429, json={})))
        with pytest.raises(DataSourceRateLimitError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="world-bank", query="GDP"))
        assert exc_info.value.code == "EXCEPTION_412"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_invalid_json_raises_response_error_no_retry(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200, content=b"not-json{{{")

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(DataSourceResponseError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="world-bank", query="GDP"))
        assert exc_info.value.code == "EXCEPTION_413"
        assert calls["n"] == 1  # 解析失败不可重试
        await adapter.close()

    @pytest.mark.asyncio
    async def test_malformed_structure_raises_response_error(self) -> None:
        # World Bank 合法响应为 [meta, rows] 列表；返回 dict 视为结构异常
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(200, json={"unexpected": True})))
        with pytest.raises(DataSourceResponseError):
            await adapter.fetch(DataSourceQuery(source_name="world-bank", query="GDP"))
        await adapter.close()

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_threshold(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, json={})

        adapter = _make_adapter(httpx.MockTransport(handler))
        # 默认熔断阈值 5 次连续失败 → 两次 fetch（各 3 次重试）后熔断
        for _ in range(2):
            with pytest.raises(DataSourceUnavailableError):
                await adapter.fetch(DataSourceQuery(source_name="world-bank", query="GDP"))
        # 第三次调用：熔断器已断开，快速失败（不再发起 HTTP）
        with pytest.raises(DataSourceUnavailableError):
            await adapter.fetch(DataSourceQuery(source_name="world-bank", query="GDP"))
        await adapter.close()
