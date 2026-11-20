"""控制器共享执行基建

短路执行器（DC-5 优先级契约）：守卫前置 → ``--dry-run`` 最外层短路（静态
``PORT_NAME`` 渲染+参数预览，不 resolve——与「不 bootstrap」自洽，R1-F5）→
``--mock`` 次层短路（冻结 DTO 四键）→ 真实执行委派命令特化 runner。

DomainError 不在本层捕获（守卫异常向上传播，stderr 呈现与退出码映射归
``main_cli.main`` 统一出口）。
"""

from __future__ import annotations

import uuid as uuid_module
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from src.interfaces.cli._guards import require_agent_budget
from src.interfaces.cli.formatters import get_formatter


def ensure_session(session: str) -> str:
    """会话标识缺省自动生成 UUID（R2-4：缺省生成入 Mock DTO session 字段）。"""
    return session or str(uuid_module.uuid4())


def to_decimal(cost_budget: str | None) -> Decimal | None:
    """cost_budget 字符串转 Decimal（typer 不支持 Decimal 注解——controller 归一层转换）。"""
    return Decimal(cost_budget) if cost_budget is not None else None


@dataclass(frozen=True)
class CommandContext:
    """命令执行上下文值对象（全局参数归一后形态+命令定位信息）。

    Args:
        command: 命令名（如 "document upload"）
        port_name: 消费端口注册名（controller 静态 ``PORT_NAME`` 常量来源——R1-F5）
        parameters: 命令参数归一后形态（UUID 归一/金额 Decimal/超时 int）
        fmt: 输出格式（json/table/pretty）
        dry_run: 预览模式开关
        mock: Mock 响应模式开关
        yes: Agent 模式开关
        cost_budget: 成本预算（Agent 模式必填）
        session: 会话标识（缺省自动生成 UUID）
    """

    command: str
    port_name: str
    parameters: dict[str, Any] = field(default_factory=dict)
    fmt: str = "table"
    dry_run: bool = False
    mock: bool = False
    yes: bool = False
    cost_budget: Decimal | None = None
    session: str = ""

    def to_mock_payload(self) -> dict[str, Any]:
        """Mock DTO 冻结形态（数据模型契约：mock/command/parameters/session 四键）。"""
        return {"mock": True, "command": self.command, "parameters": self.parameters, "session": self.session}

    def to_dry_run_payload(self) -> dict[str, Any]:
        """预览载荷（命令定位+静态端口名+归一后参数——AC-3 契约）。"""
        return {"command": self.command, "port": self.port_name, "parameters": self.parameters}


def execute_command(
    ctx: CommandContext,
    resolve: Callable[[str], Any],
    real_runner: Callable[[Callable[[str], Any]], int],
) -> int:
    """执行命令（守卫 → dry-run 短路 → mock 短路 → 真实执行）。

    Args:
        ctx: 命令执行上下文（归一后参数+短路开关）
        resolve: 端口解析函数（仅真实执行面消费）
        real_runner: 命令特化真实执行器（消费 resolve，返回退出码）

    Returns:
        退出码（0=成功含短路；DomainError 向上传播由入口统一映射）

    Raises:
        ValidationError: EXCEPTION_201——``--yes`` 缺 ``--cost-budget``（守卫先于短路）
    """
    require_agent_budget(yes=ctx.yes, cost_budget=ctx.cost_budget)
    renderer = get_formatter(ctx.fmt)
    if ctx.dry_run:  # --dry-run 最外层短路（--mock 同给时优先——R1-21/R2-8）
        print(renderer(ctx.to_dry_run_payload()))
        return 0
    if ctx.mock:
        print(renderer(ctx.to_mock_payload()))
        return 0
    return real_runner(resolve)
