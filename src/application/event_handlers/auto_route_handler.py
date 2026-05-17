"""应用层自动路由处理器模块

自动路由机制的事件监听器，监听 AutoTriggerService 的 AutoTriggered 事件（Story 1.14a），
调用 AutoRouteService 做路由决策，并发布 AutoRouted 事件到下游执行阶段（Story 1.14c）

注意：与 UDMR 的 RoutingDecided 事件（Story 1.17）不同：
    - AutoRouteListener 发出: AutoRouted（auto_route_events.py）— 选择 Agent/工具
    - UDMR 发出: RoutingDecided（routing_events.py）— 选择本地/云模型

参考: Story 1.14b SDD规范定义
参考: or.md 系统公理一 (trigger→route→execute)

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import logging

from src.domain.events.auto_route_events import AutoRouted
from src.domain.events.base import DomainEvent
from src.domain.ports.event_publisher import EventPublisher
from src.domain.services.auto_route_service import AutoRouteService

logger = logging.getLogger(__name__)


class AutoRouteHandler:
    """事件监听器，桥接 AutoTriggered 事件到 AutoRouteService

    职责：
    - 监听 AutoTriggerService 的 AutoTriggered 事件（Story 1.14a）
    - 调用 AutoRouteService 做路由决策
    - 发布 AutoRouted 事件到下游执行阶段（Story 1.14c）

    架构：接口层，实现事件监听模式
    遵循六边形架构：领域逻辑（AutoRouteService）与基础设施关注点（事件总线、日志）隔离
    """

    def __init__(
        self,
        auto_route_service: AutoRouteService,
        publisher: EventPublisher | None = None,
    ) -> None:
        """初始化自动路由监听器

        Args:
            auto_route_service: 路由决策领域服务
            publisher: 事件发布器端口，None 用于独立测试
        """
        self._auto_route_service = auto_route_service
        self._publisher = publisher

    async def on_triggered(self, event: DomainEvent) -> AutoRouted | None:
        """处理 AutoTriggered 事件：做路由决策并发出 AutoRouted

        Args:
            event: 来自 AutoTriggerService 的 AutoTriggered 事件（Story 1.14a）

        Returns:
            路由决策完成返回 AutoRouted 事件，否则返回 None
        """
        from src.domain.events.auto_trigger_events import AutoTriggered

        if not isinstance(event, AutoTriggered):
            logger.warning("Received non-AutoTriggered event: %s", type(event).__name__)
            return None

        logger.info(
            "Processing AutoTriggered event: session_id=%s trigger_type=%s",
            event.session_id,
            getattr(event, "trigger_type", "unknown"),
        )

        try:
            routed = await self._auto_route_service.on_triggered_event(event)

            if routed is not None:
                logger.info(
                    "Route completed: session_id=%s route_type=%s route_target=%s score=%.3f",
                    routed.session_id,
                    routed.route_type,
                    routed.route_target,
                    routed.route_score,
                )
                await self._publish(routed)
            else:
                logger.warning("AutoRouteService returned None for AutoTriggered event")

            return routed

        except Exception as e:
            logger.error("Failed to process AutoTriggered event: %s", e)
            raise

    async def _publish(self, event: AutoRouted, channel: str | None = None) -> None:
        """通过配置的发布器发布 AutoRouted 事件

        Args:
            event: 待发布的 AutoRouted 事件
            channel: 频道名称（默认 "rt:AutoRouted"）
        """
        if self._publisher is None:
            logger.warning("No publisher configured, AutoRouted event not published")
            return

        try:
            await self._publisher.publish(event, channel=channel or "rt:AutoRouted")
            logger.debug("Published AutoRouted event: session_id=%s", event.session_id)
        except Exception as e:
            logger.error("Failed to publish AutoRouted event: %s", e)
            raise
