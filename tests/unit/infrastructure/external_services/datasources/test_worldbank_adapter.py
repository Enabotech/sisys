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

import asyncio
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
    async def test_message_error_form_raises_413_not_silent_empty_success(self) -> None:
        """World Bank message 错误形态 `[{"message": [...]}, []]` → 413（R3-P1-8 修复）

        无效指标码的真实 API 错误形态：meta 位是含 "message" 键的 dict（正常 meta
        含 page/pages 分页字段，永不含 message 键）。修复前该形态经结构校验返回
        空 rows——产出「高置信度空 payload 成功结果」进缓存（静默数据缺失）。
        """
        adapter = _make_adapter(
            httpx.MockTransport(
                lambda req: httpx.Response(
                    200,
                    json=[
                        {
                            "message": [
                                {"id": "120", "key": "Invalid value", "value": "The provided indicator value is invalid"}
                            ]
                        },
                        [],
                    ],
                )
            )
        )
        with pytest.raises(DataSourceResponseError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="world-bank", query="INVALID.CODE.X"))
        assert exc_info.value.code == "EXCEPTION_413"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_threshold(self) -> None:
        """连续失败达阈值后熔断打开，后续调用快速失败不再发起 HTTP

        熔断计数语义（R3-2 G0 判别力修复）：on_failure 按 fetch 计（tenacity
        3 次重试在外层 except 收敛后仅计 1 次）——threshold=5 需 **5 次 fetch**
        才打开（原 range(2) 从未打开，第三次调用仍发 3 次真实 HTTP，「快速失败」
        断言与真失败不可判别）；第 6 次调用 transport 计数保持不变才是真快速失败。
        """
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(503, json={})

        adapter = _make_adapter(httpx.MockTransport(handler))
        # 5 次 fetch（各 3 次重试 = 15 次 HTTP，各计 1 次 on_failure）→ 熔断打开
        for _ in range(5):
            with pytest.raises(DataSourceUnavailableError):
                await adapter.fetch(DataSourceQuery(source_name="world-bank", query="GDP"))
        assert calls["n"] == 15
        # 第 6 次调用：熔断器已断开，快速失败——transport 计数保持 15（不再发起 HTTP）
        with pytest.raises(DataSourceUnavailableError):
            await adapter.fetch(DataSourceQuery(source_name="world-bank", query="GDP"))
        assert calls["n"] == 15
        await adapter.close()

    @pytest.mark.asyncio
    async def test_half_open_probe_with_deterministic_error_recovers(self) -> None:
        """半开探测命中确定性错误（429）后熔断器不楔死，服务恢复即自愈（R3-P0-1
        端到端回归：修复前探测槽位耗尽后永久 411，后端健康也不恢复）

        场景：5xx ×5 打开熔断（按 fetch 计数）→ recovery 窗口后探测请求恰遇
        429（配额限流）→ on_ignored 释放探测槽 → 下一次请求作为新探测放行 →
        服务已恢复 200 → 熔断闭合采集成功。阶段间显式状态断言（OPEN/HALF_OPEN/
        槽位归零）消除时序假设（R3-2 G0 判别锚点修复：原 range(2) 从未打开熔断，
        回退 on_ignored 实现该用例仍全绿——零判别假锚点）。
        """
        from src.infrastructure.external_services.embedding.circuit_breaker import CircuitBreaker, CircuitState

        state = {"phase": "down"}  # down → probe_429 → up

        def handler(request: httpx.Request) -> httpx.Response:
            if state["phase"] == "down":
                return httpx.Response(503, json={})
            if state["phase"] == "probe_429":
                return httpx.Response(429, json={})
            return httpx.Response(
                200, json=[{"page": 1}, [{"indicator": {"id": "NY.GDP.MKTP.CD"}, "value": 1.0, "date": "2024"}]]
            )

        config = WorldBankConfig(api_url=_API_URL, timeout=5.0)
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=0.05, name="test-wb")
        adapter = WorldBankAdapter(
            config=config,
            client=httpx.AsyncClient(base_url=_API_URL, transport=httpx.MockTransport(handler), timeout=5.0),
            circuit_breaker=cb,
            retry_min_wait=0.01,
            retry_max_wait=0.02,
        )
        # 阶段 1：5 次 fetch（各计 1 次 on_failure）→ 熔断真打开（显式状态锚点）
        for _ in range(5):
            with pytest.raises(DataSourceUnavailableError):
                await adapter.fetch(DataSourceQuery(source_name="world-bank", query="GDP"))
        assert cb.state == CircuitState.OPEN
        # 阶段 2：recovery 窗口后探测请求命中 429（确定性错误释放探测槽——修复前此后永久 411）
        await asyncio.sleep(0.06)
        state["phase"] = "probe_429"
        with pytest.raises(DataSourceRateLimitError):
            await adapter.fetch(DataSourceQuery(source_name="world-bank", query="GDP"))
        assert cb.state == CircuitState.HALF_OPEN
        assert cb._half_open_calls == 0  # on_ignored 已释放探测槽（无墙钟依赖的判别锚点）
        # 阶段 3：服务恢复 → 下一次请求可探测且成功（楔死实现在此抛 411「熔断器已断开」）
        state["phase"] = "up"
        result = await adapter.fetch(DataSourceQuery(source_name="world-bank", query="GDP"))
        assert result.source_name == "world-bank"
        assert cb.state == CircuitState.CLOSED
        await adapter.close()


class TestUnsupportedProtocolClassification:
    """URL scheme 缺失的确定性口径（R3-4 K1：修复前被白名单重试且计熔断——与
    InvalidURL 的 101 确定性口径分裂）"""

    def test_whitelist_excludes_unsupported_protocol(self) -> None:
        """白名单分类：UnsupportedProtocol 不可重试（确定性配置错误）"""
        from src.infrastructure.external_services.datasources._http_helpers import is_retryable_http_error

        exc = httpx.UnsupportedProtocol("Request URL is missing an 'http://' or 'https://' protocol.")
        assert is_retryable_http_error(exc) is False
        # 对照：传输类瞬时故障仍可重试（白名单语义未被误伤）
        assert is_retryable_http_error(httpx.ConnectError("conn refused")) is True

    @pytest.mark.asyncio
    async def test_unsupported_protocol_raises_config_error_no_retry(self) -> None:
        """URL scheme 缺失 → ConfigurationError(101) 不重试不计熔断（对齐 InvalidURL；
        修复前：重试 3 次后 411 + on_failure 计熔断）"""
        from src.domain.exceptions import ConfigurationError

        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            raise httpx.UnsupportedProtocol("Request URL is missing an 'http://' or 'https://' protocol.")

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(ConfigurationError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="world-bank", query="GDP"))
        assert exc_info.value.code == "EXCEPTION_101"
        assert calls["n"] == 1  # 确定性错误不重试（修复前 = 3）
        await adapter.close()
