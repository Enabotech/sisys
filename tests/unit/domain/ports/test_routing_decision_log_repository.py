"""RoutingDecisionLogRepository 聚合查询单元测试.

验证内存实现的聚合查询能力：
- 按时间范围查询成本摘要
- 按 route_type 过滤
- 空结果返回零值摘要

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.domain.entities.routing_decision_log import RoutingDecisionLog
from src.domain.ports.routing_decision_log_repository import CostSummary
from src.infrastructure.messaging.inmemory_routing_decision_log_repository import (
    InMemoryRoutingDecisionLogRepository,
)


class TestCostSummaryDataclass:
    """CostSummary 数据类测试."""

    def test_default_values(self) -> None:
        """默认值应为零."""
        summary = CostSummary()
        assert summary.total_cost == 0.0
        assert summary.total_prompt_tokens == 0
        assert summary.total_completion_tokens == 0
        assert summary.record_count == 0

    def test_custom_values(self) -> None:
        """自定义值应正确."""
        summary = CostSummary(
            total_cost=1.5,
            total_prompt_tokens=1000,
            total_completion_tokens=2000,
            record_count=5,
        )
        assert summary.total_cost == 1.5
        assert summary.total_prompt_tokens == 1000
        assert summary.total_completion_tokens == 2000
        assert summary.record_count == 5


def _make_log(
    task_id: str = "test-task",
    route_type: str = "local",
    cost_actual: float = 0.0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    timestamp: datetime | None = None,
) -> RoutingDecisionLog:
    """创建测试用 RoutingDecisionLog."""
    return RoutingDecisionLog(
        log_id=uuid.uuid4(),
        task_id=task_id,
        session_id="test-session",
        route_type=route_type,
        route_target="test-target",
        route_score=1.0,
        cost_actual=cost_actual,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        timestamp=timestamp or datetime.now(UTC),
    )


class TestInMemoryRoutingDecisionLogRepositoryAggregation:
    """聚合查询测试."""

    @pytest.fixture
    def repo(self) -> InMemoryRoutingDecisionLogRepository:
        """创建仓储实例."""
        return InMemoryRoutingDecisionLogRepository()

    async def test_query_cost_summary_empty(self, repo: InMemoryRoutingDecisionLogRepository) -> None:
        """空仓储返回零值摘要."""
        now = datetime.now(UTC)
        summary = await repo.query_cost_summary(
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
        )
        assert summary.total_cost == 0.0
        assert summary.record_count == 0

    async def test_query_cost_summary_with_records(self, repo: InMemoryRoutingDecisionLogRepository) -> None:
        """包含记录时返回正确聚合."""
        now = datetime.now(UTC)
        await repo.save(_make_log(task_id="t1", cost_actual=0.5, prompt_tokens=100, completion_tokens=200, timestamp=now))
        await repo.save(_make_log(task_id="t2", cost_actual=1.5, prompt_tokens=300, completion_tokens=400, timestamp=now))

        summary = await repo.query_cost_summary(
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
        )
        assert summary.total_cost == 2.0
        assert summary.total_prompt_tokens == 400
        assert summary.total_completion_tokens == 600
        assert summary.record_count == 2

    async def test_query_cost_summary_filter_by_route_type(self, repo: InMemoryRoutingDecisionLogRepository) -> None:
        """按 route_type 过滤."""
        now = datetime.now(UTC)
        await repo.save(_make_log(task_id="t1", route_type="local", cost_actual=0.5, timestamp=now))
        await repo.save(_make_log(task_id="t2", route_type="cloud", cost_actual=1.5, timestamp=now))

        summary = await repo.query_cost_summary(
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
            route_type="local",
        )
        assert summary.total_cost == 0.5
        assert summary.record_count == 1

    async def test_query_cost_summary_out_of_range(self, repo: InMemoryRoutingDecisionLogRepository) -> None:
        """时间范围外的记录不计入."""
        now = datetime.now(UTC)
        old_time = now - timedelta(days=7)
        await repo.save(_make_log(task_id="t1", cost_actual=1.0, timestamp=old_time))

        summary = await repo.query_cost_summary(
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
        )
        assert summary.record_count == 0
