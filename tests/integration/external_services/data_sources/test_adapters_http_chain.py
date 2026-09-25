"""Story 4.1b — 数据源适配器 HTTP 链路集成测试

使用本地 aiohttp 真实 HTTP 服务器模拟外部数据源 API（WorldBank/Eurostat），
验证适配器完整 HTTP 链路（不 mock 客户端本身）：
- 真实 httpx 请求构建（路径/查询参数）与 JSON 响应解析
- tenacity 重试与熔断器协同（真实 HTTP 状态码触发：503 × N → 200）
- 熔断器断开后快速失败（零 HTTP 调用）

Mock 原因：外部 SaaS/统计 API 有成本/限流/不可控，无法在集成测试中调用真实端点；
使用本地 HTTP 服务器保持可重复性并验证完整 HTTP 交互链路
（范本：tests/integration/test_integration_llm_client.py）。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any, cast

import pytest
from aiohttp import web

from src.domain.exceptions import DataSourceUnavailableError
from src.domain.ports.data_source import DataSourceQuery
from src.infrastructure.config.eurostat import EurostatConfig
from src.infrastructure.config.worldbank import WorldBankConfig
from src.infrastructure.external_services.datasources.eurostat_adapter import EurostatAdapter
from src.infrastructure.external_services.datasources.worldbank_adapter import WorldBankAdapter

pytestmark = [pytest.mark.integration, pytest.mark.xdist_group("data-source-cache")]

# ===================================================================
# 模拟统计数据源 HTTP 服务器
# ===================================================================


class MockStatisticsHandler:
    """模拟 WorldBank/Eurostat API 的 HTTP 请求处理器（序列响应可编程）。"""

    def __init__(self) -> None:
        self._sequence: list[tuple[int, Any]] | None = None
        self._call_index = 0
        self.requests: list[str] = []

    def set_sequence(self, sequence: list[tuple[int, Any]]) -> None:
        """设置按序返回的 (status, json_body) 序列（用尽后保持最后一项）"""
        self._sequence = sequence
        self._call_index = 0

    async def handle_worldbank(self, request: web.Request) -> web.Response:
        """处理 GET /country/{country}/indicator/{indicator}"""
        self.requests.append(str(request.rel_url))
        status, body = self._next_response(
            default=[{"page": 1}, [{"indicator": {"id": "NY.GDP.MKTP.CD"}, "value": 1.7e13, "date": "2024"}]]
        )
        return web.json_response(body, status=status)

    async def handle_eurostat(self, request: web.Request) -> web.Response:
        """处理 GET /statistics/1.0/data/{dataset}"""
        self.requests.append(str(request.rel_url))
        status, body = self._next_response(default={"value": {"0": 99.5}, "dimension": {}, "updated": "2025-09-01"})
        return web.json_response(body, status=status)

    def _next_response(self, default: Any) -> tuple[int, Any]:
        if self._sequence is not None:
            idx = min(self._call_index, len(self._sequence) - 1)
            self._call_index += 1
            return self._sequence[idx]
        return 200, default


@pytest.fixture
async def mock_stats_server() -> AsyncGenerator[tuple[MockStatisticsHandler, str], None]:
    """启动本地 HTTP 服务器模拟统计数据源 API，返回 (handler, base_url)"""
    handler = MockStatisticsHandler()
    app = web.Application()
    app.router.add_get("/country/{country}/indicator/{indicator}", handler.handle_worldbank)
    app.router.add_get("/statistics/1.0/data/{dataset}", handler.handle_eurostat)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = cast(Any, site._server).sockets[0].getsockname()[1]

    yield handler, f"http://127.0.0.1:{port}"

    await runner.cleanup()


# ===================================================================
# WorldBank 完整 HTTP 链路
# ===================================================================


class TestWorldBankHttpChain:
    @pytest.mark.asyncio
    async def test_full_chain_success(self, mock_stats_server: tuple[MockStatisticsHandler, str]) -> None:
        """真实 HTTP 链路：请求构建（路径+查询参数）→ 响应解析 → 领域结果。"""
        handler, base_url = mock_stats_server
        adapter = WorldBankAdapter(
            config=WorldBankConfig(api_url=base_url, timeout=5.0),
            retry_min_wait=0.01,
            retry_max_wait=0.02,
        )
        result = await adapter.fetch(
            DataSourceQuery(source_name="world-bank", query="NY.GDP.MKTP.CD", parameters=(("country", "CN"),))
        )
        assert result.source_name == "world-bank"
        assert "country/CN/indicator/NY.GDP.MKTP.CD" in handler.requests[0]
        assert "format=json" in handler.requests[0]
        await adapter.close()

    @pytest.mark.asyncio
    async def test_retry_then_success_recovers(self, mock_stats_server: tuple[MockStatisticsHandler, str]) -> None:
        """503 × 2 → 200：tenacity 真实重试恢复，熔断器记录成功。"""
        handler, base_url = mock_stats_server
        handler.set_sequence(
            [
                (503, {"error": "down"}),
                (503, {"error": "down"}),
                (200, [{"page": 1}, [{"value": 1.0, "date": "2024"}]]),
            ]
        )
        adapter = WorldBankAdapter(
            config=WorldBankConfig(api_url=base_url, timeout=5.0),
            retry_min_wait=0.01,
            retry_max_wait=0.02,
        )
        result = await adapter.fetch(DataSourceQuery(source_name="world-bank", query="q"))
        assert result.source_name == "world-bank"
        assert len(handler.requests) == 3  # 2 次失败 + 1 次成功
        await adapter.close()

    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold_real_http(self, mock_stats_server: tuple[MockStatisticsHandler, str]) -> None:
        """持续 503：重试耗尽 → 熔断器断开 → 后续调用零 HTTP 快速失败。"""
        handler, base_url = mock_stats_server
        handler.set_sequence([(503, {"error": "down"})])
        adapter = WorldBankAdapter(
            config=WorldBankConfig(api_url=base_url, timeout=5.0),
            retry_min_wait=0.01,
            retry_max_wait=0.02,
        )
        # 5 次 fetch 耗尽熔断阈值（每次 fetch = 3 次 HTTP 重试 + 1 次熔断计数）
        for _ in range(5):
            with pytest.raises(DataSourceUnavailableError):
                await adapter.fetch(DataSourceQuery(source_name="world-bank", query="q"))
        requests_before = len(handler.requests)
        # 熔断器已断开：快速失败，零 HTTP 调用
        with pytest.raises(DataSourceUnavailableError):
            await adapter.fetch(DataSourceQuery(source_name="world-bank", query="q"))
        assert len(handler.requests) == requests_before
        await adapter.close()


# ===================================================================
# Eurostat 完整 HTTP 链路
# ===================================================================


class TestEurostatHttpChain:
    @pytest.mark.asyncio
    async def test_full_chain_success(self, mock_stats_server: tuple[MockStatisticsHandler, str]) -> None:
        handler, base_url = mock_stats_server
        adapter = EurostatAdapter(
            config=EurostatConfig(api_url=base_url, timeout=5.0),
            retry_min_wait=0.01,
            retry_max_wait=0.02,
        )
        result = await adapter.fetch(DataSourceQuery(source_name="eurostat", query="nama_10_gdp", parameters=(("geo", "DE"),)))
        assert result.source_name == "eurostat"
        assert result.source_timestamp.year == 2025
        assert "statistics/1.0/data/nama_10_gdp" in handler.requests[0]
        assert "geo=DE" in handler.requests[0]
        await adapter.close()

    @pytest.mark.asyncio
    async def test_retry_exhaustion_maps_411(self, mock_stats_server: tuple[MockStatisticsHandler, str]) -> None:
        handler, base_url = mock_stats_server
        handler.set_sequence([(500, {"error": "x"})])
        adapter = EurostatAdapter(
            config=EurostatConfig(api_url=base_url, timeout=5.0),
            retry_min_wait=0.01,
            retry_max_wait=0.02,
        )
        with pytest.raises(DataSourceUnavailableError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="eurostat", query="q"))
        assert exc_info.value.code == "EXCEPTION_411"
        assert len(handler.requests) == 3
        await adapter.close()
