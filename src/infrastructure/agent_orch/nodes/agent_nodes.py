"""基础设施层 Agent 节点函数模块

纯函数节点实现，不持有状态，不发布事件

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import Any

from src.infrastructure.agent_orch.schemas import BasicAgentState


def analysis_node(state: BasicAgentState) -> dict[str, Any]:
    """分析节点

    MVP 简化实现：直接设置分析结果。

    Args:
        state: 当前状态

    Returns:
        状态更新字典
    """
    return {"analysis_result": f"分析完成: {state.get('task_description', '')}"}


def synthesis_node(state: BasicAgentState) -> dict[str, Any]:
    """综合节点

    MVP 简化实现：直接设置综合结果。

    Args:
        state: 当前状态

    Returns:
        状态更新字典
    """
    analysis_result = state.get("analysis_result", "")
    return {"synthesis_result": f"综合完成: {analysis_result}"}
