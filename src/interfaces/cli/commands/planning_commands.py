"""plan 命令组（generate）

typer 命令定义层；编排与端口消费归 ``controllers/planning_controller.py``
（--agent-id 201 / --plan-id 242 双守卫族）。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import typer

from src.interfaces.cli import _params
from src.interfaces.cli.controllers.base import CommandContext, ensure_session, execute_command, to_decimal
from src.interfaces.cli.controllers.planning_controller import PORT_NAME, run_plan_generate


def build_app(resolve: Callable[[str], Any]) -> typer.Typer:
    """构造 plan 命令组（挂载 generate 命令——12 命令冻结矩阵）。

    Args:
        resolve: 端口解析函数（工厂注入）

    Returns:
        plan 模块 typer.Typer 子应用
    """
    plan_app = typer.Typer(help="战略规划（generate BLM 规划生成）")

    @plan_app.command("generate")
    def generate(
        agent_id: str = typer.Option(..., "--agent-id", help="Agent 实例标识（UUID）"),
        task: str = typer.Option(..., "--task", help="规划任务描述"),
        plan_id: str = typer.Option("", "--plan-id", help="计划标识（UUID，缺省自生成）"),
        yes: _params.YesOption = False,
        dry_run: _params.DryRunOption = False,
        mock: _params.MockOption = False,
        fmt: _params.FormatOption = _params.OutputFormat.TABLE,
        session: _params.SessionOption = "",
        timeout: _params.TimeoutOption = 300,
        cost_budget: _params.CostBudgetOption = None,
    ) -> int:
        """执行 BLM 战略规划生成（SP 全链编排）。"""
        from src.interfaces.cli._guards import canonical_uuid, parse_agent_uuid

        normalized_agent_id = str(parse_agent_uuid(agent_id))
        normalized_plan_id = canonical_uuid(plan_id, field="plan_id") if plan_id else ""
        ctx = CommandContext(
            command="plan generate",
            port_name=PORT_NAME,
            parameters={"agent_id": normalized_agent_id, "task": task, "plan_id": normalized_plan_id},
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
            lambda r: run_plan_generate(normalized_agent_id, task=task, plan_id=normalized_plan_id, fmt=fmt.value, resolve=r),
        )

    return plan_app
