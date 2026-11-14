"""整合命令 Typer 模块（Story 7-1——agent/plan/checkpoint 三组子 app，OD-16 层位）。

本模块承载 7 个整合命令的 Typer 前端（复用 agent_cli 既有执行函数——双前端
共享执行函数零回归铁律）。层位钦定（OD-16）：整合命令依赖 agent_cli
（entrypoints）的 controller/守卫/``_print_*``——若命令文件落 interfaces/cli/
commands 则 ``interfaces → entrypoints → composition_root → infrastructure``
传导链重触发 import-linter interfaces-no-infrastructure 契约（CI 必红），故
落 entrypoints 层（层内互引合法）。

命令面（Task 0.1 冻结表）：
    - agent：instantiate / run-task
    - plan：generate / report（--report-format 拆分——OD-13） / trace-tree
    - checkpoint：list / recover（裸跑评估保留 + --dry-run 全局短路——OD-12）

三参数与格式参数经共享 ``Annotated[typer.Option]`` 类型别名逐命令签名注入
（命令尾随位置生效——typer 0.24 venv 实证 callback 级尾随 exit 2）；四路
分发（--dry-run > --mock > 缺省 pretty / json|table）经 dispatch 注入层承载。
"""

from __future__ import annotations

import enum
from typing import Any

import typer

from src.entrypoints import agent_cli
from src.interfaces.cli.dispatch import CommandSpec, invoke_command
from src.interfaces.cli.formatters import DryRunOption, FormatOption, MockOption, OutputFormat, YesOption, enum_value

agent_app = typer.Typer(help="Agent 实例化与任务执行（instantiate / run-task）")


class TraceDepth(str, enum.Enum):
    """追溯深度值域枚举（1-4——R1-F10：typer Enum 注解解析层拒绝非数字/越域）。

    兼容入口 argparse ``choices=("1","2","3","4")`` 同构值域（exit 2 语义——
    agent_cli.py CLI 面越域守卫分工钦定）；str 混入兼容 controller 的
    ``int(depth)`` 转换与 str 注解。
    """

    D1 = "1"
    D2 = "2"
    D3 = "3"
    D4 = "4"


plan_app = typer.Typer(help="BLM 规划生成 / 报告导出 / 追溯树（generate / report / trace-tree）")

checkpoint_app = typer.Typer(help="Checkpoint 清单与恢复（list / recover）")


# ===================================================================
# agent 组（instantiate / run-task）
# ===================================================================


@agent_app.command("instantiate")
def agent_instantiate(
    role: str = typer.Option(..., "--role", help="Agent 角色（ceo/cto/cmo/cfo/coo/cho/aud）"),
    dry_run: DryRunOption = False,
    mock: MockOption = False,
    yes: YesOption = False,
    fmt: FormatOption = OutputFormat.PRETTY,
) -> None:
    """实例化 Agent（输出纯 agent_id——P1 机器可消费）。"""

    def _view(result: Any) -> dict[str, Any]:
        return {"agent_id": str(getattr(result, "agent_id", "")), "role": role}

    def _pretty_shell() -> int:
        """pretty 薄壳（幂等守卫形态——纯 agent_id 单行 stdout 同兼容出口定稿）。"""
        result = agent_cli._instantiate_controller(role)
        print(getattr(result, "agent_id"))
        return 0

    invoke_command(
        CommandSpec(
            command="sisys agent instantiate",
            controller=lambda dr: agent_cli._instantiate_controller(role, dry_run=dr),
            pretty_shell=_pretty_shell,
            mock_echo=lambda: {"role": role},
            fmt=fmt,
            to_view=_view,
        ),
        dry_run=dry_run,
        mock=mock,
        yes=yes,
    )


@agent_app.command("run-task")
def agent_run_task(
    agent_id: str = typer.Option(..., "--agent-id", help="Agent 标识（UUID）"),
    task: str = typer.Option(..., "--task", help="任务描述"),
    dry_run: DryRunOption = False,
    mock: MockOption = False,
    yes: YesOption = False,
    fmt: FormatOption = OutputFormat.PRETTY,
) -> None:
    """派发任务至 Agent 工作流（成功与失败完成态均 exit 0——status 可观测）。"""
    invoke_command(
        CommandSpec(
            command="sisys agent run-task",
            controller=lambda dr: agent_cli._task_controller(agent_id, task, dry_run=dr),
            pretty_shell=lambda: agent_cli._run_task_cli(agent_id, task),
            mock_echo=lambda: {"agent_id": agent_id, "task": task},
            fmt=fmt,
            to_view=lambda result: {
                "agent_id": agent_id,
                "workflow_status": str(getattr(result, "workflow_status", "")),
                "task": task,
            },
        ),
        dry_run=dry_run,
        mock=mock,
        yes=yes,
    )


