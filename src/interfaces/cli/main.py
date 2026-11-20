"""CLI 主入口工厂（create_cli_app）

统一 ``sisys`` 入口的 typer 应用工厂（DC-2）：``resolve`` 函数由
``src/entrypoints/main_cli.py`` 组装层注入，interfaces 层零组合根知识
（importlinter 传导禁令合规）。

六模块命令组挂载形态（R3-4）：工厂内联六模块空 Typer 骨架组（``--help``
自描述即可达挂载断言），Task 3-6 逐组以 ``commands/`` 包实现替换骨架。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import typer

_APP_HELP = "SISYS 战略规划与决策智能平台统一入口（document/tool/agent/plan/checkpoint/archive 六模块）"

# 骨架态命令组注册表（六模块已全部由 commands/ 包实现替换——12 命令冻结矩阵就位，R3-4 收官）
_MODULE_GROUPS: dict[str, str] = {}


def _print_version(value: bool) -> None:
    """--version 选项回调（R3-6 豁免边界：顶层前置形态无尾置可达性问题）。"""
    if value:
        from importlib.metadata import version

        try:
            package_version = version("sisys")
        except Exception:  # 元数据缺失（开发形态）回退占位——版本可观测优先
            package_version = "0.0.0+dev"
        typer.echo(f"sisys version {package_version}")
        raise typer.Exit


def create_cli_app(resolve: Callable[[str], Any]) -> typer.Typer:
    """构造统一 CLI 应用（六模块命令组挂载+--version 顶层选项）。

    Args:
        resolve: 端口解析函数（由入口组装层注入——懒 bootstrap 包装或测试 stub）

    Returns:
        typer.Typer 应用实例（--help 自描述三级命令结构）
    """

    def _root(
        version: bool = typer.Option(None, "--version", callback=_print_version, is_eager=True, help="显示版本号"),
    ) -> None:
        """SISYS 统一入口（sisys <service> <resource> <action> 三级命令结构）。"""

    app = typer.Typer(help=_APP_HELP, no_args_is_help=True, invoke_without_command=True)
    app.callback()(_root)
    from src.interfaces.cli.commands.agent_commands import build_app as build_agent_app
    from src.interfaces.cli.commands.archive_commands import build_app as build_archive_app
    from src.interfaces.cli.commands.checkpoint_commands import build_app as build_checkpoint_app
    from src.interfaces.cli.commands.document_commands import build_app as build_document_app
    from src.interfaces.cli.commands.planning_commands import build_app as build_plan_app
    from src.interfaces.cli.commands.tool_commands import build_app as build_tool_app

    app.add_typer(build_document_app(resolve), name="document")
    app.add_typer(build_tool_app(resolve), name="tool")
    app.add_typer(build_agent_app(resolve), name="agent")
    app.add_typer(build_plan_app(resolve), name="plan")
    app.add_typer(build_checkpoint_app(resolve), name="checkpoint")
    app.add_typer(build_archive_app(resolve), name="archive")
    for module_name, module_help in _MODULE_GROUPS.items():
        app.add_typer(typer.Typer(help=module_help), name=module_name)
    return app
