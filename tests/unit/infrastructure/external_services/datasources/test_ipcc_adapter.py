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
    ConfigurationError,
    DataSourceRateLimitError,
    DataSourceResponseError,
    DataSourceUnavailableError,
    TimeoutError,
)
from src.domain.ports.data_source import DataSourcePort, DataSourceQuery
from src.infrastructure.config.ipcc import IPCCConfig
from src.infrastructure.external_services.datasources.ipcc_adapter import IPCCAdapter

_CSV_URL = "https://www.ipcc.ch/data"


def _make_adapter(handler: httpx.MockTransport | None = None, max_rows: int = 1000, max_bytes: int = 1_048_576) -> IPCCAdapter:
    config = IPCCConfig(csv_base_url=_CSV_URL, timeout=5.0, max_bytes=max_bytes)
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


class TestIPCCResponseBounds:
    """R2-2-B2/G7：流式大小上限 + Content-Type 校验（无界读取 OOM 面与 HTML 静默污染修复）。"""

    @pytest.mark.asyncio
    async def test_response_exceeding_max_bytes_raises_413_no_retry(self) -> None:
        """响应超过 max_bytes → DataSourceResponseError(413)，确定性错误不重试。"""
        calls = {"n": 0}
        big_csv = "col\n" + "x" * 4096

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200, text=big_csv)

        adapter = _make_adapter(httpx.MockTransport(handler), max_bytes=1024)
        with pytest.raises(DataSourceResponseError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="ipcc", query="big"))
        assert exc_info.value.code == "EXCEPTION_413"
        assert calls["n"] == 1  # 不重试
        await adapter.close()

    @pytest.mark.asyncio
    async def test_response_exactly_max_bytes_passes(self) -> None:
        """恰好等于 max_bytes 的响应正常通过（边界含等号）。"""
        # header "c\n" = 2 字节 + body 1022 字节 = 恰好 1024
        body = "c\n" + "x" * 1022
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(200, text=body)), max_bytes=1024)
        result = await adapter.fetch(DataSourceQuery(source_name="ipcc", query="edge"))
        assert result.source_name == "ipcc"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_html_error_page_rejected_as_413(self) -> None:
        """HTTP 200 + text/html（CDN/反爬错误页）→ 413 拒绝（防静默解析为垃圾数据）。"""
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200, text="<html><body>Access Denied</body></html>", headers={"content-type": "text/html"})

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(DataSourceResponseError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="ipcc", query="ar6"))
        assert exc_info.value.code == "EXCEPTION_413"
        assert calls["n"] == 1
        await adapter.close()


class TestIPCCConfigMaxBytes:
    """IPCC_MAX_BYTES 环境变量解析与范围校验。"""

    def test_from_env_invalid_max_bytes_raises_101(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("IPCC_MAX_BYTES", "abc")
        with pytest.raises(ConfigurationError) as exc_info:
            IPCCConfig.from_env()
        assert exc_info.value.code == "EXCEPTION_101"

    def test_from_env_non_positive_max_bytes_raises_101(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("IPCC_MAX_BYTES", "-1")
        with pytest.raises(ConfigurationError) as exc_info:
            IPCCConfig.from_env()
        assert exc_info.value.code == "EXCEPTION_101"

    def test_from_env_valid_max_bytes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("IPCC_MAX_BYTES", "2097152")
        config = IPCCConfig.from_env()
        assert config.max_bytes == 2_097_152


class TestIPCCPathEncoding:
    """R2-2-B6/H4 按段编码（保留相对路径键契约）。"""

    @pytest.mark.asyncio
    async def test_nested_path_key_preserved(self) -> None:
        """嵌套相对路径键（a/b）的 / 分隔保留、各段独立编码。"""
        captured: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(str(request.url))
            return httpx.Response(200, text="col\n1\n")

        adapter = _make_adapter(httpx.MockTransport(handler))
        await adapter.fetch(DataSourceQuery(source_name="ipcc", query="ar6 wg1/spm ch1"))
        assert "/ar6%20wg1/spm%20ch1.csv" in captured[0]  # 段内空格编码、段间 / 保留
        await adapter.close()

    @pytest.mark.asyncio
    async def test_dotdot_key_rejected_413(self) -> None:
        """穿越序列键显式拒绝 → 413。"""
        adapter = _make_adapter()
        with pytest.raises(DataSourceResponseError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="ipcc", query="../secrets"))
        assert exc_info.value.code == "EXCEPTION_413"
        await adapter.close()


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


class TestHealthCheckCircuitBreakerIntegration:
    """health_check 熔断集成（R3-3 H3v2：原 `< 500` 使 403/404 恒报健康且绕过熔断器）"""

    @pytest.mark.asyncio
    async def test_200_healthy(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(200)))
        assert await adapter.health_check() is True

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [403, 404, 503])
    async def test_error_statuses_unhealthy(self, status: int) -> None:
        """403/404（原恒报健康）与 503 均判不健康"""
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(status)))
        assert await adapter.health_check() is False

    @pytest.mark.asyncio
    async def test_breaker_open_short_circuits_without_request(self) -> None:
        """熔断打开 → False 且不发请求（before_call 快速失败）"""
        from src.infrastructure.external_services.embedding.circuit_breaker import CircuitBreaker

        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200)

        adapter = IPCCAdapter(
            config=IPCCConfig(),
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=5.0),
            circuit_breaker=CircuitBreaker(failure_threshold=2, recovery_timeout=60.0, name="test-ipcc-hc"),
        )
        adapter._circuit_breaker.on_failure()
        adapter._circuit_breaker.on_failure()  # 手动打开熔断（不跑慢速真实失败）
        assert await adapter.health_check() is False
        assert calls["n"] == 0  # 未发请求
        await adapter.close()

    @pytest.mark.asyncio
    async def test_5xx_records_failure_to_breaker(self) -> None:
        """5xx 探活计熔断（H3v2-②：服务雪崩时探活须能打开熔断，对齐 fetch 契约）"""
        from src.infrastructure.external_services.embedding.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60.0, name="test-ipcc-5xx")
        adapter = IPCCAdapter(
            config=IPCCConfig(),
            client=httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(503)), timeout=5.0),
            circuit_breaker=cb,
        )
        assert await adapter.health_check() is False
        assert await adapter.health_check() is False
        assert cb.state == CircuitState.OPEN  # 两次 5xx 探活打开熔断
        await adapter.close()
