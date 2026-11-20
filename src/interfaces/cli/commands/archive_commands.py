"""archive 命令组（query）

typer 命令定义层；编排与端口消费归 ``controllers/archive_controller.py``
（canonical 归一 → ``blm_chain_trace_use_case`` 查询）。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import typer

from src.interfaces.cli import _params
from src.interfaces.cli._guards import canonical_uuid
from src.interfaces.cli.controllers.archive_controller import PORT_NAME, run_query
from src.interfaces.cli.controllers.base import CommandContext, execute_command


def build_app(resolve: Callable[[str], Any]) -> typer.Typer:
    """构造 archive 命令组（挂载 query 命令——12 命令冻结矩阵）。

    Args:
        resolve: 端口解析函数（工厂注入）

    Returns:
        archive 模块 typer.Typer 子应用
    """
    archive_app = typer.Typer(help="决策归档（query 链路追溯查询）")

    @archive_app.command("query")
    def query(
        plan_id: str = typer.Option(..., "--plan-id", help="计划标识（UUID）"),
        yes: _params.YesOption = False,
        dry_run: _params.DryRunOption = False,
        mock: _params.MockOption = False,
        fmt: _params.FormatOption = _params.OutputFormat.TABLE,
    ) -> int:
        """查询计划决策归档链路（fallback find 读路径）。"""
        normalized = canonical_uuid(plan_id, field="plan_id")
        ctx = CommandContext(
            command="archive query",
            port_name=PORT_NAME,
            parameters={"plan_id": normalized},
            fmt=fmt.value,
            dry_run=dry_run,
            mock=mock,
            yes=yes,
        )
        return execute_command(ctx, resolve, lambda r: run_query(plan_id=normalized, fmt=fmt.value, resolve=r))

    return archive_app
