"""Typer 命令面共享 dispatch（Story 7-1——AC-3 dispatch 矩阵 + 三参数短路）。

四路分发（优先级钦定 ``--dry-run`` > ``--mock`` > 缺省/json|table）：

    - ``--dry-run`` → ``controller(dry_run=True)``（守卫在 controller 内先于
      分叉执行——OD-12 短路层结构：守卫后、bootstrap 前分叉）+ 动作清单渲染
      （遵循 --format：json=data.actions 数组 / pretty=清单文本 / table=表）
    - ``--mock`` → ``controller(dry_run=True)`` 过守卫后丢弃清单，输出
      ``"mock": true`` 信封 + echo 参数回显（非法参数 242 exit 1 非 0）
    - 缺省（pretty）→ ``pretty_shell`` 薄壳直调（整合命令=``_run_*_cli``
      既有形态——零回归结构保证）
    - ``--format json|table`` → ``controller(dry_run=False)`` 返回 result →
      formatter 渲染（**禁经 ``_print_*``**——OD-14 stdout 纯净机制）

守卫失败照常 ``[EXCEPTION_code] message`` stderr + exit 1（dry-run/mock
均不豁免守卫报错——「exit 0」仅守卫通过的短路成功路径）。
"""

from __future__ import annotations

import logging
import sys
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, redirect_stdout
from dataclasses import dataclass
from typing import Any

import typer

from src.domain.exceptions import DomainError
from src.interfaces.cli.formatters import build_envelope, format_result, render_json

logger = logging.getLogger(__name__)

# 组装期注入钩子（cli_main.get_app 组装时注入 agent_cli 既有函数——interfaces
# 层禁 import entrypoints/composition_root（OD-16 传导链），bootstrap/关池经
# 依赖注入方向 entrypoints→interfaces 合法传递）
_bootstrap_hook: Callable[[], None] | None = None
_cleanup_hook: Callable[[], Any] | None = None


def set_bootstrap_hook(hook: Callable[[], None] | None) -> None:
    """注册 bootstrap 钩子（组装期注入——幂等守卫形态函数）。

    Args:
        hook: bootstrap 幂等函数（如 agent_cli._ensure_bootstrapped——registry
            已填充即短路）；None 清除（测试隔离）
    """
    global _bootstrap_hook
    _bootstrap_hook = hook


def set_cleanup_hook(hook: Callable[[], Any] | None) -> None:
    """注册连接池清理钩子（组装期注入——async 协程工厂）。

    Args:
        hook: 关池协程工厂（如 agent_cli._close_connection_pools——peek 语义
            不触发惰性实例化）；None 清除（测试隔离）
    """
    global _cleanup_hook
    _cleanup_hook = hook


def _ensure_bootstrap() -> None:
    """经注入钩子执行幂等 bootstrap（未注入时零动作——独立命令模块可自管）。"""
    if _bootstrap_hook is not None:
        _bootstrap_hook()


_session_scope_factory: Callable[[], Any] | None = None


def set_session_scope_factory(factory: Callable[[], Any] | None) -> None:
    """注册会话作用域工厂（组装期注入——async context manager 工厂）。

    请求路径仓储（document_repository 等硬要求 ContextVar session 的端口
    实现）在 CLI 无中间件形态下经本作用域供给会话；None 清除（测试隔离）。

    Args:
        factory: 零参 callable 返回 async context manager（如
            ``lambda: session_context(resolve("session_factory"))``）
    """
    global _session_scope_factory
    _session_scope_factory = factory


@asynccontextmanager
async def cli_session_scope() -> AsyncIterator[None]:
    """CLI 命令会话作用域（注入存在时供给 session；缺省零动作直通）。

    document upload/version 等请求路径仓储命令的异步内核包裹本作用域；
    统一入口组装期注入真实工厂，独立模块/未注入形态直通零副作用。
    """
    if _session_scope_factory is None:
        yield
        return
    async with _session_scope_factory():
        yield


def _run_cleanup() -> None:
    """兼容占位（外层关池废弃——asyncio.run 新 loop 关旧 loop 池必跨循环）。

    关池责任在 controller 异步内核协程内（``run_cleanup_async``——与业务
    同 loop，agent_cli 内核 finally 同款模式）；本函数保留空实现防外部引用。
    """
    return


async def run_cleanup_async() -> None:
    """协程内关池（controller 异步内核 finally 调用——与业务同 loop）。

    经注入钩子关闭已实例化连接池（peek 语义不触发惰性实例化）；失败仅记
    日志不反噬主结果（agent_cli _close_connection_pools 同款防御面）。
    """
    if _cleanup_hook is None:
        return
    try:
        await _cleanup_hook()
    except Exception as error:  # 清理失败不反噬主结果（agent_cli 先例防御面）
        logger.warning("连接池清理失败（忽略，不影响主结果）: %s: %s", type(error).__name__, error)


