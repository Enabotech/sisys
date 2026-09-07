"""应用层 ToolExecuted 事件处理器

订阅 ToolExecuted 事件 → 更新 Tool.reliability_score 和 Tool.execution_count。

设计依据：Story 4.1a AC-5 工具执行闭环
- ToolExecutionEngine.execute() 完成 → StrategicAnalysisUseCase 发布 ToolExecuted 事件
- 双通道（realtime + reliable）分发
- 本 Handler 订阅 → 调用 ToolRegistryService.update_tool_statistics()
- 最终一致投影（不阻塞执行链路）

可靠性评分算法（Beta 分布衰减加权，业界最佳实践）：
- reliability_score = old * 0.9 + (1.0 if success else 0.0) * 0.1
- 钳位到 [0.0, 1.0] 范围
"""

from __future__ import annotations

import logging

from src.application.services.tool_registry_service import ToolRegistryService
from src.domain.events.tool_events import ToolExecuted

logger = logging.getLogger(__name__)


class ToolExecutedEventHandler:
    """ToolExecuted 事件订阅者 → 更新 Tool statistics（最终一致投影）

    订阅语义：监听所有 ToolExecuted 事件，对每个事件执行：
    1. 提取 execution_result.status 判定 success/failure
    2. 调用 ToolRegistryService.update_tool_statistics()
    3. Beta 分布衰减加权更新 reliability_score + execution_count

    错误处理：handler 失败不重试（事件已持久化到 reliable channel，
    后续可通过 outbox pattern 重放或人工补偿）。
    """

    def __init__(self, tool_registry: ToolRegistryService) -> None:
        """初始化事件处理器

        Args:
            tool_registry: 工具注册服务（用于更新 Tool statistics）
        """
        self._registry = tool_registry
        # 测试辅助：收集已处理事件（集成测试验证事件分发）
        self.received_events: list[ToolExecuted] = []

    async def handle(self, event: ToolExecuted) -> None:
        """处理 ToolExecuted 事件

        Args:
            event: ToolExecuted 事件（execution_id + tool_id + execution_result）
        """
        # 0. 记录事件（用于测试验证）
        self.received_events.append(event)

        # 1. 提取 success 信号
        execution_result = event.execution_result or {}
        status = execution_result.get("status", "unknown")
        success = status == "success"

        # 2. 更新 Tool statistics（Beta 分布衰减加权）
        try:
            updated_tool = self._registry.update_tool_statistics(
                tool_id=event.tool_id,
                success=success,
            )
            logger.info(
                "Tool statistics 更新成功: tool_id=%s execution_count=%s reliability_score=%.3f",
                event.tool_id,
                updated_tool.execution_count,
                updated_tool.reliability_score,
            )
        except (KeyError, ValueError, AttributeError) as exc:
            # Handler 失败不阻塞后续处理（事件已持久化到 reliable channel）
            logger.error(
                "Tool statistics 更新失败: tool_id=%s exc=%s",
                event.tool_id,
                exc,
            )


__all__ = ["ToolExecutedEventHandler"]
