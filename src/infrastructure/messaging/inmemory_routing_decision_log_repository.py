"""基础设施层内存路由决策日志仓储模块

基于内存的 RoutingDecisionLogRepository 实现，适用于测试和 MVP 阶段
内置 asyncio.Lock 保证并发安全，max_size + TTL 防止无界增长

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict
from datetime import datetime

from src.domain.entities.routing_decision_log import RoutingDecisionLog
from src.domain.ports.routing_decision_log_repository import CostSummary

logger = logging.getLogger(__name__)


class InMemoryRoutingDecisionLogRepository:
    """内存路由决策日志仓储实现

    内置并发安全（asyncio.Lock）和容量控制（max_size + TTL eviction）
    """

    _DEFAULT_MAX_SIZE = 1000
    _DEFAULT_TTL_SECONDS = 86400  # 24 小时

    def __init__(
        self,
        max_size: int = _DEFAULT_MAX_SIZE,
        ttl_seconds: float = _DEFAULT_TTL_SECONDS,
    ) -> None:
        self._logs: OrderedDict[str, tuple[RoutingDecisionLog, float]] = OrderedDict()
        self._lock = asyncio.Lock()
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds

    async def save(self, log: RoutingDecisionLog) -> None:
        """保存路由决策日志到内存"""
        async with self._lock:
            self._logs[str(log.log_id)] = (log, time.monotonic())
            self._cleanup_unlocked()
        logger.debug("Saved routing decision log: log_id=%s", log.log_id)

    async def find_by_task_id(self, task_id: str) -> RoutingDecisionLog | None:
        """根据任务 ID 查找路由决策日志"""
        async with self._lock:
            for log, _ in self._logs.values():
                if log.task_id == task_id:
                    return log
        return None

    async def query_cost_summary(
        self,
        start_time: datetime,
        end_time: datetime,
        route_type: str | None = None,
    ) -> CostSummary:
        """按时间范围聚合查询成本摘要"""
        total_cost = 0.0
        total_prompt_tokens = 0
        total_completion_tokens = 0
        record_count = 0

        async with self._lock:
            for log, _ in self._logs.values():
                # 闭区间查询：[start_time, end_time]，包含边界值
                if log.timestamp < start_time or log.timestamp > end_time:
                    continue
                if route_type is not None and log.route_type != route_type:
                    continue
                total_cost += log.cost_actual
                total_prompt_tokens += log.prompt_tokens
                total_completion_tokens += log.completion_tokens
                record_count += 1

        return CostSummary(
            total_cost=total_cost,
            total_prompt_tokens=total_prompt_tokens,
            total_completion_tokens=total_completion_tokens,
            record_count=record_count,
        )

    def _cleanup_unlocked(self) -> None:
        """淘汰过期和超量记录（调用方需已持有锁）"""
        now = time.monotonic()
        # TTL 淘汰
        expired = [k for k, (_, ts) in self._logs.items() if now - ts > self._ttl_seconds]
        for k in expired:
            del self._logs[k]
        # FIFO 超量淘汰
        while len(self._logs) > self._max_size:
            self._logs.popitem(last=False)
