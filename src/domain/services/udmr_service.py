"""领域层 UDMR 三层决策服务模块

执行 UDMR 路由决策：L1 合规检查 → 静态路由策略 → 日志持久化 → 事件发布

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from src.domain.entities.routing_decision_log import RoutingDecisionLog
from src.domain.events.routing_events import RoutingDecided
from src.domain.ports.compliance_gateway import ComplianceGatewayPort
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.health_check import HealthCheckPort
from src.domain.ports.routing_decision_log_repository import (
    RoutingDecisionLogRepository,
)
from src.domain.ports.udmr_policy import UdmrPolicyPort
from src.domain.value_objects.compliance_result import ComplianceResult
from src.domain.value_objects.udmr_task import UDMRTask

logger = logging.getLogger(__name__)


class UDMRService:
    """UDMR 三层决策服务.

    MVP 阶段实现 L1 合规检查 + L3 静态路由策略。
    L2 四因子评分由 Epic 11 Story 11.1 实现。

    构造器注入原始值（不依赖 UDMRConfig），遵循六边形架构。
    """

    def __init__(
        self,
        compliance_gateway: ComplianceGatewayPort | None = None,
        policy: UdmrPolicyPort | None = None,
        health_checker: HealthCheckPort | None = None,
        log_repo: RoutingDecisionLogRepository | None = None,
        publisher: EventPublisher | None = None,
        local_first: bool = False,
        local_model: str = "qwen2.5:7b",
        llm_timeout: int = 600,
    ) -> None:
        self._compliance_gateway = compliance_gateway
        self._policy = policy
        self._health_checker = health_checker
        self._log_repo = log_repo
        self._publisher = publisher
        self._local_first = local_first
        self._local_model = local_model
        self._llm_timeout = llm_timeout

    async def decide(self, task: UDMRTask) -> RoutingDecided:
        """执行 UDMR 路由决策.

        决策流程：
        1. L1 合规检查（ComplianceGatewayPort）
        2. 静态路由策略（UdmrPolicyPort）
        3. 健康检查（HealthCheckPort）
        4. 发布 RoutingDecided 事件
        5. 持久化路由决策日志

        Args:
            task: UDMR 路由任务

        Returns:
            RoutingDecided 路由决策事件
        """
        # 1. L1 合规检查
        compliance_result = await self._check_compliance(task)

        # 2. 静态路由策略
        assert self._policy is not None  # MVP 阶段保证注入
        route_type, selected_model, fallback_reason = await self._policy.route(task, compliance_result)

        # 3. 健康检查
        health_passed = await self._check_health()
        health_latency = 0.0

        # 4. 构造 RoutingDecided 事件
        event = RoutingDecided(
            task_id=task.task_id,
            route_type=route_type,
            selected_model=selected_model,
            estimated_cost=0.0,  # MVP 静态估算
            fallback_reason=fallback_reason,
            health_check_passed=health_passed,
            health_check_latency_ms=health_latency,
            l1_compliance_result={
                "allowed": compliance_result.allowed,
                "forced_local": compliance_result.forced_local,
                "reason": compliance_result.reason,
            },
            correlation_id=task.task_id,
        )

        # 5. 发布事件
        if self._publisher is not None:
            try:
                await self._publisher.publish(event)
            except Exception:
                logger.exception("Failed to publish RoutingDecided event")

        # 6. 持久化日志
        self._persist_decision_log(event, task)

        return event

    async def _check_compliance(self, task: UDMRTask) -> ComplianceResult:
        """执行 L1 合规检查."""
        if self._compliance_gateway is None:
            return ComplianceResult(allowed=True, forced_local=False)
        try:
            return await self._compliance_gateway.check(task)
        except Exception:
            logger.exception("L1 compliance check failed, defaulting to local")
            return ComplianceResult(allowed=True, forced_local=True)

    async def _check_health(self) -> bool:
        """执行云端健康检查."""
        if self._health_checker is None:
            return True
        try:
            return await self._health_checker.check()
        except Exception:
            logger.exception("Health check failed")
            return False

    def _persist_decision_log(self, event: RoutingDecided, task: UDMRTask) -> None:
        """异步持久化路由决策日志."""
        if self._log_repo is None:
            return

        log_entry = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id=str(task.task_id),
            session_id=str(task.task_id),  # MVP: 使用 task_id 作为 session_id
            route_type=event.route_type,
            route_target=event.selected_model,
            route_score=1.0,  # 静态路由固定评分
            selected_model=event.selected_model,
            cost_actual=0.0,  # MVP 阶段使用默认值
            fallback_reason=event.fallback_reason,
            timestamp=datetime.now(UTC),
        )

        async def _save() -> None:
            if self._log_repo is None:
                return
            try:
                await self._log_repo.save(log_entry)
            except Exception:
                logger.exception("Failed to persist routing decision log")

        try:
            asyncio.get_running_loop().create_task(_save())
        except RuntimeError:
            logger.debug("No running loop, skipping async decision log persist")
