"""agent 命令控制器

消费端口（AC-5 表）：``agent_workflow_use_case``（:3178——
``execute(agent_id: UUID, task)`` async）。

OD-9（端口签名现实层优先）：interface-design §4.3.3 钦定 ``<role>`` 位置
参数，但用例签名吃 instantiate 产出的实体 id（role 仅 Agent 实体属性，
无 role→agent 解析端口面）；落地为 ``agent run <agent-id>``（agent-id 族
201 守卫——存量 agent_cli run-task 同形态先例）；7-1-DF1 迁移专项复核。
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from src.interfaces.cli._guards import parse_agent_uuid
from src.interfaces.cli.formatters import get_formatter

PORT_NAME = "agent_workflow_use_case"


def run_agent_workflow(agent_id: str, *, task: str, fmt: str, resolve: Callable[[str], Any]) -> int:
    """真实执行单 Agent 工作流（agent-id 201 守卫 → execute → 结果渲染）。

    Args:
        agent_id: Agent 实例标识原始输入（UUID 守卫归一）
        task: 任务描述原文
        fmt: 输出格式
        resolve: 端口解析函数

    Returns:
        退出码（0=成功）
    """
    parsed_agent_id = parse_agent_uuid(agent_id)
    use_case = resolve(PORT_NAME)
    result = asyncio.run(use_case.execute(agent_id=parsed_agent_id, task=task))
    evidence = getattr(result, "evidence", None)
    payload = {
        "agent_id": str(getattr(result, "agent_id", parsed_agent_id)),
        "workflow_status": getattr(result, "workflow_status", None),
        "retry_count": getattr(result, "retry_count", None),
        "executed_phases": list(getattr(result, "executed_phases", ())),
        "confidence": getattr(evidence, "confidence", None) if evidence is not None else None,
    }
    print(get_formatter(fmt)(payload))
    return 0
