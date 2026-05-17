"""应用层自动执行完成处理器模块

自动执行完成事件监听器，监听 AutoExecuted 事件并发布下游领域事件
（DocumentProcessed/ToolExecuted/AgentDecided），根据 business_event_type 决定事件类型

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import logging

from src.domain.events.auto_execute_events import AutoExecuted
from src.domain.events.base import DomainEvent
from src.domain.ports.event_publisher import EventPublisher

logger = logging.getLogger(__name__)


class AutoExecuteCompletedHandler:
    """处理 AutoExecuted 事件的事件监听器

    职责：
    - 监听 AutoExecuteService 的 AutoExecuted 事件
    - 根据 business_event_type 发布对应的领域事件：
      - "DocumentProcessed" -> DocumentProcessed 事件
      - "ToolExecuted" -> ToolExecuted 事件
      - "AgentDecided" -> AgentDecided 事件

    架构：接口层，实现事件监听模式

    Attributes:
        _publisher: 事件发布器端口，None 用于独立测试
    """

    def __init__(self, publisher: EventPublisher | None = None):
        """初始化自动执行完成监听器

        Args:
            publisher: 事件发布器端口，None 用于独立测试
        """
        self._publisher = publisher

    async def on_executed(self, event: AutoExecuted) -> None:
        """处理 AutoExecuted 事件：发布下游领域事件

        Args:
            event: 来自 ExecuteService 的 AutoExecuted 事件
        """
        business_event_type = event.business_event_type or "ToolExecuted"

        logger.info(
            "Processing AutoExecuted event: session_id=%s business_event_type=%s",
            event.session_id,
            business_event_type,
        )

        # Build domain event based on business_event_type
        if business_event_type == "DocumentProcessed":
            await self._publish_document_processed(event)
        elif business_event_type == "ToolExecuted":
            await self._publish_tool_executed(event)
        elif business_event_type == "AgentDecided":
            await self._publish_agent_decided(event)
        else:
            logger.warning("Unknown business_event_type: %s, defaulting to ToolExecuted", business_event_type)
            await self._publish_tool_executed(event)

    async def _publish_document_processed(self, event: AutoExecuted) -> None:
        """发布 DocumentProcessed 领域事件"""
        from src.domain.events.document_events import DocumentProcessed

        domain_event = DocumentProcessed(
            document_id=event.task_context.get("document_id", ""),
            parse_result=event.execution_result,
        )

        await self._publish(domain_event, "domain:DocumentProcessed")
        logger.info("Published DocumentProcessed: document_id=%s", domain_event.document_id)

    async def _publish_tool_executed(self, event: AutoExecuted) -> None:
        """发布 ToolExecuted 领域事件"""
        from src.domain.events.tool_events import ToolExecuted

        domain_event = ToolExecuted(
            tool_id=event.task_context.get("tool_id", ""),
            execution_result=event.execution_result,
            cost_audit={"estimated": event.cost_estimate},
        )

        await self._publish(domain_event, "domain:ToolExecuted")
        logger.info("Published ToolExecuted: tool_id=%s", domain_event.tool_id)

    async def _publish_agent_decided(self, event: AutoExecuted) -> None:
        """发布 AgentDecided 领域事件"""
        from src.domain.events.agent_events import AgentDecided

        domain_event = AgentDecided(
            agent_id=event.task_context.get("agent_id", ""),
            decision_result=event.execution_result,
            confidence=event.route_score,
        )

        await self._publish(domain_event, "domain:AgentDecided")
        logger.info("Published AgentDecided: agent_id=%s", domain_event.agent_id)

    async def _publish(self, event: DomainEvent, channel: str) -> None:
        """通过配置的发布器发布领域事件

        Args:
            event: 待发布的领域事件
            channel: 频道名称
        """
        if self._publisher is None:
            logger.warning("No publisher configured, event not published: %s", event.event_type)
            return

        try:
            await self._publisher.publish(event, channel=channel)
            logger.debug("Published event: type=%s channel=%s", event.event_type, channel)
        except Exception as e:
            logger.error("Failed to publish %s event: %s", event.event_type, e)
            raise
