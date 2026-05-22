"""应用层 UDMR 事件处理器模块

处理 AutoRouted 事件，调用 UDMRService.decide() 发布 RoutingDecided 事件

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import logging
import uuid

from src.application.ports.event_subscriber import EventSubscriber
from src.domain.events.auto_route_events import AutoRouted
from src.domain.events.base import DomainEvent
from src.domain.events.routing_events import RoutingDecided
from src.domain.services.udmr_service import UDMRService
from src.domain.value_objects.udmr_task import UDMRTask

logger = logging.getLogger(__name__)


class UDMRHandler:
    """UDMR 事件处理器（带外模式）.

    并行消费 AutoRouted 事件，调用 UDMRService.decide() 发布 RoutingDecided 事件。
    不阻塞 AutoExecuteService 执行管线。

    Attributes:
        _udmr_service: UDMR 三层决策服务
        _event_bus: DualChannelEventBus（实现 EventSubscriber）
        _enabled: 是否启用 UDMR 处理
    """

    def __init__(
        self,
        udmr_service: UDMRService,
        event_bus: EventSubscriber,
        enabled: bool = True,
    ) -> None:
        self._udmr_service = udmr_service
        self._event_bus = event_bus
        self._enabled = enabled

    async def on_routed(self, event: DomainEvent) -> RoutingDecided | None:
        """处理 AutoRouted 事件.

        Args:
            event: 领域事件（期望为 AutoRouted）

        Returns:
            RoutingDecided 事件，或 None（跳过处理）
        """
        if not self._enabled:
            return None

        if not isinstance(event, AutoRouted):
            logger.warning(
                "UDMRHandler received non-AutoRouted event: %s",
                type(event).__name__,
            )
            return None

        # 从 task_context 提取字段构造 UDMRTask
        task_context = event.task_context or {}
        task = UDMRTask(
            task_id=uuid.uuid4(),
            input=task_context.get("input", ""),
            data_residency=task_context.get("data_residency", "CHINA_DOMESTIC"),
            preferred_model=task_context.get("preferred_model", ""),
            allowed_models=task_context.get("allowed_models", []),
        )

        # 调用 UDMRService.decide()
        try:
            decided = await self._udmr_service.decide(task)
            logger.info(
                "UDMR decided: route_type=%s, model=%s",
                decided.route_type,
                decided.selected_model,
            )
            return decided
        except Exception:
            logger.exception("UDMRService.decide() failed")
            return None

    async def register(self) -> None:
        """注册事件订阅（subscribe_async AutoRouted）."""
        if self._enabled:
            await self._event_bus.subscribe_async("AutoRouted", self.on_routed)
            logger.info("UDMRHandler registered for AutoRouted events")
