"""Agent 命令行接口（Story 5-1 — CEO Agent 实例化 MVP）

提供 Agent 实例化命令行工具。使用 argparse 标准库（零额外依赖），
通过 pyproject.toml 注册为 sisys-agent 入口点。

架构约束：
- 位于 entrypoints 组装层（进程入口，D1 方案 A 上移自 interfaces/cli）
- 通过 composition_root 的 bootstrap() + resolve("agent_instantiation_use_case")
  获取应用层用例（与 ocr_cli 同款接线模式）
- 角色字符串 → 枚举转换必须守卫（禁止裸 AgentRole(value)——Enum 原生抛
  ValueError 逃逸统一异常体系，统一映射 AgentRoleNotSupportedError）

幂等性：instantiate 非幂等——每次调用创建新 Agent 与新 Redis 键
（AC-1.3 设计行为，靠 TTL 自然回收）。

运行方式：
    sisys-agent instantiate --role ceo
    poetry run sisys-agent instantiate --role ceo

输出：
    成功路径 stdout 为纯 UUID 单行（agent_id）；日志与错误走 stderr；
    退出码 0=成功 / 1=业务异常（统一异常体系编码） / 2=用法错误（argparse）。
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from src.composition_root import bootstrap
from src.domain.entities.agent import AgentRole
from src.domain.exceptions import AgentRoleNotSupportedError, DomainError
from src.domain.ports.resolver import get_resolver, resolve

logger = logging.getLogger(__name__)


def _parse_role(role_str: str) -> AgentRole:
    """角色字符串 → AgentRole 枚举（守卫转换）

    大小写归一化（.lower()）+ 空白剥离；非法字符串与未开放角色统一映射
    AgentRoleNotSupportedError(441)，context 携带原始输入与支持列表。
    两道防线：①禁止裸 AgentRole(value) 的 ValueError 逃逸统一异常体系；
    ②合法枚举但未开放（如 "cfo"——字符串转换拦不住它）经 SUPPORTED_ROLES
    预检拦截（用例层守卫仍是 441 真源，本预检为 CLI 早期拒绝）。

    Args:
        role_str: 命令行原始输入（如 "ceo"/"CEO"/"cfo"）

    Returns:
        AgentRole 枚举实例

    Raises:
        AgentRoleNotSupportedError: 非法或未开放角色字符串（EXCEPTION_441）
    """
    from src.application.use_cases.agent_instantiation import SUPPORTED_ROLES

    normalized = role_str.strip().lower()
    role: AgentRole
    try:
        role = AgentRole(normalized)
    except ValueError:
        raise AgentRoleNotSupportedError(
            role=role_str,
            supported_roles=tuple(sorted(supported.value for supported in SUPPORTED_ROLES)),
        ) from None
    if role not in SUPPORTED_ROLES:
        raise AgentRoleNotSupportedError(
            role=role_str,
            supported_roles=tuple(sorted(supported.value for supported in SUPPORTED_ROLES)),
        )
    return role


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器

    Returns:
        配置完成的 ArgumentParser 实例
    """
    parser = argparse.ArgumentParser(
        prog="sisys-agent",
        description="SISYS Agent 命令行工具 — Agent 实例化（MVP: CEO 单 Agent）",
        epilog="示例: sisys-agent instantiate --role ceo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # required=True 必设：argparse 子命令默认可选，裸调用 sisys-agent 会因取
    # args.role 抛 AttributeError 裸崩（逃逸统一异常体系；ocr_cli 无子命令先例，
    # 此点不可从模板继承）
    subparsers = parser.add_subparsers(required=True, dest="command")

    instantiate = subparsers.add_parser(
        "instantiate",
        help="实例化 Agent（每次调用创建新 Agent，非幂等——靠状态 TTL 自然回收）",
    )
    instantiate.add_argument(
        "-r",
        "--role",
        type=str,
        required=True,
        metavar="ROLE",
        help='Agent 角色字符串（MVP 仅 "ceo" 开放；大小写不敏感）',
    )
    return parser


async def _close_redis_pool() -> None:
    """关闭已实例化的 Redis 连接池（若存在）——关闭失败仅记日志不抛。

    agent_cli 是首个打开 Redis 池的 CLI（ocr_cli 不触碰 Redis）——退出不关池
    留 ResourceWarning。仅关闭已实例化的 redis_connection_manager（peek 不触发
    懒实例化）；禁用全量 shutdown()——它会在退出路径惰性实例化 PG/Qdrant/Neo4j
    manager。

    本方法在 finally 中调用：关闭异常（如断连超时）若上抛会反噬主结果——
    实例化成功被误报 exit 1、失败路径丢失根因异常，故内部消化记 warning
    （对齐 run_tool_chain 发布失败「记日志不回滚」先例的防御面收窄）。
    """
    try:
        manager = get_resolver().peek_singleton("redis_connection_manager")
        if manager is not None:
            await manager.close()
    except Exception as exc:
        logger.warning("Redis 连接池关闭失败（忽略，不影响主结果）: %s: %s", type(exc).__name__, exc)


async def _instantiate(role: AgentRole) -> object:
    """执行实例化并清理 Redis 池（组合根经 bootstrap 引导后 resolve 用例）。"""
    use_case = resolve("agent_instantiation_use_case")
    try:
        return await use_case.execute(role=role)
    finally:
        await _close_redis_pool()


def main(argv: list[str] | None = None) -> int:
    """CLI 主入口

    Args:
        argv: 命令行参数（默认使用 sys.argv[1:]）

    Returns:
        退出码（0=成功，1=业务异常，2=用法错误——argparse 自动）
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    # 角色守卫（先于 bootstrap——用法/输入错误无需初始化端口注册表）
    try:
        role = _parse_role(args.role)
    except AgentRoleNotSupportedError as error:
        logger.error("%s", error)
        print(f"[{error.code}] {error.message} (role={error.context.get('role')!r})", file=sys.stderr)
        return 1

    # 初始化端口注册表（独立进程内 bootstrap 合法）——纳入统一异常处理：
    # bootstrap 失败（依赖缺失/二次注册冲突）同样遵守「编码输出 + 退出码」契约，
    # 禁裸 traceback 逃逸（成功后路径行为不变）
    try:
        bootstrap()
        result = asyncio.run(_instantiate(role))
        # 输出格式定稿：纯 UUID 单行 stdout（日志走 stderr，供脚本消费）
        print(getattr(result, "agent_id"))
        logger.info("Agent 实例化成功: role=%s", role.value)
        return 0
    except DomainError as error:
        logger.error("Agent 实例化失败: %s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1
    except Exception as error:
        logger.error("Agent 实例化异常: %s", error, exc_info=True)
        return 1


# ===================================================================
# 模块入口
# ===================================================================

if __name__ == "__main__":
    sys.exit(main())
