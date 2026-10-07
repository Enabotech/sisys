"""应用层红蓝辩论服务端口模块

Story 4.5 — 单 Agent 多视角辩论的服务端口协议（唯一编排入口）。

对齐 ToolChainServicePort / SummaryGenerationServicePort 先例：
@runtime_checkable Protocol + 两方法（run_debate / get_debate_result）。
"""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from src.domain.value_objects.debate import DebateResult, DebateTopic
from src.domain.value_objects.tool_execution import ExecutionContext


@runtime_checkable
class RedBlueDebateServicePort(Protocol):
    """红蓝辩论服务端口协议（单 Agent 多视角 MVP）

    编排流程：双视角并发生成（gather）→ 分化度门控 → 风险视图合成 → 事件发布。
    """

    async def run_debate(self, topic: DebateTopic, context: ExecutionContext) -> DebateResult:
        """执行红蓝辩论（双视角并发 → 门控 → 合成 → 发布事件）

        Args:
            topic: 争议议题（含租户与背景）
            context: 执行上下文（会话/追踪）

        Returns:
            DebateResult 辩论结果（red/blue/risk_view 三段 + 质量 + 耗时）

        Raises:
            DebateGenerationError: 视角 LLM 生成失败（EXCEPTION_420）
            DebateSynthesisError: 风险视图合成失败（EXCEPTION_421）
            DebateLowDivergenceError: 红蓝重叠率 ≥ 0.95 分化不足（EXCEPTION_422）
            EntityValidationError: 结构化输出违反领域不变量时透传（EXCEPTION_242，
                session 已转 FAILED 落库——数据契约违反不包装为 420/421）
        """
        ...

    async def get_debate_result(self, debate_id: uuid.UUID) -> DebateResult | None:
        """按辩论会话 ID 查询结果（仅 COMPLETED 会话可重建）

        Args:
            debate_id: 辩论会话 ID

        Returns:
            DebateResult 重建结果；未知名 / 非 COMPLETED（含 FAILED）返回 None
        """
        ...


__all__ = ["RedBlueDebateServicePort"]
