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
    ValidationError,
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
    async def test_non_integer_max_results_raises_validation_error(self) -> None:
        """max_results 非整数 → ValidationError(201)（R3-2 G4：内置 ValueError 逃逸
        领域异常体系的前置拦截——参数错误归 201 且在发请求前拦截）"""
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(200, json={"results": []})))
        with pytest.raises(ValidationError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="tavily", query="q", parameters=(("max_results", "10.5"),)))
        assert exc_info.value.code == "EXCEPTION_201"
        assert exc_info.value.context.get("field") == "max_results"
        await adapter.close()

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


class TestResultsTypeValidation:
    """results 类型校验（R3-3 H4：非 list 形态静默透传是数据毒丸面）"""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("results_value", [{"unexpected": "dict"}, "not-a-list"])
    async def test_non_list_results_raises_response_error(self, results_value: object) -> None:
        """results 为 dict/str 形态 → 413（结构非法即拒绝，对齐 newsapi/uspto 先例）"""
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(200, json={"results": results_value})))
        with pytest.raises(DataSourceResponseError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="tavily", query="q"))
        assert exc_info.value.code == "EXCEPTION_413"
        await adapter.close()


class TestTavilyCjkAdaptiveParams:
    """Story 4.1f AC-1：CJK query 自适应注入 country=china（官方全名枚举）。

    双态契约：含 CJK → 请求体加 country；不含 CJK → 请求体与既有形态逐键一致（回归基线）。
    """

    @staticmethod
    def _capture_body() -> tuple[list[dict[str, object]], httpx.MockTransport]:
        bodies: list[dict[str, object]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            bodies.append(json.loads(request.content.decode()))
            return httpx.Response(200, json={"results": []})

        return bodies, httpx.MockTransport(handler)

    @pytest.mark.asyncio
    async def test_cjk_query_adds_country_china(self) -> None:
        """中文 query → 请求体自动加 country=china。"""
        bodies, transport = self._capture_body()
        adapter = _make_adapter(transport)
        await adapter.fetch(DataSourceQuery(source_name="tavily", query="比亚迪 战略动态 并购 新能源汽车"))
        assert bodies[0].get("country") == "china"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_mixed_cjk_english_query_adds_country(self) -> None:
        """中英混合 query → 同样注入（检测规则为「含任一 CJK 字符」）。"""
        bodies, transport = self._capture_body()
        adapter = _make_adapter(transport)
        await adapter.fetch(DataSourceQuery(source_name="tavily", query="宁德时代 CATL 产能扩张"))
        assert bodies[0].get("country") == "china"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_non_cjk_query_body_unchanged_baseline(self) -> None:
        """英文 query → 请求体与既有形态逐键一致（回归基线——零既有影响）。"""
        bodies, transport = self._capture_body()
        adapter = _make_adapter(transport)
        await adapter.fetch(DataSourceQuery(source_name="tavily", query="BYD strategy news"))
        assert set(bodies[0]) == {"api_key", "query", "max_results"}, "非 CJK 请求体应零变化"
        await adapter.close()
