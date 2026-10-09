"""应用层 Validation Feedback 服务端口模块（Story 4.7 AC-2/AC-3）

定义 ValidationFeedbackServicePort——反馈闭环编排端口（recover 单方法）。

注入形态（SSOT 定稿——R9-14 双句柄）：
- llm_client：修复建议生成（fix-gen）
- error_case_repository / evolution_log_repository：案例库与演进日志
- event_publisher：领域事件发布（fire-and-forget，None 时跳过）
- engine：裸引擎引用（防放大封顶/恢复 engine._retry 用——_retry 属性所在）
- inner_chain：重执行用完整内层链（SSD>TOV>Engine——绕过裸引擎会架空
  SSD 安全防护与 TOV 出参校验，389 闭环被静默架空）
- 不注入 RetryPolicy（fix-gen 重试封顶由服务内自建——防「按值恢复」陷阱）
"""

from __future__ import annotations

import uuid
from typing import Any, Protocol, runtime_checkable

from src.domain.value_objects.tool_execution import ToolResult

__all__ = ["ValidationFeedbackServicePort"]


@runtime_checkable
class ValidationFeedbackServicePort(Protocol):
    """Validation Feedback 闭环编排端口."""

    async def recover(
        self,
        tool_id: uuid.UUID,
        tool: Any,
        tool_call: Any,
        context: Any,
        trigger_error: Exception,
    ) -> ToolResult:
        """执行完整反馈闭环（提取→查询→修复→增强重试→演进日志→不可行标记/恢复事件）.

        Args:
            tool_id: 工具 ID
            tool: 工具实体
            tool_call: 工具调用值对象
            context: 执行上下文
            trigger_error: 触发异常（389 或 382-EXECUTION-cause∈ExecutionError 族；
                execution_id 幂等键取自其 context）

        Returns:
            闭环结果：恢复成功 → ToolResult(SUCCESS, retry_count=增强尝试次数)；
            耗尽 → ToolResult(INFEASIBLE, output 携带失败摘要)；
            幂等短路 → 合成结论（RECOVERED 携带 replayed 标记）

        Raises:
            Exception: 增强尝试中浮出不满足入环谓词的异常（中止直传）或
                3 attempt 全失败且根因均为 LLM 瞬时（直传原触发——决策 #17②）
        """
        ...
