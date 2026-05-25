"""应用层成本度量事件处理器模块

订阅 RoutingDecided 事件，估算 Token 消耗、计算成本、更新日志、记录 Prometheus 指标

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import dataclasses
import logging

from src.application.ports.event_subscriber import EventSubscriber
from src.application.ports.metrics_port import MetricsPort
from src.domain.events.base import DomainEvent
from src.domain.events.routing_events import RoutingDecided
from src.domain.ports.routing_decision_log_repository import RoutingDecisionLogRepository
from src.domain.ports.token_estimator import TokenEstimatorPort
from src.domain.services.cost_calculator import CostCalculator
from src.domain.value_objects.token_consumption import TokenConsumption

logger = logging.getLogger(__name__)


class CostMetricsListener:
    """成本度量事件处理器.

    订阅 RoutingDecided 事件，完成 Token 估算 → 成本计算 → 日志更新 → 指标记录

    Attributes:
        _token_estimator: Token 估算端口
        _cost_calculator: 成本计算领域服务
        _log_repo: 路由决策日志仓储
        _metrics: 指标采集端口
        _event_bus: 事件订阅端口
    """

    def __init__(
        self,
        token_estimator: TokenEstimatorPort,
        cost_calculator: CostCalculator,
        log_repo: RoutingDecisionLogRepository,
        metrics: MetricsPort,
        event_bus: EventSubscriber,
    ) -> None:
        self._token_estimator = token_estimator
        self._cost_calculator = cost_calculator
        self._log_repo = log_repo
        self._metrics = metrics
        self._event_bus = event_bus

    async def on_routing_decided(self, event: DomainEvent) -> None:
        """处理 RoutingDecided 事件.

        MVP 阶段：Token 逐字段 fallback（event > 0 则用事件值，否则用估算器）
        计算成本、更新日志、记录指标，异常时记录日志不中断流程

        Args:
            event: 领域事件（期望为 RoutingDecided）
        """
        if not isinstance(event, RoutingDecided):
            return

        try:
            # Token 获取：逐字段 fallback（event > 0 则用事件值，否则用估算器）
            event_prompt = event.prompt_tokens
            event_completion = event.completion_tokens

            if event_prompt > 0 and event_completion > 0:
                prompt_tokens = event_prompt
                completion_tokens = event_completion
            else:
                estimated_prompt, estimated_completion = await self._token_estimator.estimate(
                    event.route_type,
                    event.selected_model,
                )
                # 逐字段 fallback：event > 0 用 event，否则用 estimate
                prompt_tokens = event_prompt if event_prompt > 0 else estimated_prompt
                completion_tokens = event_completion if event_completion > 0 else estimated_completion

            consumption = TokenConsumption(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

            cost = self._cost_calculator.calculate(
                consumption,
                event.route_type,
                event.selected_model,
            )

            # 更新日志（如果存在）
            log = await self._log_repo.find_by_task_id(str(event.task_id))
            if log is not None:
                updated = dataclasses.replace(
                    log,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=consumption.total_tokens,
                    cost_actual=cost,
                )
                await self._log_repo.save(updated)

            # 记录 Prometheus 指标
            self._metrics.record_token_usage(
                prompt_tokens,
                completion_tokens,
                event.selected_model,
                event.route_type,
            )
            self._metrics.record_cost(
                cost,
                event.selected_model,
                event.route_type,
            )

            logger.info(
                "Cost metrics recorded: route_type=%s, model=%s, cost=%.6f, tokens=%d",
                event.route_type,
                event.selected_model,
                cost,
                consumption.total_tokens,
            )
        except Exception:
            logger.exception(
                "Failed to process RoutingDecided event: task_id=%s, route_type=%s",
                event.task_id,
                event.route_type,
            )

    async def register(self) -> None:
        """注册事件订阅（subscribe_async RoutingDecided）."""
        await self._event_bus.subscribe_async("RoutingDecided", self.on_routing_decided)
        logger.info("CostMetricsListener registered for RoutingDecided events")
