"""领域层语义路由协议模块

定义语义路由适配器的接口协议
基础设施层实现此协议以完成智能任务路由
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SemanticRouterProtocol(Protocol):
    """语义路由协议（由基础设施层实现）

    基于任务上下文与可用目标之间的语义相似度匹配进行路由
    """

    async def route(self, task_context: dict[str, Any]) -> tuple[str, float]:
        """基于任务上下文的语义相似度进行路由

        Args:
            task_context: 任务上下文字典

        Returns:
            (目标 ID, 相似度分数) 元组
        """
        ...
