"""CLI 控制器包

六控制器（document/tool/agent/plan/checkpoint/archive）——命令对象+
translator+编排+静态 ``PORT_NAME`` 常量+DomainError 传播（呈现归
``main_cli.main`` 统一出口）。base 承载共享短路执行基建。
"""

from src.interfaces.cli.controllers.base import CommandContext, execute_command

__all__ = ["CommandContext", "execute_command"]
