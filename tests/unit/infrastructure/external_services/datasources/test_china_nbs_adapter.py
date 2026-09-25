"""Story 4.1b — ChinaNBSAdapter 单元测试

验证中国国家统计局数据源适配器（CRAWLER，复用 CrawlerClientPort 爬虫插件）：
- 成功采集（提交任务 → 轮询完成 → 结果解析）
- 任务失败 → DataSourceUnavailableError(411)
- 轮询超时 → TimeoutError(302)
- 结果结构非法 → DataSourceResponseError(413)
- CrawlerClientPort 故障 → DataSourceUnavailableError(411)

强制约束：禁止直连 httpx 抓取国家局站点（PoC v2 验证直连 HTTP 403），
必须经 CrawlerClientPort（robots.txt 遵守 + UA 轮换 + 域名限速）。

测试模式：AsyncMock(spec=CrawlerClientPort)（单元测试 Mock 端口，CLAUDE.md §5 允许）。
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from src.domain.exceptions import (
    DataSourceResponseError,
    DataSourceUnavailableError,
    TimeoutError,
)
from src.domain.ports.crawler_client import CrawlerClientPort
from src.domain.ports.data_source import DataSourcePort, DataSourceQuery
from src.infrastructure.config.china_nbs import ChinaNBSConfig
from src.infrastructure.external_services.datasources.china_nbs_adapter import ChinaNBSAdapter


def _make_crawler_mock(status_sequence: list[dict]) -> AsyncMock:
    """构造 CrawlerClientPort mock（get_task_status 按序返回状态）。"""
    mock = AsyncMock(spec=CrawlerClientPort)
    mock.submit_task = AsyncMock(return_value="task-abc-123")
    mock.get_task_status = AsyncMock(side_effect=status_sequence)
    mock.cancel_task = AsyncMock(return_value=True)
    mock.list_supported_formats = AsyncMock(return_value=["html", "pdf"])
    return mock


def _completed_status() -> dict:
    return {
        "status": "completed",
        "result": {"pages": [{"url": "https://www.stats.gov.cn/sj/zxfb/", "text": "2025年国内生产总值..."}]},
    }


def _make_adapter(crawler: AsyncMock) -> ChinaNBSAdapter:
    return ChinaNBSAdapter(
        crawler_client=crawler,
        config=ChinaNBSConfig(poll_interval_sec=0.01, poll_timeout_sec=5.0),
    )


class TestChinaNBSAdapterSuccess:
    @pytest.mark.asyncio
    async def test_fetch_success(self) -> None:
        crawler = _make_crawler_mock([{"status": "running"}, _completed_status()])
        adapter = _make_adapter(crawler)
        result = await adapter.fetch(DataSourceQuery(source_name="china-nbs", query="sj/zxfb"))
        assert result.source_name == "china-nbs"
        payload = json.loads(result.payload)
        assert payload["pages"][0]["text"].startswith("2025年")
        # 验证经 crawler 插件提交（域名限定 stats.gov.cn）
        submit_kwargs = crawler.submit_task.call_args
        assert "stats.gov.cn" in str(submit_kwargs)

    @pytest.mark.asyncio
    async def test_implements_port(self) -> None:
        assert isinstance(_make_adapter(crawler := _make_crawler_mock([_completed_status()])), DataSourcePort)
        assert crawler is not None

    def test_get_metadata(self) -> None:
        ref = _make_adapter(_make_crawler_mock([])).get_metadata()
        assert ref.name == "china-nbs"

    @pytest.mark.asyncio
    async def test_health_check_via_list_supported_formats(self) -> None:
        """探活使用 list_supported_formats() 轻量调用（不消耗任务配额）。"""
        crawler = _make_crawler_mock([])
        adapter = _make_adapter(crawler)
        assert await adapter.health_check() is True
        crawler.list_supported_formats.assert_called_once()
        crawler.submit_task.assert_not_called()


class TestChinaNBSAdapterFailures:
    @pytest.mark.asyncio
    async def test_task_failed_raises_unavailable(self) -> None:
        crawler = _make_crawler_mock([{"status": "failed", "error": "crawl error"}])
        adapter = _make_adapter(crawler)
        with pytest.raises(DataSourceUnavailableError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="china-nbs", query="sj/zxfb"))
        assert exc_info.value.code == "EXCEPTION_411"

    @pytest.mark.asyncio
    async def test_poll_timeout_raises_timeout_error(self) -> None:
        crawler = _make_crawler_mock([{"status": "running"}] * 100)
        adapter = ChinaNBSAdapter(
            crawler_client=crawler,
            config=ChinaNBSConfig(poll_interval_sec=0.01, poll_timeout_sec=0.05),
        )
        with pytest.raises(TimeoutError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="china-nbs", query="sj/zxfb"))
        assert exc_info.value.code == "EXCEPTION_302"
        # 超时后应取消任务（资源回收）
        crawler.cancel_task.assert_called_once_with("task-abc-123")

    @pytest.mark.asyncio
    async def test_malformed_result_raises_response_error(self) -> None:
        crawler = _make_crawler_mock([{"status": "completed", "result": None}])
        adapter = _make_adapter(crawler)
        with pytest.raises(DataSourceResponseError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="china-nbs", query="sj/zxfb"))
        assert exc_info.value.code == "EXCEPTION_413"

    @pytest.mark.asyncio
    async def test_crawler_client_failure_raises_unavailable(self) -> None:
        crawler = AsyncMock(spec=CrawlerClientPort)
        crawler.submit_task = AsyncMock(side_effect=ConnectionError("crawler service down"))
        adapter = _make_adapter(crawler)
        with pytest.raises(DataSourceUnavailableError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="china-nbs", query="sj/zxfb"))
        assert exc_info.value.code == "EXCEPTION_411"

    @pytest.mark.asyncio
    async def test_health_check_failure_returns_false(self) -> None:
        crawler = AsyncMock(spec=CrawlerClientPort)
        crawler.list_supported_formats = AsyncMock(side_effect=ConnectionError("down"))
        adapter = _make_adapter(crawler)
        assert await adapter.health_check() is False
