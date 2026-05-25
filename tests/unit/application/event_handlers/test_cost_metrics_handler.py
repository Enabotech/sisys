"""CostMetricsListener 单元测试.

验证成本度量事件处理器：
- 订阅 RoutingDecided 事件
- 调用 TokenEstimatorPort 估算 Token（MVP）
- 调用 CostCalculator 计算成本
- 更新 RoutingDecisionLog
- 记录 Prometheus 指标

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.event_handlers.cost_metrics_handler import CostMetricsListener
from src.domain.entities.routing_decision_log import RoutingDecisionLog
from src.domain.events.base import DomainEvent
from src.domain.events.routing_events import RoutingDecided
from src.domain.ports.token_estimator import TokenEstimatorPort
from src.domain.services.cost_calculator import CostCalculator
from src.infrastructure.messaging.inmemory_routing_decision_log_repository import (
    InMemoryRoutingDecisionLogRepository,
)


@pytest.fixture
def token_estimator() -> AsyncMock:
    """创建 TokenEstimatorPort mock."""
    estimator = AsyncMock(spec=TokenEstimatorPort)
    estimator.estimate.return_value = (256, 512)
    return estimator


@pytest.fixture
def cost_calculator() -> CostCalculator:
    """创建 CostCalculator 实例（已知定价）."""
    return CostCalculator(
        local_input_price=0.002,
        local_output_price=0.002,
        cloud_input_price=0.02,
        cloud_output_price=0.02,
        model_pricing_map={},
    )


@pytest.fixture
def log_repo() -> InMemoryRoutingDecisionLogRepository:
    """创建内存仓储实例."""
    return InMemoryRoutingDecisionLogRepository()


@pytest.fixture
def metrics() -> MagicMock:
    """创建 MetricsPort mock."""
    return MagicMock()


@pytest.fixture
def event_bus() -> AsyncMock:
    """创建 EventSubscriber mock."""
    return AsyncMock()


@pytest.fixture
def handler(
    token_estimator: AsyncMock,
    cost_calculator: CostCalculator,
    log_repo: InMemoryRoutingDecisionLogRepository,
    metrics: MagicMock,
    event_bus: AsyncMock,
) -> CostMetricsListener:
    """创建 CostMetricsListener 实例."""
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
# 本地路由成本计算测试
# ===================================================================


class TestCostMetricsListenerLocalCost:
    """本地路由成本计算测试."""

    async def test_local_cost_calculation(
        self,
        handler: CostMetricsListener,
        token_estimator: AsyncMock,
        log_repo: InMemoryRoutingDecisionLogRepository,
        metrics: MagicMock,
    ) -> None:
        """本地路由: (256×0.002 + 512×0.002) / 1000 = 0.001536."""
        task_id = uuid.uuid4()
        await log_repo.save(_make_log(task_id, route_type="local", route_target="qwen2.5:7b"))

        event = RoutingDecided(
            task_id=task_id,
            route_type="local",
            selected_model="qwen2.5:7b",
        )

        await handler.on_routing_decided(event)

        token_estimator.estimate.assert_called_once_with("local", "qwen2.5:7b")
        metrics.record_token_usage.assert_called_once_with(256, 512, "qwen2.5:7b", "local")
        metrics.record_cost.assert_called_once_with(0.001536, "qwen2.5:7b", "local")

        updated = await log_repo.find_by_task_id(str(task_id))
        assert updated is not None
        assert updated.prompt_tokens == 256
        assert updated.completion_tokens == 512
        assert updated.total_tokens == 768
        assert updated.cost_actual == pytest.approx(0.001536)


# ===================================================================
# 云端路由成本计算测试
# ===================================================================


class TestCostMetricsListenerCloudCost:
    """云端路由成本计算测试."""

    async def test_cloud_cost_calculation(
        self,
        handler: CostMetricsListener,
        token_estimator: AsyncMock,
        log_repo: InMemoryRoutingDecisionLogRepository,
        metrics: MagicMock,
    ) -> None:
        """云端路由: (512×0.02 + 1024×0.02) / 1000 = 0.03072."""
        token_estimator.estimate.return_value = (512, 1024)
        task_id = uuid.uuid4()
        await log_repo.save(_make_log(task_id, route_type="cloud", route_target="MiniMax-M2.7"))

        event = RoutingDecided(
            task_id=task_id,
            route_type="cloud",
            selected_model="MiniMax-M2.7",
        )

        await handler.on_routing_decided(event)

        metrics.record_cost.assert_called_once_with(pytest.approx(0.03072), "MiniMax-M2.7", "cloud")

        updated = await log_repo.find_by_task_id(str(task_id))
        assert updated is not None
        assert updated.cost_actual == pytest.approx(0.03072)


# ===================================================================
# 事件类型过滤测试
# ===================================================================


class TestCostMetricsListenerEventFilter:
    """事件类型过滤测试."""

    async def test_ignores_non_routing_decided_event(
        self,
        handler: CostMetricsListener,
        token_estimator: AsyncMock,
        metrics: MagicMock,
    ) -> None:
        """非 RoutingDecided 事件应忽略."""
        other_event = DomainEvent()
        await handler.on_routing_decided(other_event)

        token_estimator.estimate.assert_not_called()
        metrics.record_token_usage.assert_not_called()
        metrics.record_cost.assert_not_called()

    async def test_uses_estimator_when_tokens_zero(
        self,
        handler: CostMetricsListener,
        token_estimator: AsyncMock,
        metrics: MagicMock,
    ) -> None:
        """Token 为 0 时使用估算器（MVP）."""
        event = RoutingDecided(
            task_id=uuid.uuid4(),
            route_type="local",
            selected_model="qwen2.5:7b",
            prompt_tokens=0,
            completion_tokens=0,
        )

        await handler.on_routing_decided(event)

        token_estimator.estimate.assert_called_once()

    async def test_uses_event_tokens_when_nonzero(
        self,
        handler: CostMetricsListener,
        token_estimator: AsyncMock,
        log_repo: InMemoryRoutingDecisionLogRepository,
        metrics: MagicMock,
    ) -> None:
        """Token 非零时直接使用事件数据（未来实际 Token 场景）."""
        task_id = uuid.uuid4()
        await log_repo.save(_make_log(task_id))

        event = RoutingDecided(
            task_id=task_id,
            route_type="local",
            selected_model="qwen2.5:7b",
            prompt_tokens=100,
            completion_tokens=200,
        )

        await handler.on_routing_decided(event)

        # 不应调用估算器
        token_estimator.estimate.assert_not_called()
        # 使用事件中的 Token 值
        metrics.record_token_usage.assert_called_once_with(100, 200, "qwen2.5:7b", "local")


# ===================================================================
# 无日志场景测试
# ===================================================================


class TestCostMetricsListenerNoLog:
    """无对应日志场景测试."""

    async def test_no_log_still_records_metrics(
        self,
        handler: CostMetricsListener,
        metrics: MagicMock,
    ) -> None:
        """无对应日志时不报错，仍记录指标."""
        event = RoutingDecided(
            task_id=uuid.uuid4(),
            route_type="local",
            selected_model="qwen2.5:7b",
        )

        await handler.on_routing_decided(event)

        metrics.record_token_usage.assert_called_once()
        metrics.record_cost.assert_called_once()


# ===================================================================
# 事件订阅注册测试
# ===================================================================


class TestCostMetricsListenerRegister:
    """事件订阅注册测试."""

    async def test_register_subscribes_to_routing_decided(
        self,
        handler: CostMetricsListener,
        event_bus: AsyncMock,
    ) -> None:
        """register() 订阅 RoutingDecided 事件."""
        await handler.register()

        event_bus.subscribe_async.assert_called_once_with(
            "RoutingDecided",
            handler.on_routing_decided,
        )