# ===================================================================
# plan 组（generate / report / trace-tree）
# ===================================================================


@plan_app.command("generate")
def plan_generate(
    agent_id: str = typer.Option(..., "--agent-id", help="Agent 标识（UUID）"),
    task: str = typer.Option(..., "--task", help="规划任务描述"),
    plan_id: str | None = typer.Option(None, "--plan-id", help="规划任务标识（可选——缺省用例内新铸）"),
    dry_run: DryRunOption = False,
    mock: MockOption = False,
    yes: YesOption = False,
    fmt: FormatOption = OutputFormat.PRETTY,
) -> None:
    """执行 BLM 前两阶段规划（阻塞到终态——含部分降级完成态）。"""
    invoke_command(
        CommandSpec(
            command="sisys plan generate",
            controller=lambda dr: agent_cli._blm_plan_controller(agent_id, task, plan_id, dry_run=dr),
            pretty_shell=lambda: agent_cli._run_blm_plan_cli(agent_id, task, plan_id),
            mock_echo=lambda: {"agent_id": agent_id, "task": task, "plan_id": plan_id},
            fmt=fmt,
            to_view=lambda result: {
                "plan_id": str(getattr(result, "plan_id", "")),
                "degraded_steps": len(getattr(result, "degraded_steps", ()) or ()),
            },
        ),
        dry_run=dry_run,
        mock=mock,
        yes=yes,
    )


@plan_app.command("report")
def plan_report(
    plan_id: str = typer.Option(..., "--plan-id", help="规划任务标识（UUID）"),
    report_format: str = typer.Option("markdown", "--report-format", help="报告内容格式（markdown/pdf——OD-13 拆分）"),
    brand_template: str | None = typer.Option(None, "--brand-template", help="品牌模板名（仅 pdf 组合合法）"),
    dry_run: DryRunOption = False,
    mock: MockOption = False,
    yes: YesOption = False,
    fmt: FormatOption = OutputFormat.PRETTY,
) -> None:
    """生成战略报告（--report-format 内容格式与 --format 输出格式正交——OD-13）。"""
    invoke_command(
        CommandSpec(
            command="sisys plan report",
            controller=lambda dr: agent_cli._report_generate_controller(plan_id, report_format, brand_template, dry_run=dr),
            pretty_shell=lambda: agent_cli._run_report_generate_cli(plan_id, report_format, brand_template),
            mock_echo=lambda: {"plan_id": plan_id, "report_format": report_format, "brand_template": brand_template},
            fmt=fmt,
            to_view=lambda result: {
                "report_path": str(
                    getattr(result, "memory_id", None)
                    or getattr(result, "report_id", None)
                    or getattr(result, "object_key", "")
                ),
                "report_format": report_format,
                "plan_id": plan_id,
            },
        ),
        dry_run=dry_run,
        mock=mock,
        yes=yes,
    )


@plan_app.command("trace-tree")
def plan_trace_tree(
    plan_id: str = typer.Option(..., "--plan-id", help="规划任务标识（UUID）"),
    depth: TraceDepth = typer.Option(
        TraceDepth.D4,
        "--depth",
        help="追溯深度（结论→分析→切片→文档四层标签；缺省 4=全深度与兼容入口一致——R1-F5/F10）",
    ),
    stage: str | None = typer.Option(None, "--stage", help="阶段过滤（缺省全量展示）"),
    dry_run: DryRunOption = False,
    mock: MockOption = False,
    yes: YesOption = False,
    fmt: FormatOption = OutputFormat.PRETTY,
) -> None:
    """查询思维链追溯树（四层标签前缀+逐层缩进）。"""
    invoke_command(
        CommandSpec(
            command="sisys plan trace-tree",
            controller=lambda dr: agent_cli._trace_tree_controller(plan_id, depth, stage, dry_run=dr),
            pretty_shell=lambda: agent_cli._run_trace_tree_cli(plan_id, depth, stage),
            mock_echo=lambda: {"plan_id": plan_id, "depth": depth, "stage": stage},
            fmt=fmt,
            to_view=lambda result: {
                "plan_id": plan_id,
                "total": getattr(result, "total", 0),
                "build_degraded": bool(getattr(result, "build_degraded", False)),
            },
        ),
        dry_run=dry_run,
        mock=mock,
        yes=yes,
    )


# ===================================================================
# checkpoint 组（list / recover）
# ===================================================================


