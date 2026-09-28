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
from collections.abc import Sequence
from typing import Any
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


def _make_crawler_mock(status_sequence: Sequence[dict[str, Any] | Exception]) -> AsyncMock:
    """构造 CrawlerClientPort mock（get_task_status 按序返回状态或抛异常）。"""
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


class TestChinaNBSAdapterPollingResilience:
    """R2-2-B3/H1 轮询健壮性：已知中间态/取消终态/未知状态容忍/抖动容忍。"""

    @pytest.mark.asyncio
    async def test_pending_long_resident_not_misjudged(self) -> None:
        """pending 排队态长驻（crawler 并发常态）不误判失败。"""
        crawler = _make_crawler_mock([{"status": "pending"}] * 10 + [_completed_status()])
        adapter = _make_adapter(crawler)
        result = await adapter.fetch(DataSourceQuery(source_name="china-nbs", query="sj/zxfb"))
        assert result.source_name == "china-nbs"

    @pytest.mark.asyncio
    async def test_cancelled_raises_unavailable_411(self) -> None:
        """cancelled 是对端合法终态（运维主动取消）→ 411 而非 413。"""
        crawler = _make_crawler_mock([{"status": "cancelled"}])
        adapter = _make_adapter(crawler)
        with pytest.raises(DataSourceUnavailableError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="china-nbs", query="sj/zxfb"))
        assert exc_info.value.code == "EXCEPTION_411"

    @pytest.mark.asyncio
    async def test_consecutive_unknown_status_raises_413(self) -> None:
        """连续 3 次未知状态 → 413（对端契约违反，不再空转满超时）。"""
        crawler = _make_crawler_mock([{"status": "mystery"}] * 10)
        adapter = _make_adapter(crawler)
        with pytest.raises(DataSourceResponseError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="china-nbs", query="sj/zxfb"))
        assert exc_info.value.code == "EXCEPTION_413"
        assert crawler.get_task_status.call_count == 3  # 快速失败，未空转

    @pytest.mark.asyncio
    async def test_unknown_count_reset_by_known_pending(self) -> None:
        """未知计数遇已知中间态清零：unknown×2 → running → unknown×2 → completed 成功。"""
        crawler = _make_crawler_mock(
            [{"status": "mystery"}, {"status": "mystery"}, {"status": "running"}]
            + [{"status": "mystery"}, {"status": "mystery"}, _completed_status()]
        )
        adapter = _make_adapter(crawler)
        result = await adapter.fetch(DataSourceQuery(source_name="china-nbs", query="sj/zxfb"))
        assert result.source_name == "china-nbs"

    @pytest.mark.asyncio
    async def test_status_query_transient_errors_tolerated(self) -> None:
        """状态查询连续 2 次抖动后成功 → 正常完成（成功清零错误计数）。"""
        crawler = _make_crawler_mock(
            [ConnectionError("blip"), ConnectionError("blip"), {"status": "running"}, _completed_status()]
        )
        adapter = _make_adapter(crawler)
        result = await adapter.fetch(DataSourceQuery(source_name="china-nbs", query="sj/zxfb"))
        assert result.source_name == "china-nbs"

    @pytest.mark.asyncio
    async def test_status_query_errors_exhausted_raises_411(self) -> None:
        """状态查询连续 3 次抖动 → 411（容忍耗尽）。"""
        crawler = _make_crawler_mock([ConnectionError("down")] * 5)
        adapter = _make_adapter(crawler)
        with pytest.raises(DataSourceUnavailableError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="china-nbs", query="sj/zxfb"))
        assert exc_info.value.code == "EXCEPTION_411"
        assert crawler.get_task_status.call_count == 3


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
        assert isinstance(_make_adapter(_make_crawler_mock([_completed_status()])), DataSourcePort)

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


class TestSeedUrlPathEncoding:
    """seed_url 逐段编码（R3-3 H2：8 适配器中唯一未走 quote_path_segment 的
    LLM 不可信输入注入缺口——".." 穿越拒绝 + 特殊字符段编码）"""

    @pytest.mark.asyncio
    async def test_dotdot_path_rejected_413(self) -> None:
        """路径含 ".." 段 → 413（防站内路径穿越）"""
        crawler = _make_crawler_mock([_completed_status()])
        adapter = _make_adapter(crawler)
        with pytest.raises(DataSourceResponseError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="china-nbs", query="../admin"))
        assert exc_info.value.code == "EXCEPTION_413"

    @pytest.mark.asyncio
    async def test_legitimate_path_unchanged(self) -> None:
        """合法路径（sj/zxfb，unreserved 字符）恒等通过（回归保护）"""
        crawler = _make_crawler_mock([_completed_status()])
        adapter = _make_adapter(crawler)
        await adapter.fetch(DataSourceQuery(source_name="china-nbs", query="sj/zxfb"))
        submit_kwargs = crawler.submit_task.await_args.kwargs
        assert submit_kwargs["seed_urls"] == ["https://www.stats.gov.cn/sj/zxfb"]

    @pytest.mark.asyncio
    async def test_special_characters_encoded_per_segment(self) -> None:
        """含空格/特殊字符的段被 percent 编码（段间 / 保留）"""
        crawler = _make_crawler_mock([_completed_status()])
        adapter = _make_adapter(crawler)
        await adapter.fetch(DataSourceQuery(source_name="china-nbs", query="sj/a b?c"))
        submit_kwargs = crawler.submit_task.await_args.kwargs
        seed = submit_kwargs["seed_urls"][0]
        assert seed.endswith("/sj/a%20b%3Fc")
        assert " " not in seed.rsplit("/sj/", 1)[-1]
