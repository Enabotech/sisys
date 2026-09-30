"""Story 4.1f — UN Comtrade 适配器单元测试

验证 UN Comtrade 数据源适配器（key 可选 + 管道串解析 + 日配额守卫）：
- 注册语义：无条件注册 + preview 端点免 key 兜底；key 缺失构造成功（缺省空串）
- Ocp 头双态：有 key 附加 Ocp-Apim-Subscription-Key / 无 key 不附
- 管道串解析：`reporter=156|cmd=8703|flow=X|period=2024`（cmd 必填缺失 → 201
  输入前置校验；reporter 缺省 156 中国口径）
- 日配额守卫：有 key 500 次/天 / 无 key preview 100 次/天（UTC 00:00 重置，
  now_fn 注入）——超限前置抛 412 零请求消耗；并发安全
- 结构校验：缺 records → 413；失败矩阵（412/411/302/413）

测试模式：httpx.MockTransport 注入（零外网）。
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

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
from src.infrastructure.config.comtrade import ComtradeConfig
from src.infrastructure.external_services.datasources.comtrade_adapter import (
    ComtradeAdapter,
    _DailyQuotaGuard,
    _parse_pipeline_query,
)

_API_URL = "https://comtradeapi.un.org"
_FAKE_KEY_PARTS = ("fake-comtrade-", "key-test1234")
_PREVIEW_ENDPOINT = "/public/v1/preview/C/A/HS"

_RECORDS_BODY = {"records": [{"cmd_code": "8703", "trade_value": 1234567, "period": "2024"}]}


def _fake_key() -> str:
    return _FAKE_KEY_PARTS[0] + _FAKE_KEY_PARTS[1]


def _make_adapter(
    handler: httpx.MockTransport | None = None,
    *,
    api_key: str = "",
    quota_requests_used: int = 0,
    now_fn=None,
) -> ComtradeAdapter:
    transport = handler or httpx.MockTransport(lambda req: httpx.Response(200, json=_RECORDS_BODY))
    return ComtradeAdapter(
        config=ComtradeConfig(api_key=api_key, api_url=_API_URL, timeout=5.0),
        client=httpx.AsyncClient(base_url=_API_URL, transport=transport, timeout=5.0),
        retry_min_wait=0.01,
        retry_max_wait=0.02,
        quota_requests_used=quota_requests_used,
        now_fn=now_fn,
    )


class TestComtradeConfig:
    def test_from_env_reads_four_variables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COMTRADE_API_KEY", _fake_key())
        monkeypatch.setenv("COMTRADE_API_URL", "https://comtrade.example.org")
        monkeypatch.setenv("COMTRADE_TIMEOUT", "15.0")
        monkeypatch.setenv("COMTRADE_TTL_SECONDS", "3600")
        config = ComtradeConfig.from_env()
        assert config.api_key == _fake_key()
        assert config.api_url == "https://comtrade.example.org"
        assert config.timeout == 15.0
        assert config.ttl_seconds == 3600

    def test_from_env_missing_key_defaults_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """key 可选语义：缺失时缺省空串 = 无 key 走 preview 裸模式（构造器不抛）。"""
        monkeypatch.delenv("COMTRADE_API_KEY", raising=False)
        config = ComtradeConfig.from_env()
        assert config.api_key == ""

    def test_from_env_invalid_timeout_raises_configuration_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.domain.exceptions import ConfigurationError

        monkeypatch.setenv("COMTRADE_TIMEOUT", "abc")
        with pytest.raises(ConfigurationError):
            ComtradeConfig.from_env()


class TestPipelineQueryParsing:
    def test_full_pipeline_with_all_params(self) -> None:
        params = _parse_pipeline_query("reporter=156|cmd=8703|flow=X|period=2024")
        assert params == {"reporterCode": "156", "cmdCode": "8703", "flowCode": "X", "period": "2024"}

    def test_reporter_defaults_to_china(self) -> None:
        params = _parse_pipeline_query("cmd=8703")
        assert params["reporterCode"] == "156", "reporter 缺省 156（中国口径）"
        assert params["cmdCode"] == "8703"

    def test_missing_cmd_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            _parse_pipeline_query("reporter=156|flow=X")
        assert exc_info.value.code == "EXCEPTION_201"

    def test_empty_query_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            _parse_pipeline_query("")


class TestOcpHeaderDualState:
    @pytest.mark.asyncio
    async def test_with_key_attaches_subscription_header(self) -> None:
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json=_RECORDS_BODY)

        adapter = _make_adapter(httpx.MockTransport(handler), api_key=_fake_key())
        await adapter.fetch(DataSourceQuery(source_name="comtrade", query="reporter=156|cmd=8703"))
        assert captured[0].headers.get("Ocp-Apim-Subscription-Key") == _fake_key()

    @pytest.mark.asyncio
    async def test_without_key_omits_subscription_header(self) -> None:
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json=_RECORDS_BODY)

        adapter = _make_adapter(httpx.MockTransport(handler))
        await adapter.fetch(DataSourceQuery(source_name="comtrade", query="reporter=156|cmd=8703"))
        assert "ocp-apim-subscription-key" not in {k.lower() for k in captured[0].headers}

    @pytest.mark.asyncio
    async def test_preview_endpoint_path(self) -> None:
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json=_RECORDS_BODY)

        adapter = _make_adapter(httpx.MockTransport(handler))
        await adapter.fetch(DataSourceQuery(source_name="comtrade", query="cmd=8703|period=2024"))
        assert _PREVIEW_ENDPOINT in str(captured[0].url)
        params = dict(captured[0].url.params)
        assert params.get("cmdCode") == "8703" and params.get("period") == "2024"


class TestDailyQuotaGuard:
    @pytest.mark.asyncio
    async def test_with_key_limit_500_preflight_blocks(self) -> None:
        guard = _DailyQuotaGuard(api_key_present=True, quota_requests_used=500)
        with pytest.raises(DataSourceRateLimitError) as exc_info:
            await guard.ensure_capacity()
        assert exc_info.value.code == "EXCEPTION_412"
        assert "500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_without_key_preview_limit_100(self) -> None:
        """无 key preview 模式保守值 100 次/天（Task 0 定稿）。"""
        guard = _DailyQuotaGuard(api_key_present=False, quota_requests_used=100)
        with pytest.raises(DataSourceRateLimitError):
            await guard.ensure_capacity()
        # 99 次未满不抛
        guard_ok = _DailyQuotaGuard(api_key_present=False, quota_requests_used=99)
        await guard_ok.ensure_capacity()

    @pytest.mark.asyncio
    async def test_daily_reset_by_now_fn(self) -> None:
        day1 = datetime(2026, 9, 30, 12, 0, 0, tzinfo=UTC)
        day2 = datetime(2026, 10, 1, 0, 0, 30, tzinfo=UTC)  # 越过 UTC 00:00
        guard = _DailyQuotaGuard(api_key_present=True, quota_requests_used=500, now_fn=lambda: day1)
        with pytest.raises(DataSourceRateLimitError):
            await guard.ensure_capacity()
        guard._now_fn = lambda: day2
        await guard.ensure_capacity()  # 日窗口重置（不抛）

    @pytest.mark.asyncio
    async def test_concurrent_consume_under_lock(self) -> None:
        """并发计数精确性的行为回归防线（非锁存在性证明——当前临界区无 await、
        单 loop 下天然串行；未来临界区演化出 await 引入竞争丢失更新时本测试变红）。"""
        guard = _DailyQuotaGuard(api_key_present=True)

        async def consume_once() -> None:
            await guard.consume()

        await asyncio.gather(*(consume_once() for _ in range(30)))
        assert guard.used_requests == 30


class TestComtradeAdapterFetch:
    @pytest.mark.asyncio
    async def test_fetch_success_structured_records(self) -> None:
        adapter = _make_adapter()
        result = await adapter.fetch(DataSourceQuery(source_name="comtrade", query="reporter=156|cmd=8703|flow=X|period=2024"))
        payload = json.loads(result.payload)
        assert payload["records"][0]["cmd_code"] == "8703"
        assert {"cmd_code", "trade_value", "period"} <= set(payload["records"][0])
        assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_monthly_period_parsed_to_month_not_year(self) -> None:
        """月频 period（YYYYMM）时效锚定到月首——截断为年会虚增 age 达 11 个月误判过期（R1-F11）。"""
        monthly_body = {"records": [{"cmd_code": "8703", "trade_value": 1, "period": "202411"}]}
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(200, json=monthly_body)))
        result = await adapter.fetch(DataSourceQuery(source_name="comtrade", query="reporter=156|cmd=8703|period=202411"))
        assert result.freshness.source_timestamp is not None
        assert (result.freshness.source_timestamp.year, result.freshness.source_timestamp.month) == (2024, 11), (
            "YYYYMM 形态应解析到该年该月，而非截断为年初"
        )
        await adapter.close()

    @pytest.mark.asyncio
    async def test_quota_exhausted_preflight_zero_requests(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200, json=_RECORDS_BODY)

        adapter = _make_adapter(httpx.MockTransport(handler), api_key=_fake_key(), quota_requests_used=500)
        with pytest.raises(DataSourceRateLimitError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="comtrade", query="cmd=8703"))
        assert exc_info.value.code == "EXCEPTION_412"
        assert calls["n"] == 0, "守卫前置拦截——零请求消耗"

    @pytest.mark.asyncio
    async def test_request_counted_into_daily_quota(self) -> None:
        adapter = _make_adapter()
        await adapter.fetch(DataSourceQuery(source_name="comtrade", query="cmd=8703"))
        assert adapter.quota_used_requests == 1

    @pytest.mark.asyncio
    async def test_missing_cmd_zero_requests(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200, json=_RECORDS_BODY)

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(ValidationError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="comtrade", query="reporter=156|flow=X"))
        assert exc_info.value.code == "EXCEPTION_201"
        assert calls["n"] == 0

    def test_get_metadata(self) -> None:
        ref = _make_adapter().get_metadata()
        assert ref.name == "comtrade"
        assert ref.url == _API_URL
        assert ref.api_type.value == "rest_json"
        assert ref.ttl_seconds == 604800
        assert ref.required_fields == ()

    @pytest.mark.asyncio
    async def test_implements_port(self) -> None:
        assert isinstance(_make_adapter(), DataSourcePort)

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        adapter = _make_adapter()
        assert await adapter.health_check() is True
        # 探活请求同样计入日配额（探活是真实消耗——R1-F12，防配额旁路）
        assert adapter._quota_guard.used_requests == 1, "探活成功后日配额计数应为 1"


class TestComtradeAdapterFailures:
    @pytest.mark.asyncio
    async def test_429_raises_rate_limit(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(429)))
        with pytest.raises(DataSourceRateLimitError):
            await adapter.fetch(DataSourceQuery(source_name="comtrade", query="cmd=8703"))

    @pytest.mark.asyncio
    async def test_5xx_retry_exhausted_raises_unavailable(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(503)

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(DataSourceUnavailableError):
            await adapter.fetch(DataSourceQuery(source_name="comtrade", query="cmd=8703"))
        assert calls["n"] == 3

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timeout", request=request)

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(TimeoutError):
            await adapter.fetch(DataSourceQuery(source_name="comtrade", query="cmd=8703"))

    @pytest.mark.asyncio
    async def test_missing_records_field_raises_response_error(self) -> None:
        """双形态皆缺（无 records 契约键亦无 data 真实端点键）→ 413（{"data": []} 属真实端点合法空结果）。"""
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(200, json={"unexpected": 1})))
        with pytest.raises(DataSourceResponseError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="comtrade", query="cmd=8703"))
        assert exc_info.value.code == "EXCEPTION_413"


class TestRealEndpointShapeConversion:
    """真实端点 data[] 形态转换（契约四「195 条真实记录」锚点形态——cmdCode/primaryValue/refYear）。"""

    @pytest.mark.asyncio
    async def test_data_list_converted_to_records(self) -> None:
        real_body = {
            "elapsedTime": 12,
            "count": 1,
            "data": [{"cmdCode": "8703", "flowCode": "X", "primaryValue": 90220553898.0, "refYear": 2024, "period": "2024"}],
        }
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(200, json=real_body)))
        result = await adapter.fetch(DataSourceQuery(source_name="comtrade", query="reporter=156|cmd=8703"))
        payload = json.loads(result.payload)
        assert payload["records"][0]["cmd_code"] == "8703"
        assert payload["records"][0]["trade_value"] == 90220553898.0
        assert payload["records"][0]["period"] == "2024"
        await adapter.close()
