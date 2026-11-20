"""checkpoint 命令组（list / show / recover）

typer 命令定义层；编排与端口消费归 ``controllers/checkpoint_controller.py``
（复合定位 :2508 预览 / :2536 执行面）。

参数形态（R3-3 勘正/OD-8）：show/recover 均为 ``--plan-id``+``--checkpoint-no``
复合定位（两参必填——R5 方案 a）；``--mode`` 值域 replay|override；
``--confirmed-by`` 缺省取 ``--session``（归一先于短路——R4-3）。
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import Any

import typer

from src.interfaces.cli import _params
from src.interfaces.cli._guards import canonical_uuid, require_agent_budget
from src.interfaces.cli.controllers.base import CommandContext, ensure_session, execute_command, to_decimal
from src.interfaces.cli.controllers.checkpoint_controller import (
    PORT_NAME_LIST,
    PORT_NAME_RECOVERY,
    PORT_NAME_RECOVERY_EXECUTE,
    run_list,
    run_recover,
    run_recovery_preview,
    run_show,
    validate_checkpoint_no,
)


class RecoveryModeChoice(str, Enum):
    """恢复模式值域（replay|override——typer choice 守卫，非法值 exit 2）。"""

    REPLAY = "replay"
    OVERRIDE = "override"


def build_app(resolve: Callable[[str], Any]) -> typer.Typer:
    """构造 checkpoint 命令组（挂载 list/show/recover 三命令——12 命令冻结矩阵）。

    Args:
        resolve: 端口解析函数（工厂注入）

    Returns:
        checkpoint 模块 typer.Typer 子应用
    """
    checkpoint_app = typer.Typer(help="检查点（list 清单 / show 详情 / recover 恢复）")

    @checkpoint_app.command("list")
    def list_checkpoints(
        plan_id: str = typer.Option(..., "--plan-id", help="计划标识（UUID）"),
        yes: _params.YesOption = False,
        dry_run: _params.DryRunOption = False,
        mock: _params.MockOption = False,
        fmt: _params.FormatOption = _params.OutputFormat.TABLE,
    ) -> int:
        """列出计划下全部检查点（canonical 归一命中）。"""
        normalized = canonical_uuid(plan_id, field="plan_id")
        ctx = CommandContext(
            command="checkpoint list",
            port_name=PORT_NAME_LIST,
            parameters={"plan_id": normalized},
            fmt=fmt.value,
            dry_run=dry_run,
            mock=mock,
            yes=yes,
        )
        return execute_command(ctx, resolve, lambda r: run_list(plan_id=normalized, fmt=fmt.value, resolve=r))

    @checkpoint_app.command("show")
    def show(
        plan_id: str = typer.Option(..., "--plan-id", help="计划标识（UUID）"),
        checkpoint_no: str = typer.Option(..., "--checkpoint-no", help="检查点编号（CP-N）"),
        yes: _params.YesOption = False,
        dry_run: _params.DryRunOption = False,
        mock: _params.MockOption = False,
        fmt: _params.FormatOption = _params.OutputFormat.TABLE,
    ) -> int:
        """查看检查点详情（复合定位预览视图）。"""
        normalized = canonical_uuid(plan_id, field="plan_id")
        normalized_no = validate_checkpoint_no(checkpoint_no)
        ctx = CommandContext(
            command="checkpoint show",
            port_name=PORT_NAME_RECOVERY,
            parameters={"plan_id": normalized, "checkpoint_no": normalized_no},
            fmt=fmt.value,
            dry_run=dry_run,
            mock=mock,
            yes=yes,
        )
        return execute_command(
            ctx, resolve, lambda r: run_show(plan_id=normalized, checkpoint_no=normalized_no, fmt=fmt.value, resolve=r)
        )

    @checkpoint_app.command("recover")
    def recover(
        plan_id: str = typer.Option(..., "--plan-id", help="计划标识（UUID）"),
        checkpoint_no: str = typer.Option(..., "--checkpoint-no", help="检查点编号（CP-N）"),
        mode: RecoveryModeChoice | None = typer.Option(None, "--mode", help="恢复模式（replay|override）"),
        confirmed_by: str = typer.Option("", "--confirmed-by", help="确认人标识（缺省取 --session）"),
        yes: _params.YesOption = False,
        dry_run: _params.DryRunOption = False,
        mock: _params.MockOption = False,
        fmt: _params.FormatOption = _params.OutputFormat.TABLE,
        session: _params.SessionOption = "",
        timeout: _params.TimeoutOption = 300,
        cost_budget: _params.CostBudgetOption = None,
    ) -> int:
        """执行检查点恢复（:2536 执行面——created_via=cli）。"""
        normalized = canonical_uuid(plan_id, field="plan_id")
        normalized_no = validate_checkpoint_no(checkpoint_no)
        mode_value = mode.value if mode is not None else ""
        effective_session = ensure_session(session)
        resolved_confirmed_by = confirmed_by or effective_session
        require_agent_budget(yes=yes, cost_budget=to_decimal(cost_budget))
        if dry_run:
            return run_recovery_preview(plan_id=normalized, checkpoint_no=normalized_no, fmt=fmt.value, resolve=resolve)
        recover_ctx = CommandContext(
            command="checkpoint recover",
            port_name=PORT_NAME_RECOVERY_EXECUTE,
            parameters={
                "plan_id": normalized,
                "checkpoint_no": normalized_no,
                "mode": mode_value,
                "confirmed_by": resolved_confirmed_by,
            },
            fmt=fmt.value,
            dry_run=dry_run,
            mock=mock,
            yes=yes,
            cost_budget=to_decimal(cost_budget),
            session=effective_session,
        )
        return execute_command(
            recover_ctx,
            resolve,
            lambda r: run_recover(
                plan_id=normalized,
                checkpoint_no=normalized_no,
                mode=mode_value,
                confirmed_by=resolved_confirmed_by,
                fmt=fmt.value,
                resolve=r,
            ),
        )

    return checkpoint_app
