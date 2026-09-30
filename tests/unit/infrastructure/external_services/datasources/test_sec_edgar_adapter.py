"""Story 4.1f — SEC EDGAR 适配器单元测试

验证 SEC EDGAR 数据源适配器（免 key + 强制 UA + 限速 + 双模式检索）：
- UA 规范：全部请求携带「公司名 邮箱」格式 UA 头（官方 Fair Access 义务）
- 限速：滑动窗口令牌桶 8 req/s（官方 10 留余量）——并发 10 请求实测节流（断言仅下界）
- 双模式：检索模式缺省（efts search-index + forms 解析）/ xbrl: 前缀分派（data.sec.gov
  companyconcept 绝对 URL 拼接——单 client 双 base）/ 非法前缀 → 201（输入前置校验）
- 结构校验：缺 filings/concept → 413；失败矩阵（302/411/412/413/熔断）

测试模式：httpx.MockTransport 注入（零外网）。
"""

from __future__ import annotations

import asyncio
import json
import re
import time

import httpx
import pytest

from src.domain.exceptions import (
    DataSourceRateLimitError,
    DataSourceResponseError,
    DataSourceUnavailableError,
    TimeoutError,
    ValidationError,
)
from src.domain.ports.data_source import DataSourcePort, DataSourceQuery
from src.infrastructure.config.sec_edgar import SecEdgarConfig
from src.infrastructure.external_services.datasources.sec_edgar_adapter import (
    UA_HEADER,
    SecEdgarAdapter,
    _compute_delay,
)
from src.infrastructure.external_services.embedding.circuit_breaker import CircuitBreaker

_EFTS_URL = "https://efts.sec.gov"
_DATA_URL = "https://data.sec.gov"

_FILINGS_BODY = {"filings": [{"company": "Tesla", "cik": "1318605", "form": "10-K", "filed_at": "2026-01-30"}]}
_XBRL_BODY = {"concept": "Revenues", "unit": "USD", "values": [{"end": "2024-12-31", "val": 97690}]}


def _make_config() -> SecEdgarConfig:
    return SecEdgarConfig(api_url=_EFTS_URL, timeout=5.0)


def _make_adapter(
    handler: httpx.MockTransport | None = None,
    *,
    rate_limited: bool = True,
    circuit_breaker: CircuitBreaker | None = None,
) -> SecEdgarAdapter:
    transport = handler or httpx.MockTransport(lambda req: httpx.Response(200, json=_FILINGS_BODY))
    return SecEdgarAdapter(
        config=_make_config(),
        client=httpx.AsyncClient(base_url=_EFTS_URL, transport=transport, timeout=5.0),
        retry_min_wait=0.01,
        retry_max_wait=0.02,
        rate_limited=rate_limited,
        circuit_breaker=circuit_breaker,
    )


def _is_data_url(url: str) -> bool:
    return url.startswith(_DATA_URL)


class TestSecEdgarConfig:
    def test_from_env_reads_three_variables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SEC_EDGAR_API_URL", "https://efts.example.gov")
        monkeypatch.setenv("SEC_EDGAR_TIMEOUT", "8.0")
        monkeypatch.setenv("SEC_EDGAR_TTL_SECONDS", "3600")
        config = SecEdgarConfig.from_env()
        assert config.api_url == "https://efts.example.gov"
        assert config.timeout == 8.0
        assert config.ttl_seconds == 3600

    def test_from_env_invalid_ttl_raises_configuration_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SEC_EDGAR_TTL_SECONDS", "abc")
        from src.domain.exceptions import ConfigurationError

        with pytest.raises(ConfigurationError):
            SecEdgarConfig.from_env()


class TestUserAgentHeader:
    @pytest.mark.asyncio
    async def test_all_requests_carry_official_ua(self) -> None:
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json=_XBRL_BODY if _is_data_url(str(request.url)) else _FILINGS_BODY)

        adapter = _make_adapter(httpx.MockTransport(handler), rate_limited=False)
        await adapter.fetch(DataSourceQuery(source_name="sec-edgar", query="market share"))
        await adapter.fetch(DataSourceQuery(source_name="sec-edgar", query="xbrl:CIK0001318605:Revenues"))
        assert len(captured) == 2
        for request in captured:
            ua = request.headers.get("user-agent", "")
            assert "sisys-tools" in ua and "@" in ua, f"UA 应为公司名+邮箱格式（官方 Fair Access），实际: {ua!r}"
        await adapter.close()


