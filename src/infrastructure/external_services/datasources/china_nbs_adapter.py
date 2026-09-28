"""基础设施层中国国家统计局数据源适配器（Story 4.1b）

中国国家统计局数据采集（CRAWLER 类型）：
- **强制约束**：禁止直连 httpx 抓取国家局站点（PoC v2 验证直连 HTTP 403 反爬拒绝），
  必须经 CrawlerClientPort 复用 crawler 插件（robots.txt 遵守 + UA 轮换 + 域名限速 + Playwright 反爬）
- 流程：submit_task（seed_urls + 域名白名单）→ 轮询 get_task_status → 解析结果
- 熔断放宽（10 次/120s）：爬虫任务失败率天然高于 REST API

实现 DataSourcePort。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

from src.domain.exceptions import (
    DataSourceResponseError,
    DataSourceUnavailableError,
    TimeoutError,
)
from src.domain.ports.crawler_client import CrawlerClientPort
from src.domain.ports.data_source import DataSourceQuery
from src.domain.value_objects.data_source import (
    DataFreshness,
    DataSourceApiType,
    DataSourceRef,
    DataSourceResult,
)
from src.infrastructure.config.china_nbs import ChinaNBSConfig

logger = logging.getLogger(__name__)

_TERMINAL_SUCCESS = "completed"
_TERMINAL_FAILED = "failed"
_TERMINAL_CANCELLED = "cancelled"
# 已知中间态（出处：plugins/crawler/core/value_objects.py CrawlStatus 枚举
# {PENDING, RUNNING, COMPLETED, FAILED, CANCELLED}——pending 排队态在 crawler
# 并发下是常态，缺失会导致确定性误判回归）
_KNOWN_PENDING = frozenset({"pending", "running"})
# 连续未知状态/连续查询异常容忍次数（吸收 crawler 侧短暂中间态与网络抖动）
_TOLERANCE = 3


class ChinaNBSAdapter:
    """中国国家统计局数据源适配器（CRAWLER，经 CrawlerClientPort）

    爬虫熔断放宽：失败率天然高于 REST API，由调用方（Resolver）超时与缓存兜底；
    本适配器不内置 CircuitBreaker（任务级故障语义由 crawler 服务侧管理）。
    """

    def __init__(
        self,
        crawler_client: CrawlerClientPort,
        config: ChinaNBSConfig | None = None,
    ) -> None:
        """初始化适配器

        Args:
            crawler_client: CrawlerClientPort（crawler 插件 HTTP 客户端）
            config: ChinaNBSConfig 配置（默认 from 默认值）
        """
        self._crawler = crawler_client
        self._config = config or ChinaNBSConfig()

    def get_metadata(self) -> DataSourceRef:
        """返回数据源引用元数据"""
        return DataSourceRef(
            name="china-nbs",
            url=self._config.base_url,
            ttl_seconds=self._config.ttl_seconds,
            api_type=DataSourceApiType.CRAWLER,
        )

    async def fetch(self, query: DataSourceQuery) -> DataSourceResult:
        """经 crawler 插件采集国家局数据

        Args:
            query: DataSourceQuery（query=站点相对路径，如 "sj/zxfb"）

        Returns:
            DataSourceResult（payload 为采集页面 JSON 字符串）

        Raises:
            DataSourceUnavailableError: crawler 服务故障/任务失败（EXCEPTION_411）
            TimeoutError: 轮询超时（EXCEPTION_302，超时后自动取消任务）
            DataSourceResponseError: 结果结构非法（EXCEPTION_413）
        """
        seed_url = f"{self._config.base_url}/{query.query}"
        try:
            task_id = await self._crawler.submit_task(
                domains=[self._config.domain],
                seed_urls=[seed_url],
                max_depth=1,
                max_files=10,
            )
        except Exception as e:
            raise DataSourceUnavailableError(
                message="中国国家统计局采集任务提交失败（crawler 服务不可达）",
                context={"source_name": "china-nbs"},
                cause=e,
            ) from e

        status = await self._poll_until_terminal(task_id)
        payload_obj = self._extract_payload(status)
        now = datetime.now(UTC)
        return DataSourceResult(
            source_name="china-nbs",
            payload=json.dumps(payload_obj, ensure_ascii=False),
            source_timestamp=now,
            fetched_at=now,
            freshness=DataFreshness(source_timestamp=now, ttl_seconds=self._config.ttl_seconds),
            confidence=0.9,  # 官方统计源
        )

    async def health_check(self) -> bool:
        """探活（list_supported_formats 轻量调用，不消耗任务配额）"""
        try:
            await self._crawler.list_supported_formats()
            return True
        except Exception as e:
            logger.warning("ChinaNBS 探活失败（crawler 服务）: %s", type(e).__name__)
            return False

    async def _poll_until_terminal(self, task_id: str) -> dict[str, Any]:
        """轮询任务状态直至终态（completed/failed/cancelled）或超时

        R2-2-B3/H1 健壮性：未知状态不再空转至超时（连续 3 次 → 413 对端契约违反）；
        状态查询瞬时抖动连续容忍 3 次（成功即清零，耗尽 → 411）；poll_timeout 为
        硬上界（异常容忍分支同样检查 deadline）。

        Raises:
            TimeoutError: 超过 poll_timeout_sec（超时后自动取消任务回收资源）
            DataSourceUnavailableError: 任务失败/被取消或状态查询故障（411）
            DataSourceResponseError: 连续未知状态（413，对端契约违反）
        """
        deadline = time.monotonic() + self._config.poll_timeout_sec
        consecutive_unknown = 0
        consecutive_errors = 0
        while True:
            try:
                status = await self._crawler.get_task_status(task_id)
                consecutive_errors = 0
            except Exception as e:
                consecutive_errors += 1
                if consecutive_errors >= _TOLERANCE:
                    raise DataSourceUnavailableError(
                        message="中国国家统计局采集任务状态查询失败（连续抖动耗尽容忍）",
                        context={"source_name": "china-nbs", "task_id": task_id},
                        cause=e,
                    ) from e
                logger.warning("ChinaNBS 状态查询抖动(%d/%d)，下轮重试: %s", consecutive_errors, _TOLERANCE, type(e).__name__)
            else:
                state = status.get("status")
                if state == _TERMINAL_SUCCESS:
                    return status
                if state in (_TERMINAL_FAILED, _TERMINAL_CANCELLED):
                    reason = "被取消" if state == _TERMINAL_CANCELLED else "失败"
                    raise DataSourceUnavailableError(
                        message=f"中国国家统计局采集任务{reason}",
                        context={"source_name": "china-nbs", "task_id": task_id, "error": str(status.get("error", ""))[:200]},
                    )
                if state in _KNOWN_PENDING:
                    consecutive_unknown = 0
                else:
                    consecutive_unknown += 1
                    if consecutive_unknown >= _TOLERANCE:
                        raise DataSourceResponseError(
                            message=f"中国国家统计局采集任务状态非法（连续 {consecutive_unknown} 次未知状态 {state!r}）",
                            context={"source_name": "china-nbs", "task_id": task_id, "status": state},
                        )
            if time.monotonic() > deadline:
                # 资源回收：超时后取消任务
                try:
                    await self._crawler.cancel_task(task_id)
                except Exception:
                    logger.warning("取消超时任务失败（可忽略）: task_id=%s", task_id)
                raise TimeoutError(
                    message=f"中国国家统计局采集任务轮询超时（{self._config.poll_timeout_sec}s）",
                    context={"source_name": "china-nbs", "task_id": task_id},
                )
            await asyncio.sleep(self._config.poll_interval_sec)

    def _extract_payload(self, status: dict[str, Any]) -> dict[str, Any]:
        """提取采集结果（结构非法抛 DataSourceResponseError）"""
        result = status.get("result")
        if not isinstance(result, dict) or "pages" not in result:
            raise DataSourceResponseError(
                message="中国国家统计局采集结果结构非法（缺少 result.pages）",
                context={"source_name": "china-nbs", "actual_type": type(result).__name__},
            )
        return result


__all__ = ["ChinaNBSAdapter"]
