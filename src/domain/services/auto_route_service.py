"""领域层自动路由服务模块

AutoRouteService 是处理 AutoTriggered 事件并发出 AutoRouted 事件的领域服务
监听 AutoTriggerService 发出的 AutoTriggered 事件，使用哈希路由（会话一致性）
和/或语义路由（目标匹配）进行路由决策，并发布 AutoRouted 事件给下游执行阶段

架构：领域层（无外部依赖），通过端口/协议实现路由和事件发布

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import logging

from src.domain.events.auto_route_events import AutoRouted
from src.domain.events.auto_trigger_events import AutoTriggered
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.hash_router_protocol import HashRouterProtocol
from src.domain.ports.semantic_router_protocol import SemanticRouterProtocol

logger = logging.getLogger(__name__)


class AutoRouteService:
    """监听 AutoTriggered 事件、执行路由决策并发出 AutoRouted 事件的领域服务

    职责：
    - 监听 AutoTriggerService 发出的 AutoTriggered 事件（Story 1.14a）
    - 使用哈希路由（会话一致性）和/或语义路由（目标匹配）进行路由决策
    - 发布 AutoRouted 事件给下游执行阶段（Story 1.14c）
    - 将路由决策记录到 RoutingDecisionLog

    架构：领域层（无外部依赖），通过端口/协议实现路由和事件发布
    """

    def __init__(
        self,
        publisher: EventPublisher | None = None,
        hash_router: HashRouterProtocol | None = None,
        semantic_router: SemanticRouterProtocol | None = None,
    ):
        """初始化 AutoRouteService

        Args:
            publisher: 事件发布器端口（基础设施实现）。传入 None 用于独立测试
            hash_router: 哈希路由器端口（基础设施实现）。传入 None 禁用哈希路由
            semantic_router: 语义路由器端口（基础设施实现）。传入 None 禁用语义路由
        """
        self._publisher = publisher
        self._hash_router = hash_router
        self._semantic_router = semantic_router

    async def on_triggered_event(self, event: AutoTriggered) -> AutoRouted:
        """处理 AutoTriggered 事件：执行路由决策并发出 AutoRouted 事件

        Args:
            event: 来自触发阶段（Story 1.14a）的 AutoTriggered 事件

        Returns:
            路由决策完成并发布后返回 AutoRouted 事件，否则返回 None
        """
        logger.debug("Processing AutoTriggered event: session_id=%s", event.session_id)

        # Determine route type and target based on available routers
        route_type, route_target, route_score = await self._make_routing_decision(event)

        routed = AutoRouted(
            route_type=route_type,
            session_id=event.session_id,
            task_context=event.task_context,
            route_target=route_target,
            route_score=route_score,
            trigger_event_type=event.event_type,
            trigger_event_id=str(event.event_id) if event.event_id else None,
        )

        await self._publish(routed)
        return routed

    async def _make_routing_decision(self, event: AutoTriggered) -> tuple[str, str, float]:
        """根据可用路由器进行路由决策

        Args:
            event: AutoTriggered 事件

        Returns:
            元组 (route_type, route_target, route_score)
        """
        hash_target = ""
        hash_score = 0.0
        semantic_target = ""
        semantic_score = 0.0

        # Hash routing (session consistency)
        if self._hash_router is not None:
            hash_target = self._hash_router.route(event.session_id)
            hash_score = 1.0  # Hash routing is deterministic, 100% confidence

        # Semantic routing (target matching)
        if self._semantic_router is not None:
            semantic_target, semantic_score = await self._semantic_router.route(event.task_context)

        # Determine final route type and target
        if hash_target and semantic_target:
            # In mixed mode, prefer semantic routing (more intelligent matching)
            # when it returns a valid target
            if semantic_target:
                route_type = "mixed"
                route_target = semantic_target
                route_score = semantic_score
            else:
                route_type = "hash"
                route_target = hash_target
                route_score = hash_score
        elif semantic_target:
            route_type = "semantic"
            route_target = semantic_target
            route_score = semantic_score
        elif hash_target:
            route_type = "hash"
            route_target = hash_target
            route_score = hash_score
        else:
            # No router available, use defaults
            route_type = "hash"
            route_target = "default"
            route_score = 0.0

        return route_type, route_target, route_score

    async def _publish(self, event: AutoRouted) -> None:
        """通过已配置的发布器发布 AutoRouted 事件

        Args:
            event: 待发布的 AutoRouted 事件
        """
        if self._publisher is None:
            logger.warning("No publisher configured, AutoRouted event not published: %s", event.event_id)
            return

        try:
            await self._publisher.publish(event, channel="rt:AutoRouted")
            logger.info(
                "Published AutoRouted event: session_id=%s route_type=%s route_target=%s score=%.3f",
                event.session_id,
                event.route_type,
                event.route_target,
                event.route_score,
            )
        except Exception as e:
            logger.error("Failed to publish AutoRouted event: %s", e)
            raise
