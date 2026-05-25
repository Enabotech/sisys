"""Cost Metrics 集成测试.

端到端验证成本度量管线：RoutingDecided → CostMetricsListener → CostCalculator → Prometheus 指标

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.event_handlers.cost_metrics_handler import CostMetricsListener
from src.domain.entities.routing_decision_log import RoutingDecisionLog
from src.domain.events.routing_events import RoutingDecided
from src.domain.services.cost_calculator import CostCalculator
from src.infrastructure.messaging.inmemory_routing_decision_log_repository import (
    InMemoryRoutingDecisionLogRepository,
)
from src.infrastructure.monitoring.static_token_estimator import StaticTokenEstimator


@pytest.fixture
def token_estimator() -> StaticTokenEstimator:
    """创建真实的 StaticTokenEstimator."""
    return StaticTokenEstimator()


@pytest.fixture
def cost_calculator() -> CostCalculator:
    """创建真实的 CostCalculator（MVP 定价）."""
    return CostCalculator(
        local_input_price=0.002,
        local_output_price=0.002,
        cloud_input_price=0.02,
        cloud_output_price=0.02,
        model_pricing_map={},
    )


@pytest.fixture
def log_repo() -> InMemoryRoutingDecisionLogRepository:
    """创建真实的内存仓储."""
    return InMemoryRoutingDecisionLogRepository()


@pytest.fixture
def metrics() -> MagicMock:
    """创建 MetricsPort mock（记录调用）."""
    return MagicMock()


@pytest.fixture
def event_bus() -> AsyncMock:
    """创建 EventSubscriber mock."""
    return AsyncMock()


@pytest.fixture
def listener(
    token_estimator: StaticTokenEstimator,
    cost_calculator: CostCalculator,
    log_repo: InMemoryRoutingDecisionLogRepository,
    metrics: MagicMock,
    event_bus: AsyncMock,
) -> CostMetricsListener:
    """创建完整的 CostMetricsListener（真实依赖）."""
    return CostMetricsListener(
        token_estimator=token_estimator,
        cost_calculator=cost_calculator,
        log_repo=log_repo,
        metrics=metrics,
        event_bus=event_bus,
    )


def _make_log(
    task_id: uuid.UUID,
    route_type: str = "local",
    route_target: str = "qwen2.5:7b",
) -> RoutingDecisionLog:
    """创建测试用 RoutingDecisionLog."""
    return RoutingDecisionLog(
        log_id=uuid.uuid4(),
        task_id=str(task_id),
        session_id="test-session",
        route_type=route_type,
        route_target=route_target,
        route_score=1.0,
        cost_actual=0.0,
        timestamp=datetime.now(UTC),
    )


# ===================================================================
# 端到端管线集成测试
# ===================================================================


class TestCostMetricsIntegration:
    """端到端成本度量管线集成测试."""

    async def test_local_pipeline(
        self,
        listener: CostMetricsListener,
        log_repo: InMemoryRoutingDecisionLogRepository,
        metrics: MagicMock,
    ) -> None:
        """本地路由端到端：RoutingDecided → 估算(256+512) → 成本(0.001536) → 指标."""
        task_id = uuid.uuid4()
        await log_repo.save(_make_log(task_id, route_type="local", route_target="qwen2.5:7b"))

        event = RoutingDecided(
            task_id=task_id,
            route_type="local",
            selected_model="qwen2.5:7b",
        )

        await listener.on_routing_decided(event)

        # 验证日志更新
        log = await log_repo.find_by_task_id(str(task_id))
        assert log is not None
        assert log.prompt_tokens == 256
        assert log.completion_tokens == 512
        assert log.total_tokens == 768
        assert log.cost_actual == pytest.approx(0.001536)

        # 验证 Prometheus 指标
        metrics.record_token_usage.assert_called_once_with(256, 512, "qwen2.5:7b", "local")
        metrics.record_cost.assert_called_once_with(pytest.approx(0.001536), "qwen2.5:7b", "local")

    async def test_cloud_pipeline(
        self,
        listener: CostMetricsListener,
        log_repo: InMemoryRoutingDecisionLogRepository,
        metrics: MagicMock,
    ) -> None:
        """云端路由端到端：RoutingDecided → 估算(512+1024) → 成本(0.03072) → 指标."""
        task_id = uuid.uuid4()
        await log_repo.save(_make_log(task_id, route_type="cloud", route_target="MiniMax-M2.7"))

        event = RoutingDecided(
            task_id=task_id,
            route_type="cloud",
            selected_model="MiniMax-M2.7",
        )

        await listener.on_routing_decided(event)

        log = await log_repo.find_by_task_id(str(task_id))
        assert log is not None
        assert log.cost_actual == pytest.approx(0.03072)

        metrics.record_cost.assert_called_once_with(pytest.approx(0.03072), "MiniMax-M2.7", "cloud")

    async def test_aggregation_after_multiple_events(
        self,
        listener: CostMetricsListener,
        log_repo: InMemoryRoutingDecisionLogRepository,
    ) -> None:
        """多次事件后的聚合查询验证."""
        now = datetime.now(UTC)

        # 本地路由
        local_task = uuid.uuid4()
        await log_repo.save(_make_log(local_task, route_type="local", route_target="qwen2.5:7b"))
        await listener.on_routing_decided(RoutingDecided(task_id=local_task, route_type="local", selected_model="qwen2.5:7b"))

        # 云端路由
        cloud_task = uuid.uuid4()
        await log_repo.save(_make_log(cloud_task, route_type="cloud", route_target="MiniMax-M2.7"))
        await listener.on_routing_decided(RoutingDecided(task_id=cloud_task, route_type="cloud", selected_model="MiniMax-M2.7"))

        # 聚合查询
        summary = await log_repo.query_cost_summary(
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
        )

        assert summary.record_count == 2
        assert summary.total_cost == pytest.approx(0.001536 + 0.03072)
        assert summary.total_prompt_tokens == 256 + 512
        assert summary.total_completion_tokens == 512 + 1024

    async def test_aggregation_filter_by_route_type(
        self,
        listener: CostMetricsListener,
        log_repo: InMemoryRoutingDecisionLogRepository,
    ) -> None:
        """聚合查询按 route_type 过滤."""
        now = datetime.now(UTC)

        local_task = uuid.uuid4()
        await log_repo.save(_make_log(local_task, route_type="local", route_target="qwen2.5:7b"))
        await listener.on_routing_decided(RoutingDecided(task_id=local_task, route_type="local", selected_model="qwen2.5:7b"))

        cloud_task = uuid.uuid4()
        await log_repo.save(_make_log(cloud_task, route_type="cloud", route_target="MiniMax-M2.7"))
        await listener.on_routing_decided(RoutingDecided(task_id=cloud_task, route_type="cloud", selected_model="MiniMax-M2.7"))

        # 仅查询本地
        local_summary = await log_repo.query_cost_summary(
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
            route_type="local",
        )
        assert local_summary.record_count == 1
        assert local_summary.total_cost == pytest.approx(0.001536)

        # 仅查询云端
        cloud_summary = await log_repo.query_cost_summary(
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
            route_type="cloud",
        )
        assert cloud_summary.record_count == 1
        assert cloud_summary.total_cost == pytest.approx(0.03072)

    async def test_register_subscribes_correctly(
        self,
        listener: CostMetricsListener,
        event_bus: AsyncMock,
    ) -> None:
        """register() 正确订阅 RoutingDecided 事件."""
        await listener.register()
        event_bus.subscribe_async.assert_called_once_with(
            "RoutingDecided",
            listener.on_routing_decided,
        )
