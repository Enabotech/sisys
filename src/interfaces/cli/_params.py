"""CLI 共享参数注解单一来源（R1-F1 P0 机制载体）

全局参数（``--yes/--dry-run/--mock/--format``）与 Agent 专用参数
（``--session/--timeout/--cost-budget``）经共享 ``Annotated`` 类型在各命令
签名逐一声明（typer 标准形态，前置/尾置形态均可解析）。

**禁止 ``@app.callback()`` 承载全局参数**——click group callback 参数在
子命令之后的尾置形态（如 ``sisys document upload --file x --yes``）实测
exit 2（typer 0.24.2/click 8.4.2）。豁免边界（R3-6）：``--version`` 顶层
选项经 ``app.callback(invoke_without_command=True)`` 承载（顶层前置形态
无尾置可达性问题）。

用法形态（typer 0.24.2 实测约束）：
- 注解仅含 ``--选项`` 声明与 help 元数据（``Option(default, ...)`` 位置
  默认值形态对 bool flag 实测崩坏），缺省值经命令签名 ``= 默认值`` 提供；
- ``--cost-budget`` 注解为 ``str | None``（typer 不支持 Decimal 注解），
  金额 ``Decimal`` 转换在 controller 参数归一层完成（命令对象归一语义）。
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

import typer


class OutputFormat(str, Enum):
    """三态输出格式值域（AC-4——typer Enum choice 守卫载体，非法值 exit 2）。"""

    JSON = "json"
    TABLE = "table"
    PRETTY = "pretty"


YesOption = Annotated[bool, typer.Option("--yes", help="Agent 模式开关（需显式提供 --cost-budget，缺失拒绝执行）")]
DryRunOption = Annotated[
    bool,
    typer.Option("--dry-run", help="预览模式：打印命令解析结果与将调用的用例端口名（不装配不执行）"),
]
MockOption = Annotated[bool, typer.Option("--mock", help="Mock 响应模式：短路返回结构化 mock DTO（不装配）")]
FormatOption = Annotated[OutputFormat, typer.Option("--format", help="输出格式（默认 table）", case_sensitive=False)]
SessionOption = Annotated[str, typer.Option("--session", help="会话标识（缺省自动生成 UUID）")]
TimeoutOption = Annotated[int, typer.Option("--timeout", help="超时秒数（默认 300）")]
CostBudgetOption = Annotated[str | None, typer.Option("--cost-budget", help="成本预算（Agent 模式 --yes 必填）")]

__all__ = [
    "CostBudgetOption",
    "DryRunOption",
    "FormatOption",
    "MockOption",
    "OutputFormat",
    "SessionOption",
    "TimeoutOption",
    "YesOption",
]
