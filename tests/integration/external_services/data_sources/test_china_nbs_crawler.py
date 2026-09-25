"""Story 4.1b — 中国国家统计局 crawler 链路集成测试

使用本地 aiohttp 真实 HTTP 服务器模拟 Crawler Service REST API，
验证 ChinaNBSAdapter 经真实 HttpCrawlerClient 的完整链路（不 mock 客户端本身）：
- 真实任务提交（POST /api/v1/tasks，断言域名白名单 stats.gov.cn）
- 真实状态轮询（GET /api/v1/tasks/{id} 序列：running → completed）
- 探活（GET /api/v1/formats 轻量调用，不消耗任务配额）
- 失败路径：任务 failed → 411 / 轮询超时自动取消（DELETE）→ 302

Mock 原因：Crawler Service 是有状态微服务（Scrapy 引擎），集成测试不要求常驻；
使用本地 HTTP 服务器保持可重复性并验证完整 HTTP 交互链路
（范本：tests/integration/test_integration_llm_client.py + test_adapters_http_chain.py）。
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any, cast

import pytest
from aiohttp import web

from src.domain.exceptions import DataSourceUnavailableError, TimeoutError
from src.domain.ports.data_source import DataSourcePort, DataSourceQuery
from src.infrastructure.config.china_nbs import ChinaNBSConfig
from src.infrastructure.crawler.http_crawler_client import HttpCrawlerClient
from src.infrastructure.external_services.datasources.china_nbs_adapter import ChinaNBSAdapter

pytestmark = [pytest.mark.integration, pytest.mark.xdist_group("data-source-cache")]

# ===================================================================
# 模拟 Crawler Service HTTP 服务器
# ===================================================================


class MockCrawlerHandler:
    """模拟 Crawler Service REST API 的处理器（任务状态序列可编程）。"""

    def __init__(self) -> None:
        self._status_sequence: list[dict[str, Any]] = [{"status": "completed", "result": {"pages": []}}]
        self._call_index = 0
        self.submit_payloads: list[dict[str, Any]] = []
        self.cancelled_task_ids: list[str] = []

    def set_status_sequence(self, sequence: list[dict[str, Any]]) -> None:
        """设置 get_task_status 按序返回的状态（用尽后保持最后一项）"""
        self._status_sequence = sequence
        self._call_index = 0

    async def handle_submit(self, request: web.Request) -> web.Response:
        """POST /api/v1/tasks → {"task_id": ...}"""
        payload = await request.json()
        self.submit_payloads.append(payload)
        return web.json_response({"task_id": "task-mock-001"})

    async def handle_status(self, request: web.Request) -> web.Response:
        """GET /api/v1/tasks/{task_id} → 状态字典"""
        idx = min(self._call_index, len(self._status_sequence) - 1)
        self._call_index += 1
        return web.json_response(self._status_sequence[idx])

    async def handle_cancel(self, request: web.Request) -> web.Response:
        """DELETE /api/v1/tasks/{task_id} → 200"""
        self.cancelled_task_ids.append(request.match_info["task_id"])
        return web.Response(status=200)

    async def handle_formats(self, request: web.Request) -> web.Response:
        """GET /api/v1/formats → {"formats": [...]}"""
        return web.json_response({"formats": ["html", "pdf", "json"]})


@pytest.fixture
async def mock_crawler_server() -> AsyncGenerator[tuple[MockCrawlerHandler, str], None]:
    """启动本地 HTTP 服务器模拟 Crawler Service，返回 (handler, base_url)"""
    handler = MockCrawlerHandler()
    app = web.Application()
    app.router.add_post("/api/v1/tasks", handler.handle_submit)
    app.router.add_get("/api/v1/tasks/{task_id}", handler.handle_status)
    app.router.add_delete("/api/v1/tasks/{task_id}", handler.handle_cancel)
    app.router.add_get("/api/v1/formats", handler.handle_formats)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = cast(Any, site._server).sockets[0].getsockname()[1]

    yield handler, f"http://127.0.0.1:{port}"

    await runner.cleanup()


def _make_adapter(base_url: str, **config_overrides: Any) -> tuple[ChinaNBSAdapter, HttpCrawlerClient]:
    """构造真实 HttpCrawlerClient + ChinaNBSAdapter（连接本地模拟服务）。"""
    client = HttpCrawlerClient(base_url=base_url, timeout=5.0)
    base: dict[str, Any] = {"poll_interval_sec": 0.01, "poll_timeout_sec": 2.0}
    base.update(config_overrides)
    return ChinaNBSAdapter(crawler_client=client, config=ChinaNBSConfig(**base)), client


# ===================================================================
# 完整 HTTP 链路
# ===================================================================


class TestChinaNBSCrawlerChain:
    @pytest.mark.asyncio
    async def test_health_check_via_formats_endpoint(self, mock_crawler_server: tuple[MockCrawlerHandler, str]) -> None:
        """探活：list_supported_formats 经真实 HTTP GET /api/v1/formats（不消耗任务配额）。"""
        _handler, base_url = mock_crawler_server
        adapter, client = _make_adapter(base_url)
        assert await adapter.health_check() is True
        await client.close()

    @pytest.mark.asyncio
    async def test_implements_port(self, mock_crawler_server: tuple[MockCrawlerHandler, str]) -> None:
        _handler, base_url = mock_crawler_server
        adapter, client = _make_adapter(base_url)
        assert isinstance(adapter, DataSourcePort)
        await client.close()

    @pytest.mark.asyncio
    async def test_submit_poll_fetch_full_chain(self, mock_crawler_server: tuple[MockCrawlerHandler, str]) -> None:
        """完整链路：提交（域名白名单断言）→ 轮询 running→completed → 结果解析。"""
        handler, base_url = mock_crawler_server
        handler.set_status_sequence(
            [
                {"status": "running"},
                {"status": "completed", "result": {"pages": [{"url": "https://www.stats.gov.cn/sj/zxfb", "text": "统计数据"}]}},
            ]
        )
        adapter, client = _make_adapter(base_url)
        result = await adapter.fetch(DataSourceQuery(source_name="china-nbs", query="sj/zxfb"))

        # 提交载荷：域名白名单 + seed_urls（禁止直连的合规路径）
        assert len(handler.submit_payloads) == 1
        payload = handler.submit_payloads[0]
        assert payload["domains"] == ["www.stats.gov.cn"]
        assert payload["seed_urls"] == ["https://www.stats.gov.cn/sj/zxfb"]
        # 结果解析
        body = json.loads(result.payload)
        assert body["pages"][0]["text"] == "统计数据"
        assert result.source_name == "china-nbs"
        assert 0.0 < result.confidence <= 1.0
        await client.close()

    @pytest.mark.asyncio
    async def test_task_failed_maps_411(self, mock_crawler_server: tuple[MockCrawlerHandler, str]) -> None:
        handler, base_url = mock_crawler_server
        handler.set_status_sequence([{"status": "failed", "error": "crawl error"}])
        adapter, client = _make_adapter(base_url)
        with pytest.raises(DataSourceUnavailableError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="china-nbs", query="sj/zxfb"))
        assert exc_info.value.code == "EXCEPTION_411"
        await client.close()

    @pytest.mark.asyncio
    async def test_poll_timeout_cancels_task_maps_302(self, mock_crawler_server: tuple[MockCrawlerHandler, str]) -> None:
        """轮询超时 → 自动取消任务（DELETE 资源回收）→ TimeoutError(302)。"""
        handler, base_url = mock_crawler_server
        handler.set_status_sequence([{"status": "running"}])
        adapter, client = _make_adapter(base_url, poll_timeout_sec=0.05)
        with pytest.raises(TimeoutError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="china-nbs", query="sj/zxfb"))
        assert exc_info.value.code == "EXCEPTION_302"
        assert handler.cancelled_task_ids == ["task-mock-001"]
        await client.close()
