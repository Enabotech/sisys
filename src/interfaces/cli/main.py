"""Typer app 骨架（Story 7-1——interfaces 侧 CLI 总装配）。

仅挂载 document/tool/archive 三模块（新命令面——interfaces 合法层位）；
agent/plan/checkpoint 三组整合命令子 app 落 entrypoints/cli_commands.py
（OD-16 层位钦定），由 cli_main.get_app() 程序化注册到本 app——interfaces
侧禁 import entrypoints（传导链守卫）。
"""

from __future__ import annotations

import typer

from src.interfaces.cli.commands import archive_commands, document_commands, tool_commands

app = typer.Typer(
    name="sisys",
    help="SISYS 战略规划与决策智能平台——统一 CLI 入口（文档/工具/Agent/规划/Checkpoint/归档）",
    no_args_is_help=False,
)

app.add_typer(document_commands.app, name="document")
app.add_typer(tool_commands.app, name="tool")
app.add_typer(archive_commands.app, name="archive")
