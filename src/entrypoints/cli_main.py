"""sisys 统一 CLI 入口（Story 7-1——Epic 7 首站 FR-UI-01/FR-IF-01）

统一 Typer 入口（三级命令结构 ``sisys <service> <resource> <action>``——
interface-design §4.2 钦定）+ 兼容入口 ``sisys-agent`` 双前端共享执行函数
（OD-14 controller 抽取路径，argparse 解析层差异隔离在兼容入口）。

装配链（D1 方案 A + OD-16 层位钦定）::

    load_env（agent_cli 单函数复用——6.8-R1-DF1 核销，override=False +
    测试形态守卫）→ register_signal_handlers（SIGTERM/SIGINT 优雅退出——
    5-7 R1-DF6 核销）→ get_app（interfaces 三模块 + entrypoints 三组
    程序化注册 + dispatch 钩子注入）→ main（Typer 分发）

分层落位（OD-16）：
    - interfaces/cli/main.py：app 骨架，挂载 document/tool/archive 三模块
    - entrypoints/cli_commands.py：agent/plan/checkpoint 三组子 app（整合命令
      依赖 agent_cli 的 controller/守卫——entrypoints 层内互引合法）
    - cli_main 程序化注册两组并缓存（重复调用幂等）

用法:
    sisys --help                          # 六模块总览
    sisys document upload --file ...      # 三级命令
    python -m src.entrypoints.cli_main    # python -m 形态（__main__ 守卫）

退出码契约（与 agent_cli.main 同契约）: 0=成功，1=业务异常，2=用法错误；
信号中断=128+signum（POSIX 惯例——R1-F9：SIGINT=130/SIGTERM=143）。
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from typing import Any

import click
import typer

from src.domain.ports.resolver import get_resolver
from src.entrypoints.agent_cli import load_env
from src.infrastructure.storage.postgresql.session_context import session_context

logger = logging.getLogger(__name__)

# 组装缓存（get_app 幂等——重复调用不重复注册）
_assembled_app: typer.Typer | None = None


def get_app() -> typer.Typer:
    """组装完整 CLI app（interfaces 三模块 + entrypoints 三组——OD-16 层位）。

    interfaces 裸 app 仅含 document/tool/archive 三模块（新命令面——domain 层
    Resolver 先例合法方向）；agent/plan/checkpoint 三组整合命令子 app 落
    entrypoints/cli_commands.py（依赖 agent_cli 的 controller/守卫——interfaces
    侧 import agent_cli 会重触发 import-linter 传导链，故由本函数程序化注册）。
    首次组装后缓存（重复调用幂等——测试多次 get_app 不重复挂载）。

    Returns:
        组装完成的完整 Typer app（六模块全部挂载）
    """
    global _assembled_app
    if _assembled_app is not None:
        return _assembled_app
    from src.entrypoints import agent_cli, cli_commands
    from src.interfaces.cli import dispatch
    from src.interfaces.cli.main import app as interfaces_app

    interfaces_app.add_typer(cli_commands.agent_app, name="agent")
    interfaces_app.add_typer(cli_commands.plan_app, name="plan")
    interfaces_app.add_typer(cli_commands.checkpoint_app, name="checkpoint")
    # bootstrap/关池钩子注入（OD-16——interfaces 层禁 import entrypoints，
    # 经组装期依赖注入方向传递；agent_cli 既有函数钦定 import 复用非复制）
    dispatch.set_bootstrap_hook(agent_cli._ensure_bootstrapped)
    dispatch.set_cleanup_hook(agent_cli._close_connection_pools)
    # 会话作用域工厂注入（请求路径仓储——document_repository 等硬要求
    # ContextVar session 的端口实现在 CLI 无中间件形态下的 session 供给；
    # entrypoints import infrastructure 为设计使然——.importlinter:75 注记）
    dispatch.set_session_scope_factory(lambda: session_context(get_resolver().resolve("session_factory")))
    _assembled_app = interfaces_app
    return _assembled_app


def handle_termination_signal(signum: int, frame: Any) -> None:
    """SIGTERM/SIGINT 优雅退出 handler（5-7 R1-DF6 核销——OD-9 最小处置）。

    机制钦定：同步 handler 内 ①PhoenixTracer.shutdown() 同步 API 直调
    （phoenix_tracer.py:179——span flush；未激活 tracer 零动作）；②已实例化
    连接池关闭经 ``run_coroutine_threadsafe`` 调度至运行中 loop（关池协程
    尾部进程退出——handler 内同步等待会死锁：loop 与 handler 同主线程，
    loop 暂停期间调度协程不可执行）。无运行 loop（bootstrap 前信号）仅同步
    面 flush 后直退。退出码 ``128 + signum``（POSIX 惯例——SIGINT=130/
    SIGTERM=143，R1-F9：中断不再上报 exit 0 成功态）；退出前显式 flush
    stdout/stderr（``os._exit`` 跳过解释器缓冲刷盘——pipe 形态块缓冲下
    已 print 信封会丢）。**禁**组合根 shutdown() 复用（其连接池段用
    resolve 非 peek——退出路径惰性实例化副作用，亲验不合 OD-9 peek 语义，
    按故事钦定「不一致则独立调度」分支）。

    Args:
        signum: 信号编号（SIGTERM/SIGINT）
        frame: 当前栈帧（signal 惯例——本 handler 不消费）
    """
    try:
        tracer = get_resolver().peek_singleton("agent_tracing")
        if tracer is not None:
            tracer.shutdown()
    except Exception as error:  # 信号路径降级（flush 失败不阻断退出）
        logger.warning("信号路径 tracer 刷盘降级: %s: %s", type(error).__name__, error)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(128 + signum)  # 无运行 loop（bootstrap 前信号）——同步面已处理，按信号码直退
        return

    async def _graceful_exit() -> None:
        """关池协程（loop 恢复运行后执行——尾部按信号码进程退出）。"""
        from src.entrypoints.agent_cli import _close_connection_pools

        try:
            await _close_connection_pools()
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(128 + signum)

    asyncio.run_coroutine_threadsafe(_graceful_exit(), loop)


def register_signal_handlers() -> None:
    """注册 SIGTERM/SIGINT 优雅退出 handler（幂等——main() 每次调用重注册）。

    仅主线程可注册（signal.signal 惯例）；非主线程静默跳过；测试形态
    （SISYS_USE_TEST_PORTS=1）跳过——注册会劫持 pytest/xdist 的 worker 信号
    机制（worker 关闭 SIGTERM 触发 handler 的 os._exit 分支→execnet 挂起）。
    """
    import os

    if os.environ.get("SISYS_USE_TEST_PORTS") == "1":
        return  # 测试形态守卫（进程信号机制不可劫持）
    try:
        signal.signal(signal.SIGTERM, handle_termination_signal)
        signal.signal(signal.SIGINT, handle_termination_signal)
    except ValueError:
        logger.debug("非主线程跳过信号 handler 注册")


def main(argv: list[str] | None = None) -> int:
    """CLI 主入口（console_script 目标——返回 int 退出码契约）。

    load_env → 信号注册 → Typer 分发（standalone_mode=False 捕获命令返回值
    与用法错误——argparse 前端同契约）；--help 等 eager 选项返回 0。

    Args:
        argv: 命令行参数（默认 sys.argv[1:]）

    Returns:
        退出码（0=成功，1=业务异常，2=用法错误）
    """
    load_env()
    register_signal_handlers()
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    app = get_app()
    try:
        result = app(argv, standalone_mode=False)
        return result if isinstance(result, int) else 0
    except click.UsageError as error:
        error.show(file=sys.stderr)
        return 2
    except typer.Exit as error:
        return int(error.exit_code)
    except SystemExit as error:
        return int(error.code or 0)


if __name__ == "__main__":
    sys.exit(main())