@checkpoint_app.command("list")
def checkpoint_list(
    plan_id: str = typer.Option(..., "--plan-id", help="规划任务标识（UUID）"),
    dry_run: DryRunOption = False,
    mock: MockOption = False,
    yes: YesOption = False,
    fmt: FormatOption = OutputFormat.PRETTY,
) -> None:
    """查询 Checkpoint 清单（两遍法动态列宽表格——空清单亦 exit 0）。"""
    invoke_command(
        CommandSpec(
            command="sisys checkpoint list",
            controller=lambda dr: agent_cli._checkpoint_list_controller(plan_id, dry_run=dr),
            pretty_shell=lambda: agent_cli._run_checkpoint_list_cli(plan_id),
            mock_echo=lambda: {"plan_id": plan_id},
            fmt=fmt,
            to_view=lambda result: {
                "plan_id": plan_id,
                "checkpoints": [
                    {
                        "checkpoint_no": str(getattr(item, "checkpoint_no", "")),
                        "stage": str(getattr(item, "stage_id", "")),
                        "completed": bool(getattr(item, "completed", False)),
                        "version": getattr(item, "state_version", 0),
                        "sync_status": str(getattr(item, "sync_status", "")),
                    }
                    for item in (result or [])
                ],
            },
        ),
        dry_run=dry_run,
        mock=mock,
        yes=yes,
    )


@checkpoint_app.command("recover")
def checkpoint_recover(
    plan_id: str = typer.Option(..., "--plan-id", help="规划任务标识（UUID）"),
    checkpoint_no: str = typer.Option(..., "--checkpoint-no", help="检查点编号"),
    correction_type: str | None = typer.Option(None, "--correction-type", help="修正类型（四参数成组）"),
    previous_value: str | None = typer.Option(None, "--previous-value", help="修正前值（四参数成组）"),
    new_value: str | None = typer.Option(None, "--new-value", help="修正新值（四参数成组）"),
    applied_by: str | None = typer.Option(None, "--applied-by", help="修正执行人（四参数成组）"),
    mode: str | None = typer.Option(None, "--mode", help="恢复模式（replay/override）"),
    yes: YesOption = False,
    confirmed_by: str | None = typer.Option(None, "--confirmed-by", help="审批人（--yes 执行必填）"),
    dry_run: DryRunOption = False,
    mock: MockOption = False,
    fmt: FormatOption = OutputFormat.PRETTY,
) -> None:
    """Checkpoint 恢复（缺省=影响评估模式；--yes=确认执行；--dry-run=快速回显零服务调用）。"""

    def _assessment_view(result: Any) -> dict[str, Any]:
        """评估态 data 视图（Task 0.3 白名单对表——R1-F7 收口）。

        view 对象字段：recommended_mode（RecoveryMode 枚举——enum_value 提取
        防 str() 泄漏类名）/subsequent_checkpoints（计数语义）。
        """
        return {
            "plan_id": plan_id,
            "checkpoint_no": checkpoint_no,
            "assessment": {
                "recommended_mode": enum_value(getattr(result, "recommended_mode", "") or ""),
                "subsequent_count": len(getattr(result, "subsequent_checkpoints", []) or []),
            },
        }

    def _outcome_view(result: Any) -> dict[str, Any]:
        """执行态 data 视图（Task 0.3 白名单对表——R1-F7 收口）。

        outcome 对象字段：recovery_mode（RecoveryMode 枚举）/corrected/
        new_state_version/affected_checkpoints（计数语义）。
        """
        return {
            "plan_id": plan_id,
            "checkpoint_no": checkpoint_no,
            "recovery": {
                "mode": enum_value(getattr(result, "recovery_mode", "") or ""),
                "corrected": bool(getattr(result, "corrected", False)),
                "new_state_version": getattr(result, "new_state_version", 0),
                "affected_count": len(getattr(result, "affected_checkpoints", []) or []),
            },
        }

    invoke_command(
        CommandSpec(
            command="sisys checkpoint recover",
            controller=lambda dr: agent_cli._checkpoint_recover_controller(
                plan_id,
                checkpoint_no,
                correction_type,
                previous_value,
                new_value,
                applied_by,
                mode,
                yes,
                confirmed_by,
                dry_run=dr,
            ),
            pretty_shell=lambda: agent_cli._run_checkpoint_recover_cli(
                plan_id, checkpoint_no, correction_type, previous_value, new_value, applied_by, mode, yes, confirmed_by
            ),
            mock_echo=lambda: {"plan_id": plan_id, "checkpoint_no": checkpoint_no, "mode": mode},
            fmt=fmt,
            # confirm 位显式分叉（R1-F7 评审钦定——替代 hasattr 嗅探，双态字段名不重叠）
            to_view=lambda result: _outcome_view(result) if yes else _assessment_view(result),
        ),
        dry_run=dry_run,
        mock=mock,
        yes=yes,
    )
