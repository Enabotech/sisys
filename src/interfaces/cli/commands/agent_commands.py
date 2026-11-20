"""agent 命令组（run）

typer 命令定义层；编排与端口消费归 ``controllers/agent_controller.py``
（OD-9：<agent-id> 位置参数 UUID——201 守卫族）。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import typer

from src.interfaces.cli import _params
from src.interfaces.cli.controllers.agent_controller import PORT_NAME, run_agent_workflow
from src.interfaces.cli.controllers.base import CommandContext, ensure_session, execute_command, to_decimal


def build_app(resolve: Callable[[str], Any]) -> typer.Typer:
    """构造 agent 命令组（挂载 run 命令——12 命令冻结矩阵）。

    Args:
        resolve: 端口解析函数（工厂注入）

    Returns:
        agent 模块 typer.Typer 子应用
    """
    agent_app = typer.Typer(help="Agent 协作（run 运行工作流）")

    @agent_app.command("run")
    def run(
        agent_id: str = typer.Argument(..., help="Agent 实例标识（instantiate 产出的 UUID）"),
        task: str = typer.Option(..., "--task", help="任务描述原文"),
        yes: _params.YesOption = False,
        dry_run: _params.DryRunOption = False,
        mock: _params.MockOption = False,
        fmt: _params.FormatOption = _params.OutputFormat.TABLE,
        session: _params.SessionOption = "",
        timeout: _params.TimeoutOption = 300,
        cost_budget: _params.CostBudgetOption = None,
    ) -> int:
        """执行单 Agent 标准工作流（守卫 → 编排执行 → 结果渲染）。"""
        from src.interfaces.cli._guards import parse_agent_uuid

        normalized_agent_id = str(parse_agent_uuid(agent_id))
        ctx = CommandContext(
            command="agent run",
            port_name=PORT_NAME,
            parameters={"agent_id": normalized_agent_id, "task": task, "timeout": timeout},
            fmt=fmt.value,
            dry_run=dry_run,
            mock=mock,
            yes=yes,
            cost_budget=to_decimal(cost_budget),
            session=ensure_session(session),
        )
        return execute_command(
            ctx,
            resolve,
            lambda r: run_agent_workflow(normalized_agent_id, task=task, fmt=fmt.value, resolve=r),
        )

    return agent_app
