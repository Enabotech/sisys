"""sisys 统一 CLI 进程入口（组装层——D1 方案 A）

入口五步（R3-5 钉死顺序）：

1. ``load_dotenv(ENV_FILE)`` —— **main() 函数体内、bootstrap 之前**（禁止
   模块级 import 副作用形态——pytest 收集期加载/monkeypatch 不可达/
   in-process 二次直调不再执行，顺序守卫断言形态崩坏）；
2. 懒 bootstrap —— 首次 ``_resolve_port`` 时 ``bootstrap()``（幂等守卫防
   ConflictError；``--dry-run``/``--mock``/``--help`` 零 resolve 路径不
   bootstrap——与「不 bootstrap」契约自洽）；
3. ``create_cli_app(resolve)`` 工厂装配（interfaces 层零组合根知识）；
4. ``app(argv, standalone_mode=False)`` 派发（命令函数返回值=int 退出码）；
5. 异常统一映射出口：DomainError → stderr ``[EXCEPTION_NNN] message`` +
   exit 1（agent_cli 逐字契约）；click UsageError / typer.Exit → 退出码
   直传（用法错误 exit 2）；成功 → 0。

模块级 ``main(argv: list[str] | None = None) -> int`` 包装（agent_cli:2623
同签名先例——in-process 直调拿返回值不触发 SystemExit，``sys.exit`` 仅在
``__main__`` 块）。
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# 仓库根 .env 模块常量（main_cli.py 位于 src/entrypoints/ 下两层——R2-11 钉死；
# 集成测试经 monkeypatch 该常量指向临时 .env 注入，不改仓库根 .env）
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

logger = logging.getLogger(__name__)

_BOOTSTRAPPED = False


def bootstrap() -> None:
    """组合根 bootstrap 延迟导入壳（模块级直引会使本模块 import 即触发重依赖加载）。"""
    from src.composition_root import bootstrap as _bootstrap

    _bootstrap()


def _registry_bootstrapped() -> bool:
    """组合根注册表已初始化探测（agent_cli _ensure_bootstrapped 幂等先例形态）。"""
    from src.domain.ports.registry import _global_registry

    return _global_registry.get("agent_workflow_use_case") is not None


def _ensure_bootstrapped() -> None:
    """懒 bootstrap（幂等：模块 flag 或注册表探测任一命中即跳过——防 ConflictError）。"""
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED or _registry_bootstrapped():
        return
    bootstrap()
    _BOOTSTRAPPED = True


def _resolve_port(name: str) -> Any:
    """懒 bootstrap 端口解析（首次调用时 bootstrap——幂等守卫）。"""
    _ensure_bootstrapped()
    from src.domain.ports.resolver import resolve

    return resolve(name)


def create_cli_app(resolve: Callable[[str], Any]) -> Any:
    """CLI 工厂延迟导入壳（入口组装层直注 _resolve_port）。"""
    from src.interfaces.cli.main import create_cli_app as _create_cli_app

    return _create_cli_app(resolve)


def main(argv: list[str] | None = None) -> int:
    """sisys 统一入口主函数（load_dotenv → 懒 bootstrap 工厂 → 派发 → 退出码映射）。

    Args:
        argv: 命令行参数（缺省 sys.argv[1:]——in-process 直调传显式列表）

    Returns:
        退出码（0=成功含空态 / 1=DomainError / 2=用法错误）
    """
    load_dotenv(ENV_FILE)  # R3-5：main() 函数体内、bootstrap 之前（禁模块级副作用形态）
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", stream=sys.stderr)
    app = create_cli_app(_resolve_port)
    try:
        result = app(argv if argv is not None else sys.argv[1:], standalone_mode=False)
        return result if isinstance(result, int) else 0
    except Exception as error:  # 入口统一出口（异常→退出码映射唯一承载位）
        return _map_exception_to_exit_code(error)


def _map_exception_to_exit_code(error: Exception) -> int:
    """异常统一映射（DomainError → stderr 呈现+1 / UsageError → 2 / Exit → 码）。"""
    import click

    from src.domain.exceptions.base_exceptions import DomainError

    if isinstance(error, DomainError):
        logger.error("领域异常: %s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1
    if isinstance(error, click.exceptions.Abort):
        return 130
    if isinstance(error, click.exceptions.Exit):
        return error.exit_code
    if isinstance(error, click.exceptions.UsageError):
        print(f"用法错误: {error.format_message()}", file=sys.stderr)
        return 2
    logger.error("CLI 执行异常: %s", error, exc_info=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
