"""tool 命令组（list / schema / run / chain run）

typer 命令定义层；编排与端口消费归 ``controllers/tool_controller.py``
（slug→Tool.tool_id 解析链与 input_examples 通路在 controller）。
Agent 专用参数（--session/--timeout/--cost-budget）复用 ``_params.py``
共享注解（R2-A2：不另建 tool 侧注解）。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import typer

from src.interfaces.cli import _params
from src.interfaces.cli.controllers.base import CommandContext, ensure_session, execute_command, to_decimal
from src.interfaces.cli.controllers.tool_controller import (
    PORT_NAME,
    PORT_NAME_CHAIN,
    PORT_NAME_EXECUTION,
    load_chain_config,
    load_input_json,
    run_chain,
    run_list,
    run_schema,
    run_tool,
)


def build_app(resolve: Callable[[str], Any]) -> typer.Typer:
    """构造 tool 命令组（挂载 list/schema/run/chain run 四命令——12 命令冻结矩阵）。

    Args:
        resolve: 端口解析函数（工厂注入）

    Returns:
        tool 模块 typer.Typer 子应用
    """
    tool_app = typer.Typer(help="工具注册与执行（list 清单 / schema 结构 / run 执行 / chain run 链式）")

    @tool_app.command("list")
    def list_tools(
        category: str = typer.Option("", "--category", help="按域过滤（工具 category 字段）"),
        yes: _params.YesOption = False,
        dry_run: _params.DryRunOption = False,
        mock: _params.MockOption = False,
        fmt: _params.FormatOption = _params.OutputFormat.TABLE,
    ) -> int:
        """列出全部已注册工具（可选域过滤）。"""
        ctx = CommandContext(
            command="tool list",
            port_name=PORT_NAME,
            parameters={"category": category},
            fmt=fmt.value,
            dry_run=dry_run,
            mock=mock,
            yes=yes,
        )
        return execute_command(ctx, resolve, lambda r: run_list(category=category, fmt=fmt.value, resolve=r))

    @tool_app.command("schema")
    def schema(
        slug: str = typer.Argument(..., help="工具标识（TOOLS.md slug 形态，非 UUID）"),
        yes: _params.YesOption = False,
        dry_run: _params.DryRunOption = False,
        mock: _params.MockOption = False,
        fmt: _params.FormatOption = _params.OutputFormat.TABLE,
    ) -> int:
        """查询工具 schema（含 input_examples 输入示例——P7）。"""
        ctx = CommandContext(
            command="tool schema",
            port_name=PORT_NAME,
            parameters={"slug": slug},
            fmt=fmt.value,
            dry_run=dry_run,
            mock=mock,
            yes=yes,
        )
        return execute_command(ctx, resolve, lambda r: run_schema(slug, fmt=fmt.value, resolve=r))

    @tool_app.command("run")
    def run(
        slug: str = typer.Argument(..., help="工具标识（TOOLS.md slug 形态，非 UUID）"),
        input_json: str = typer.Option(..., "--input", help="工具参数（JSON 对象）"),
        yes: _params.YesOption = False,
        dry_run: _params.DryRunOption = False,
        mock: _params.MockOption = False,
        fmt: _params.FormatOption = _params.OutputFormat.TABLE,
        session: _params.SessionOption = "",
        timeout: _params.TimeoutOption = 300,
        cost_budget: _params.CostBudgetOption = None,
    ) -> int:
        """执行单工具调用（slug 解析→ToolCall→执行）。"""
        arguments = load_input_json(input_json)
        ctx = CommandContext(
            command="tool run",
            port_name=PORT_NAME_EXECUTION,
            parameters={"slug": slug, "arguments": arguments, "timeout": timeout},
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
            lambda r: run_tool(slug, arguments, session=ensure_session(session), timeout=timeout, fmt=fmt.value, resolve=r),
        )

    chain_app = typer.Typer(help="工具链执行（run）")
    tool_app.add_typer(chain_app, name="chain")

    @chain_app.command("run")
    def chain_run(
        chain_id: str = typer.Argument(..., help="工具链标识"),
        config: str = typer.Option(..., "--config", help="链参数（内联 JSON 或文件路径）"),
        yes: _params.YesOption = False,
        dry_run: _params.DryRunOption = False,
        mock: _params.MockOption = False,
        fmt: _params.FormatOption = _params.OutputFormat.TABLE,
        session: _params.SessionOption = "",
        timeout: _params.TimeoutOption = 300,
        cost_budget: _params.CostBudgetOption = None,
    ) -> int:
        """执行工具链（run_tool_chain_use_case）。"""
        parameters = load_chain_config(config)
        ctx = CommandContext(
            command="tool chain run",
            port_name=PORT_NAME_CHAIN,
            parameters={"chain_id": chain_id, "parameters": parameters, "timeout": timeout},
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
            lambda r: run_chain(
                chain_id, parameters, session=ensure_session(session), timeout=timeout, fmt=fmt.value, resolve=r
            ),
        )

    return tool_app
