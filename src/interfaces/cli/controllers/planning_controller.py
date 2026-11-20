"""plan 命令控制器

消费端口（AC-5 表）：``blm_planning_use_case``（:3518——
``execute(agent_id, task, plan_id)`` 位置参数签名 async）。

双守卫族分工（异常表）：``--agent-id`` 201（agent-id 族——
``parse_agent_uuid`` 先例）/ ``--plan-id`` 242（实体 ID 族——
``canonical_uuid`` 归一守卫）。
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from src.interfaces.cli._guards import canonical_uuid, parse_agent_uuid
from src.interfaces.cli.formatters import get_formatter

PORT_NAME = "blm_planning_use_case"


def run_plan_generate(
    agent_id: str,
    *,
    task: str,
    plan_id: str,
    fmt: str,
    resolve: Callable[[str], Any],
) -> int:
    """真实执行 BLM 规划生成（双守卫归一 → execute → 结果渲染）。

    Args:
        agent_id: Agent 实体标识原始输入（201 守卫族）
        task: 规划任务描述
        plan_id: 计划标识（242 守卫族；空串为缺省——BLM 自生成）
        fmt: 输出格式
        resolve: 端口解析函数

    Returns:
        退出码（0=成功）
    """
    parsed_agent_id = parse_agent_uuid(agent_id)
    normalized_plan_id = canonical_uuid(plan_id, field="plan_id") if plan_id else None
    use_case = resolve(PORT_NAME)
    result = asyncio.run(use_case.execute(parsed_agent_id, task, normalized_plan_id))
    payload = {
        "plan_id": str(getattr(result, "plan_id", normalized_plan_id or "")),
        "status": getattr(result, "status", None),
        "stages_completed": getattr(result, "stages_completed", None),
    }
    print(get_formatter(fmt)(payload))
    return 0