class TestSlidingWindowRateLimiter:
    def test_compute_delay_pure_function(self) -> None:
        """refill 纯函数：窗口已满 → 返回最老时间戳出窗所需等待；未满 → 0。"""
        now = 100.0
        # 同刻满载（最老 100.0，距 now 0）→ 需等满整个窗口 1.0s
        assert _compute_delay([100.0] * 8, now, rate=8.0) == pytest.approx(1.0)
        # 最老时间戳 99.5（距 now 0.5s）→ 出窗需再等 0.5s
        assert _compute_delay([99.5] * 8, now, rate=8.0) == pytest.approx(0.5)
        # 恰好出窗（距 now = window）与未满 → 零等待
        assert _compute_delay([99.0] * 8, now, rate=8.0) == 0.0
        assert _compute_delay([99.0] * 7, now, rate=8.0) == 0.0
        assert _compute_delay([], now, rate=8.0) == 0.0

    @pytest.mark.asyncio
    async def test_ten_concurrent_requests_throttled_lower_bound(self) -> None:
        """并发 10 请求经 8 req/s 节流——断言仅下界（elapsed ≥ 1.0s 证明确实节流；不设紧凑上界防 CI 慢机 flaky）。"""
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200, json=_FILINGS_BODY)

        adapter = _make_adapter(httpx.MockTransport(handler))
        start = time.monotonic()
        await asyncio.gather(*(adapter.fetch(DataSourceQuery(source_name="sec-edgar", query=f"q{i}")) for i in range(10)))
        elapsed = time.monotonic() - start
        assert calls["n"] == 10
        assert elapsed >= 1.0, f"8 req/s 节流下 10 请求应至少约 1.125s，实际 {elapsed:.2f}s"
        await adapter.close()


class TestSearchMode:
    @pytest.mark.asyncio
    async def test_search_mode_success_and_structured(self) -> None:
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json=_FILINGS_BODY)

        adapter = _make_adapter(httpx.MockTransport(handler), rate_limited=False)
        result = await adapter.fetch(DataSourceQuery(source_name="sec-edgar", query='"market share" forms=10-K'))
        assert "/LATEST/search-index" in str(captured[0].url)
        params = dict(captured[0].url.params)
        assert params.get("q") == "market share"
        assert params.get("forms") == "10-K"
        payload = json.loads(result.payload)
        assert payload["filings"][0]["company"] == "Tesla"
        assert {"company", "form", "filed_at"} <= set(payload["filings"][0])
        assert result.confidence == 0.95
        await adapter.close()

    @pytest.mark.asyncio
    async def test_pure_keyword_query_without_forms(self) -> None:
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json=_FILINGS_BODY)

        adapter = _make_adapter(httpx.MockTransport(handler), rate_limited=False)
        await adapter.fetch(DataSourceQuery(source_name="sec-edgar", query="battery market"))
        params = dict(captured[0].url.params)
        assert params.get("q") == "battery market"
        assert "forms" not in params
        await adapter.close()

    @pytest.mark.asyncio
    async def test_missing_filings_field_raises_response_error(self) -> None:
        handler = httpx.MockTransport(lambda req: httpx.Response(200, json={"unexpected": 1}))
        adapter = _make_adapter(handler, rate_limited=False)
        with pytest.raises(DataSourceResponseError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="sec-edgar", query="market share"))
        assert exc_info.value.code == "EXCEPTION_413"
        await adapter.close()


class TestXbrlMode:
    @pytest.mark.asyncio
    async def test_xbrl_prefix_dispatches_to_companyconcept(self) -> None:
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json=_XBRL_BODY)

        adapter = _make_adapter(httpx.MockTransport(handler), rate_limited=False)
        result = await adapter.fetch(DataSourceQuery(source_name="sec-edgar", query="xbrl:CIK0001318605:Revenues"))
        url = str(captured[0].url)
        assert url.startswith(f"{_DATA_URL}/api/xbrl/companyconcept/CIK0001318605/us-gaap/Revenues"), (
            f"xbrl: 前缀应分派至 data.sec.gov companyconcept 绝对 URL，实际: {url}"
        )
        payload = json.loads(result.payload)
        assert {"concept", "unit", "values"} <= set(payload)
        await adapter.close()

    @pytest.mark.asyncio
    async def test_xbrl_missing_concept_field_raises_response_error(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(200, json={"units": {}})), rate_limited=False)
        with pytest.raises(DataSourceResponseError):
            await adapter.fetch(DataSourceQuery(source_name="sec-edgar", query="xbrl:CIK0001318605:Revenues"))
        await adapter.close()


class TestInvalidPrefix:
    @pytest.mark.asyncio
    async def test_unknown_mode_prefix_raises_validation_error_zero_requests(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200, json=_FILINGS_BODY)

        adapter = _make_adapter(httpx.MockTransport(handler), rate_limited=False)
        with pytest.raises(ValidationError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="sec-edgar", query="bad:foo:bar"))
        assert exc_info.value.code == "EXCEPTION_201"
        assert calls["n"] == 0, "非法前缀属输入前置校验——零请求消耗"

    @pytest.mark.asyncio
    async def test_xbrl_frame_prefix_rejected_as_unimplemented(self) -> None:
        """xbrl-frame: 前缀 201 拦截（frames 模式未实现——R1-F2：此前被白名单放行后静默落入检索模式）。"""

        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200, json=_FILINGS_BODY)

        adapter = _make_adapter(httpx.MockTransport(handler), rate_limited=False)
        with pytest.raises(ValidationError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="sec-edgar", query="xbrl-frame:us-gaap/Revenues/CY2024Q1"))
        assert exc_info.value.code == "EXCEPTION_201"
        assert calls["n"] == 0, "xbrl-frame 未实现须前置拦截——禁止静默落入检索模式返回无关结果"