@dataclass
class CommandSpec:
    """命令规格（dispatch 输入——守卫内聚于 controller 首段）。

    Attributes:
        command: 命令全名（信封构造——如 "sisys checkpoint list"）
        controller: controller 函数 ``controller(dry_run: bool)``——dry_run=True
            返回 ``list[str]`` 动作清单（守卫先执行）；False 返回执行 result
        pretty_shell: 缺省态薄壳（整合命令=``_run_*_cli``；新命令=自有实现）
            返回 int 退出码
        mock_echo: mock 模式参数回显构造器（文件类参数含存在性预检提示）
        fmt: 输出格式（json/table/pretty——缺省 pretty）
        to_view: json/table 态 result→data 视图转换（Task 0.3 白名单；缺省
            dict 直传或 str 包装）
    """

    command: str
    controller: Callable[[bool], Any]
    pretty_shell: Callable[[], int]
    mock_echo: Callable[[], dict[str, Any]]
    fmt: str = "pretty"
    to_view: Callable[[Any], dict[str, Any]] | None = None


def dispatch_cli_command(spec: CommandSpec, *, dry_run: bool, mock: bool, yes: bool = False) -> int:
    """四路分发（--dry-run > --mock > 缺省/json|table——三参数优先级钦定）。

    Args:
        spec: 命令规格（controller/pretty_shell/mock_echo/fmt 四件）
        dry_run: --dry-run 旗标（client 语义——零 resolve 零副作用）
        mock: --mock 旗标（模拟信封）
        yes: --yes 旗标（确认门——dispatch 层透传，controller 内消费分叉；
            无门命令幂等接受）

    Returns:
        退出码（0=成功/短路成功，1=守卫或业务异常——DomainError 定式）
    """
    try:
        if dry_run:
            actions = _as_action_list(spec.controller(True))
            print(_render_actions(actions, spec.command, spec.fmt))
            return 0
        if mock:
            spec.controller(True)  # 先过守卫（丢弃动作清单——零 resolve 前提）
            envelope = build_envelope(command=spec.command, data={}, mock=True, echo=spec.mock_echo())
            print(render_json(envelope))
            return 0
        if spec.fmt in ("json", "table"):
            _ensure_bootstrap()
            try:
                # stdout 纯净机制：controller 执行期第三方库的 stdout 污染
                # （LiteLLM provider 错误横幅等）重定向到 stderr——json 态
                # stdout 仅含信封（AC-2 pipe 消费契约）
                with redirect_stdout(sys.stderr):
                    result = spec.controller(False)
                data = (
                    spec.to_view(result)
                    if spec.to_view is not None
                    else (result if isinstance(result, dict) else {"result": str(result)})
                )
                print(format_result(spec.fmt, command=spec.command, data=data))
                return 0
            finally:
                _run_cleanup()
        _ensure_bootstrap()  # pretty 态同样前置（新命令 controller 无自带 bootstrap——子进程无 conftest 掩蔽形态实测暴露）
        try:
            exit_code = spec.pretty_shell()
        finally:
            _run_cleanup()
        return exit_code
    except DomainError as error:
        logger.error("%s 失败: %s", spec.command, error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1
    except Exception as error:  # CLI 兜底层（agent_cli 双层定式——logger 记录全栈）
        logger.error("%s 异常: %s", spec.command, error, exc_info=True)
        return 1


def invoke_command(spec: CommandSpec, *, dry_run: bool, mock: bool, yes: bool = False) -> None:
    """Typer 命令函数适配器（dispatch 返回 int → typer.Exit 退出码语义）。

    Typer/click 约定命令函数返回 None（返回 int 会被视为意外形态 exit 2）；
    本包装把 dispatch 的 int 退出码转 ``typer.Exit``（cli_main.main 已 catch
    转 int——standalone_mode=False 契约兼容）。

    Args:
        spec: 命令规格
        dry_run: --dry-run 旗标
        mock: --mock 旗标
        yes: --yes 旗标
    """
    exit_code = dispatch_cli_command(spec, dry_run=dry_run, mock=mock, yes=yes)
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


def _as_action_list(controller_result: Any) -> list[str]:
    """controller(dry_run=True) 产物归一为动作清单（list[str]——防御形态）。"""
    if isinstance(controller_result, list):
        return [str(item) for item in controller_result]
    return [str(controller_result)]


def _render_actions(actions: list[str], command: str, fmt: str) -> str:
    """动作清单渲染（遵循 --format 三态——AC-3 钦定）。

    json=data.actions 数组；pretty=「将执行动作」多行文本；table=序号动作表。
    """
    if fmt == "json":
        return render_json(build_envelope(command=command, data={"actions": actions}))
    if fmt == "table":
        rows = [{"no": index, "action": text} for index, text in enumerate(actions, start=1)]
        return format_result("table", command=command, data={"actions": rows})
    lines = ["将执行以下动作（--dry-run 零服务调用）:"]
    lines.extend(f"  {index}. {text}" for index, text in enumerate(actions, start=1))
    return "\n".join(lines)
