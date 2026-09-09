"""应用层战略分析用例模块

实现 StrategicAnalysisUseCase，编排工具执行完整链路：
tool_name → Skill 加载 → ToolExecutionService.execute → ToolExecuted 事件发布

设计依据：Story 4.1a AC-5
- 委托 SkillLoaderPort 加载技能元数据
- 委托 ToolExecutionService 执行
- 通过 EventBusPort 发布 ToolExecuted 事件（双通道）
- 通过 ToolRegistryServicePort 查询 Tool 元数据
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from src.application.ports.skill_loader import SkillLoaderPort
from src.application.ports.tool_execution_service import ToolExecutionServicePort
from src.application.ports.tool_registry_service import ToolRegistryServicePort
from src.domain.entities.tool import Tool
from src.domain.events.tool_events import ToolExecuted
from src.domain.exceptions.tool_exceptions import ToolNotFoundError
from src.domain.ports.event_publisher import EventPublisher
from src.domain.value_objects.tool_execution import (
    ExecutionContext,
    ToolCall,
    ToolResult,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StrategicAnalysisRequest:
    """战略分析请求值对象

    Attributes:
        tool_name: 工具名称（用于 Skill 加载）
        arguments: 调用参数
        user_id: 用户唯一标识
        session_id: 会话唯一标识
        trace_id: 链路追踪 ID
    """

    tool_name: str
    arguments: dict[str, Any]
    user_id: uuid.UUID | None = None
    session_id: str = ""
    trace_id: str = ""


class StrategicAnalysisUseCase:
    """战略分析用例

    编排完整链路：tool_name 查询 → Skill 加载 → ToolExecutionService.execute
                  → ToolExecuted 事件发布

    依赖通过端口注入，不导入 infrastructure 具体实现。
    """

    def __init__(
        self,
        tool_registry: ToolRegistryServicePort,
        execution_service: ToolExecutionServicePort,
        skill_loader: SkillLoaderPort,
        event_publisher: EventPublisher,
    ) -> None:
        """初始化用例

        Args:
            tool_registry: 工具注册服务端口
            execution_service: 工具执行服务端口
            skill_loader: 技能加载器端口
            event_publisher: 事件发布器端口
        """
        self._registry = tool_registry
        self._execution = execution_service
        self._skill_loader = skill_loader
        self._event_publisher = event_publisher

    async def execute(self, request: StrategicAnalysisRequest) -> ToolResult:
        """执行战略分析用例

        Args:
            request: 战略分析请求

        Returns:
            ToolResult 执行结果
        """
        # 1. 通过 tool_name 查询 Tool 元数据
        try:
            tool = self._registry.get_tool(tool_name=request.tool_name)
        except ToolNotFoundError:
            logger.warning("工具不存在: tool_name=%s", request.tool_name)
            raise
        if tool is None:
            # 仓储端口契约：get_tool 在工具不存在时返回 None，由应用层转换为 ToolNotFoundError
            raise ToolNotFoundError(tool_name=request.tool_name)

        # 2. 通过 SkillLoaderPort 加载技能元数据（L1/L2）
        # 注：L1/L2 加载可能失败，但不应阻断执行链路（可选增强）
        try:
            await self._skill_loader.load_metadata(request.tool_name)
        except Exception as exc:
            logger.warning(
                "技能元数据加载失败（不阻断执行）: tool_name=%s exc=%s",
                request.tool_name,
                exc,
            )

        # 3. 构造 ExecutionContext + ToolCall
        context = ExecutionContext(
            tenant_id=tool.tool_id,  # 简化：用 tool_id 作为 tenant_id 占位
            user_id=request.user_id,
            session_id=request.session_id,
            trace_id=request.trace_id,
            timeout_sec=60.0,
        )
        tool_call = ToolCall(
            tool_id=tool.tool_id,
            arguments=request.arguments,
            tenant_id=context.tenant_id,
        )

        # 4. 委托 ToolExecutionService 执行五阶段工作流
        result = await self._execution.execute(
            tool_id=tool.tool_id,
            tool_call=tool_call,
            context=context,
        )

        # 5. 发布 ToolExecuted 事件（双通道：realtime + reliable）
        await self._publish_tool_executed_event(tool, request, result)

        return result

    async def _publish_tool_executed_event(
        self,
        tool: Tool,
        request: StrategicAnalysisRequest,
        result: ToolResult,
    ) -> None:
        """发布 ToolExecuted 事件

        Args:
            tool: Tool 实体
            request: 战略分析请求
            result: 执行结果
        """
        event = ToolExecuted(
            execution_id=uuid.uuid4(),  # 占位：实际应使用 execution.evidence_package 关联的 ID
            tool_id=tool.tool_id,
            tool_version=tool.version,
            execution_result={
                "status": result.status.value,
                "output": result.output,
                "evidence": (
                    {
                        "input_hash": result.evidence_package.input_hash,
                        "rule_version": result.evidence_package.rule_version,
                        "confidence": result.evidence_package.confidence,
                    }
                    if result.evidence_package
                    else None
                ),
            },
            cost_audit={
                "started_at": result.started_at.isoformat(),
                "completed_at": result.completed_at.isoformat(),
            },
        )
        try:
            await self._event_publisher.publish(event)
            logger.info(
                "ToolExecuted 事件发布成功: execution_id=%s tool_id=%s",
                event.execution_id,
                tool.tool_id,
            )
        except Exception as exc:
            logger.error(
                "ToolExecuted 事件发布失败: execution_id=%s exc=%s",
                event.execution_id,
                exc,
            )
            # 事件发布失败不阻断主流程


__all__ = ["StrategicAnalysisUseCase", "StrategicAnalysisRequest"]