class TestSecEdgarAdapterFailures:
    @pytest.mark.asyncio
    async def test_429_raises_rate_limit(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(429)), rate_limited=False)
        with pytest.raises(DataSourceRateLimitError):
            await adapter.fetch(DataSourceQuery(source_name="sec-edgar", query="q"))
        await adapter.close()

    @pytest.mark.asyncio
    async def test_5xx_retry_exhausted_raises_unavailable(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(503)

        adapter = _make_adapter(httpx.MockTransport(handler), rate_limited=False)
        with pytest.raises(DataSourceUnavailableError):
            await adapter.fetch(DataSourceQuery(source_name="sec-edgar", query="q"))
        assert calls["n"] == 3
        await adapter.close()

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timeout", request=request)

        adapter = _make_adapter(httpx.MockTransport(handler), rate_limited=False)
        with pytest.raises(TimeoutError):
            await adapter.fetch(DataSourceQuery(source_name="sec-edgar", query="q"))
        await adapter.close()

    @pytest.mark.asyncio
    async def test_invalid_json_raises_response_error(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(200, content=b"###")), rate_limited=False)
        with pytest.raises(DataSourceResponseError):
            await adapter.fetch(DataSourceQuery(source_name="sec-edgar", query="q"))
        await adapter.close()


class TestSecEdgarAdapterPort:
    def test_get_metadata(self) -> None:
        ref = _make_adapter(rate_limited=False).get_metadata()
        assert ref.name == "sec-edgar"
        assert ref.url == _EFTS_URL
        assert ref.api_type.value == "rest_json"
        assert ref.ttl_seconds == 2592000
        assert ref.required_fields == ()

    @pytest.mark.asyncio
    async def test_implements_port(self) -> None:
        assert isinstance(_make_adapter(rate_limited=False), DataSourcePort)

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        adapter = _make_adapter(rate_limited=False)
        assert await adapter.health_check() is True
        await adapter.close()

    @pytest.mark.asyncio
    async def test_circuit_breaker_early_open(self) -> None:
        """熔断差异化配置：注入降阈熔断器（threshold=2），2 次 fetch 失败即断开，断开期间零 HTTP。

        注：熔断计数按"采集会话"记（每次 fetch 重试耗尽后记 1 次失败——helper 终端
        except 单点 on_failure）。断言核心 = 断开期间计数器不增（快速失败）。
        """
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(503)

        adapter = _make_adapter(
            httpx.MockTransport(handler),
            rate_limited=False,
            circuit_breaker=CircuitBreaker(failure_threshold=2, recovery_timeout=30.0, name="sec-edgar-cb-test"),
        )
        for _ in range(2):
            with pytest.raises(DataSourceUnavailableError):
                await adapter.fetch(DataSourceQuery(source_name="sec-edgar", query="q"))
        calls_before = calls["n"]
        with pytest.raises(DataSourceUnavailableError):
            await adapter.fetch(DataSourceQuery(source_name="sec-edgar", query="q"))
        assert calls["n"] == calls_before, "熔断器断开后应零 HTTP 快速失败"
        await adapter.close()

    def test_ua_header_constant_format(self) -> None:
        assert "sisys-tools" in UA_HEADER and "@" in UA_HEADER
        assert re.match(r"^[^()\s]+/[^()\s]+ \([^()]+\)$", UA_HEADER), "官方 Fair Access「公司名 邮箱」格式"


class TestSearchModeRealEndpointShape:
    """真实端点 Elasticsearch 形态转换（契约三箭头语义——hits.hits[]._source → filings）。"""

    @pytest.mark.asyncio
    async def test_elasticsearch_shape_converted_to_filings(self) -> None:
        es_body = {
            "took": 5,
            "hits": {
                "total": {"value": 1},
                "hits": [
                    {
                        "_id": "0000757011-13-000001",
                        "_source": {
                            "ciks": ["757011"],
                            "display_names": ["USG CORP  (CIK 0000757011)"],
                            "form": "10-K",
                            "file_date": "2013-02-15",
                        },
                    }
                ],
            },
        }
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(200, json=es_body)), rate_limited=False)
        result = await adapter.fetch(DataSourceQuery(source_name="sec-edgar", query="market share"))
        payload = json.loads(result.payload)
        assert payload["filings"][0]["company"] == "USG CORP  (CIK 0000757011)"
        assert payload["filings"][0]["form"] == "10-K"
        assert payload["filings"][0]["filed_at"] == "2013-02-15"
        await adapter.close()
