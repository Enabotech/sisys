"""应用层 Validation Feedback 装饰器（Story 4.7 AC-2/AC-3）

ValidationFeedbackDecorator——装饰链最外层（VFD > SSD > TOV > Engine）：
捕获触发异常（389 / 382-EXECUTION-cause∈ExecutionError 族）委托
ValidationFeedbackService.recover；其余异常不捕获自然上浮（385/207/201/
410-413/398 等矩阵排除行——R8-4 九行）。

INFEASIBLE 结果转换语义：recover 返回 ToolResult(INFEASIBLE)（对外不抛
异常——ToolChain DAG 编排按 status 分支感知，决策 #3）。
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from src.application.ports.validation_feedback_service import ValidationFeedbackServicePort
from src.domain.exceptions import ToolExecutionFailedError, ToolResultValidationError

logger = logging.getLogger(__name__)

__all__ = ["ValidationFeedbackDecorator"]


class ValidationFeedbackDecorator:
    """装饰链最外层：触发判定（九行矩阵）+ 委托反馈闭环.

    Attributes:
        _wrapped: 内层链（SandboxSecurityDecorator > ToolOutputValidator > Engine）
        _feedback: 反馈闭环服务端口
    """

    def __init__(self, wrapped: Any, feedback_service: ValidationFeedbackServicePort) -> None:
        """初始化装饰器.

        Args:
            wrapped: 内层链（SSD>TOV>Engine 完整链）
            feedback_service: Validation Feedback 服务端口
        """
        self._wrapped = wrapped
        self._feedback = feedback_service

    async def execute(
        self,
        tool_id: uuid.UUID,
        tool: Any,
        tool_call: Any,
        context: Any,
    ) -> Any:
        """执行工具（内层链）并在触发异常时进入反馈闭环.

        Args:
            tool_id: 工具 ID
            tool: 工具实体
            tool_call: 工具调用值对象
            context: 执行上下文

        Returns:
            内层链结果（成功/INFEASIBLE 结果化——不抛 399）

        Raises:
            ToolExecutionFailedError: 382 且不满足入环谓词（cause∉族或
                SANDBOX_START——R8-4：infra/配置类故障修复不可归因）
            其他矩阵排除行异常: 不捕获自然上浮（385/207/201/410-413/398）
        """
        try:
            return await self._wrapped.execute(tool_id, tool, tool_call, context)
        except ToolResultValidationError as trigger:
            # 389 = OUTPUT 校验基础重试耗尽（Schema 违规 / LLM 瞬时两子路径）
            return await self._feedback.recover(
                tool_id=tool_id,
                tool=tool,
                tool_call=tool_call,
                context=context,
                trigger_error=trigger,
            )
        except ToolExecutionFailedError as trigger:
            # 382-EXECUTION 且 cause∈ExecutionError 族（313/316/317）——沙箱内
            # 代码缺陷（STDERR 主浮现形态）→ 委托闭环；cause∉族（LLMConfigError
            # 332 等兜底宽捕获混入形态）与 SANDBOX_START——infra/配置类故障
            # 修复不可归因，直传（R8-4 九行矩阵）
            # 谓词经端口调用（CR-R1-27 清偿——端口实现替换时判定跟随）
            if self._feedback.should_enter_feedback_loop(trigger):
                return await self._feedback.recover(
                    tool_id=tool_id,
                    tool=tool,
                    tool_call=tool_call,
                    context=context,
                    trigger_error=trigger,
                )
            logger.warning(
                "Validation Feedback 跳过（非代码缺陷形态）: stage=%s cause=%s",
                trigger.context.get("stage"),
                type(trigger.cause).__name__ if trigger.cause else None,
            )
            raise
        # 其余异常（385/207/201/410-413/398 等）：不捕获自然上浮；
        # mid-attempt 对称立法在 recover 内实现（R9-13）
