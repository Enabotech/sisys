"""应用层工具执行引擎端口（Protocol）

定义 ToolExecutionEnginePort 协议，供 composition_root.py 注册使用。
实现位于 src/application/services/tool_execution_engine.py。

设计依据：Story 4.1a AC-7 端口注册规范
- 所有端口必须使用 Protocol 作为 interface 参数
- 遵循 Port/Adapter 模式，实现与抽象解耦
"""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from src.domain.entities.tool import Tool
from src.domain.value_objects.tool_execution import (
    ExecutionContext,
    ToolCall,
    ToolResult,
)


@runtime_checkable
class ToolExecutionEnginePort(Protocol):
    """工具执行引擎端口（五阶段工作流）

    实现位于 src/application/services/tool_execution_engine.py

    五阶段工作流：
    - Think: LLMClientPort.structured_generate
    - Code: LLMClientPort.structured_generate
    - Execute: SandboxExecutor.execute_code
    - Observe: SandboxExecutor.execute_code
    - Validate: LLMClientPort.structured_generate
    """

    async def execute(
        self,
        tool_id: uuid.UUID,
        tool: Tool,
        tool_call: ToolCall,
        context: ExecutionContext,
    ) -> ToolResult:
        """执行工具五阶段工作流

        Args:
            tool_id: 工具 ID
            tool: 工具实体（含元数据）
            tool_call: 工具调用请求（含 arguments）
            context: 执行上下文（含 tenant_id, user_id, session_id 等）

        Returns:
            ToolResult: 工具执行结果

        Raises:
            ToolExecutionFailedError: 五阶段任一阶段失败（不可重试）
            ToolExecutionRetryExhaustedError: 重试 3 次后仍失败
            ToolExecutionTimeoutError: 执行超过 max_total_duration_sec
        """
