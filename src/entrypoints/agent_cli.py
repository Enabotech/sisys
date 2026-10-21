"""Agent 命令行接口（Story 5-1 实例化 + Story 5-2 档案加载 + Story 5-3 工作流执行）

提供 Agent 实例化、档案加载与单 Agent 工作流执行命令行工具。使用 argparse
标准库（零额外依赖），通过 pyproject.toml 注册为 sisys-agent 入口点。

架构约束：
- 位于 entrypoints 组装层（进程入口，D1 方案 A 上移自 interfaces/cli）
- 通过 composition_root 的 bootstrap() + resolve("agent_instantiation_use_case" /
  "agent_profile_use_case" / "agent_workflow_use_case") 获取应用层用例（与
  ocr_cli 同款接线模式）
- 角色字符串 → 枚举转换必须守卫（禁止裸 AgentRole(value)——Enum 原生抛
  ValueError 逃逸统一异常体系，统一映射 AgentRoleNotSupportedError）
- agent_id 字符串 → UUID 转换必须守卫（禁止裸 uuid.UUID(value)——ValueError
  逃逸统一异常体系，统一映射 ValidationError(201)；argparse 的 type= 参数
  不得用 uuid.UUID——argparse 会把 ValueError 转 usage error exit 2 绕过
  统一异常体系）

幂等性：
- instantiate 非幂等——每次调用创建新 Agent 与新 Redis 键（AC-1.3 设计
  行为，靠 TTL 自然回收）。
- load-profile 幂等只读——纯读 + 发布事件，不创建/修改任何 Agent 领域状态
  （事件经 RELIABLE 通道落 PG outbox 表——进程外副作用，见 _close_connection_pools
  docstring）；发布事件是副作用（重复调用会重复发布 AgentProfileLoaded，
  事件带 event_id 消费方可按其幂等去重）。
- run-task 单次执行语义——六阶段工作流阻塞执行到终态（成功/失败完成态均
  正常走完 exit 0；443/441/444/445 等业务异常 exit 1）。

bootstrap 幂等守卫（Story 5-3——DC-12 ③ 前提）：
- _ensure_bootstrapped 检查 registry 关键端口已存在即跳过重放——防同进程
  二次 bootstrap 因 lambda 工厂 spec 不幂等抛 ConflictError（测试进程内
  main() 调用的前置条件）。

运行方式：
    sisys-agent instantiate --role ceo
    sisys-agent load-profile --agent-id <uuid>
    sisys-agent run-task --agent-id <uuid> --task "<任务描述>"
    poetry run sisys-agent run-task --agent-id <uuid> --task "<任务描述>"

输出：
    instantiate 成功路径 stdout 为纯 UUID 单行（agent_id）；
    load-profile 成功路径 stdout 为多行人类可读摘要（六档案逐项 OK +
    活跃技能数 + 启动上下文 token 计量）；日志与错误走 stderr；
    run-task 成功/失败完成态 stdout 为多行摘要（六阶段状态行 + 思维链
    五段预览 + 证据引用 + 置信度 + 状态标记）；
    退出码 0=成功或工作流正常走完（含失败完成态） / 1=业务异常（统一异常
    体系编码） / 2=用法错误（argparse）。
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid as uuid_module

from src.composition_root import bootstrap
from src.domain.entities.agent import AgentRole
from src.domain.exceptions import AgentRoleNotSupportedError, DomainError, ValidationError
from src.domain.ports.resolver import get_resolver, resolve

logger = logging.getLogger(__name__)


def _ensure_bootstrapped() -> None:
    """bootstrap 幂等守卫：registry 关键端口已存在即跳过重放（DC-12 ③前提）。

    同进程二次 bootstrap 会因 lambda 工厂 spec 不幂等必抛 ConflictError
    （PortRegistry.register 同名异 spec 冲突）——测试进程内 main() 调用
    （conftest _bootstrap_once 已引导）依赖本守卫短路重放。
    """
    from src.domain.ports.registry import _global_registry

    if _global_registry.get("agent_workflow_use_case") is not None:
        return
    bootstrap()


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


def _parse_agent_uuid(value: str) -> uuid_module.UUID:
    """agent_id 字符串 → UUID（守卫转换）

    禁止裸 uuid.UUID(value)——ValueError 逃逸统一异常体系；统一映射
    ValidationError(201)（应用层输入校验语义，对齐 ocr_cli D8 清偿后模式：
    int 页码转换 → 201 先例）。argparse 的 type= 参数不得用本函数裸包
    uuid.UUID（argparse 会把 ValueError 转 usage error exit 2）。

    Args:
        value: 命令行原始输入（如 "0f1e2d3c-4b5a-..."）

    Returns:
        uuid.UUID 对象

    Raises:
        ValidationError: EXCEPTION_201——非法 UUID 字符串（context 携带原始输入）
    """
    normalized = value.strip()
    try:
        return uuid_module.UUID(normalized)
    except ValueError:
        raise ValidationError(
            message=f"agent-id 必须为合法 UUID 字符串: {normalized!r}",
            context={"agent_id": normalized},
        ) from None


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器

    Returns:
        配置完成的 ArgumentParser 实例
    """
    parser = argparse.ArgumentParser(
        prog="sisys-agent",
        description="SISYS Agent 命令行工具 — Agent 实例化与身份档案加载（MVP: CEO 单 Agent）",
        epilog="示例: sisys-agent instantiate --role ceo | sisys-agent load-profile --agent-id <uuid>",
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

    load_profile = subparsers.add_parser(
        "load-profile",
        help="加载 Agent 身份档案（幂等只读——六档案 + ACTIVE 技能 + token 计量摘要）",
    )
    load_profile.add_argument(
        "-a",
        "--agent-id",
        type=str,
        required=True,
        metavar="AGENT_ID",
        help="目标 Agent 实例 UUID（instantiate 产出的 agent_id）",
    )

    run_task = subparsers.add_parser(
        "run-task",
        help="执行单 Agent 六阶段工作流（感知→规划→执行→验证→反思→证据打包——阻塞执行）",
    )
    run_task.add_argument(
        "-a",
        "--agent-id",
        type=str,
        required=True,
        metavar="AGENT_ID",
        help="目标 Agent 实例 UUID（instantiate 产出的 agent_id）",
    )
    run_task.add_argument(
        "-t",
        "--task",
        type=str,
        required=True,
        metavar="TASK",
        help='任务描述原文（如 "分析新能源汽车行业进入战略"）',
    )
    return parser


async def _close_connection_pools() -> None:
    """关闭已实例化的连接池（Redis/PostgreSQL——若存在），关闭失败仅记日志不抛。

    agent_cli 是首个打开 Redis 池的 CLI（instantiate 经仓储读写；ocr_cli 不
    触碰 Redis）；load-profile 侧 event_publisher → outbox 链路会实例化 PG
    engine（RELIABLE 事件落 outbox 表）——退出不关均留 ResourceWarning
    （R1-F7 对称清理）。仅关闭已实例化的 manager（peek 不触发懒实例化）；
    禁用全量 shutdown()——它会在退出路径惰性实例化 Qdrant/Neo4j 等
    本 CLI 未触达的 manager。

    逐 manager 独立 try/except：一处关闭失败不跳过另一处（Redis 失败仍关
    PG）。本方法在 finally 中调用：关闭异常（如断连超时）若上抛会反噬主
    结果——实例化成功被误报 exit 1、失败路径丢失根因异常，故内部消化记
    warning（对齐 run_tool_chain 发布失败「记日志不回滚」先例的防御面收窄）。
    """
    for manager_name in ("redis_connection_manager", "postgresql_connection_manager"):
        try:
            manager = get_resolver().peek_singleton(manager_name)
            if manager is not None:
                await manager.close()
        except Exception as exc:
            logger.warning("%s 关闭失败（忽略，不影响主结果）: %s: %s", manager_name, type(exc).__name__, exc)


async def _instantiate(role: AgentRole) -> object:
    """执行实例化并清理已打开的连接池（组合根经 bootstrap 引导后 resolve 用例）。"""
    use_case = resolve("agent_instantiation_use_case")
    try:
        return await use_case.execute(role=role)
    finally:
        await _close_connection_pools()


async def _load_profile(agent_id: uuid_module.UUID) -> object:
    """执行档案加载并清理已打开的连接池（读 Redis get_by_id 守卫 + outbox 触达 PG）。"""
    use_case = resolve("agent_profile_use_case")
    try:
        return await use_case.execute(agent_id=agent_id)
    finally:
        await _close_connection_pools()


def _print_profile_summary(result: object) -> None:
    """输出档案加载多行人类可读摘要（stdout）。

    六档案逐项 `文件名: OK (N chars)`（N 为 profile 字段 len 直读字符数）+
    活跃技能数（运行期动态值，不写字面量）+ 启动上下文 token 计量。

    Args:
        result: AgentProfileLoadResult（属性访问避免 import 依赖）
    """
    profile = getattr(result, "profile")
    file_fields = (
        ("IDENTITY.md", "identity"),
        ("CODE.md", "code_of_conduct"),
        ("SOUL.md", "soul"),
        ("USER.md", "user_preferences"),
        ("MEMORY.md", "memory"),
        ("HEARTBEAT.md", "heartbeat"),
    )
    for file_label, field_name in file_fields:
        content = getattr(profile, field_name)
        print(f"{file_label}: OK ({len(content)} chars)")
    print(f"活跃技能: {len(getattr(result, 'tools_l1'))}")
    print(f"启动上下文: {getattr(result, 'startup_context_tokens')} tokens")


def _run_load_profile_cli(agent_id_raw: str) -> int:
    """load-profile 子命令执行（守卫 → bootstrap → 执行 → 摘要输出）。

    Args:
        agent_id_raw: --agent-id 原始字符串

    Returns:
        退出码（0=成功，1=业务异常）
    """
    # UUID 守卫（先于 bootstrap——输入错误无需初始化端口注册表）
    try:
        agent_id = _parse_agent_uuid(agent_id_raw)
    except ValidationError as error:
        logger.error("%s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1

    try:
        _ensure_bootstrapped()
        result = asyncio.run(_load_profile(agent_id))
        _print_profile_summary(result)
        logger.info(
            "Agent 档案加载成功: agent_id=%s tokens=%s",
            getattr(result, "agent_id"),
            getattr(result, "startup_context_tokens"),
        )
        return 0
    except DomainError as error:
        logger.error("Agent 档案加载失败: %s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1
    except Exception as error:
        logger.error("Agent 档案加载异常: %s", error, exc_info=True)
        return 1


async def _run_task(agent_id: uuid_module.UUID, task: str) -> object:
    """执行单 Agent 工作流并清理已打开的连接池（守卫触 Redis + outbox 触达 PG）。"""
    use_case = resolve("agent_workflow_use_case")
    try:
        return await use_case.execute(agent_id=agent_id, task=task)
    finally:
        await _close_connection_pools()


def _print_workflow_summary(result: object) -> None:
    """输出工作流执行多行人类可读摘要（stdout）。

    六阶段状态行（executed_phases 轨迹）+ 思维链五段预览（to_display）+
    证据引用 + 置信度 + 状态标记（completed/failed——CLI 契约定稿：失败
    完成态 exit 0 语义下的状态可观测锚点）。

    Args:
        result: AgentWorkflowResult（属性访问避免 import 依赖）
    """
    status = getattr(result, "workflow_status")
    phases = getattr(result, "executed_phases")
    print(f"工作流状态: {status}（重试 {getattr(result, 'retry_count')} 次）")
    print(f"阶段轨迹: {' → '.join(phases)}")
    print(getattr(getattr(result, "chain"), "to_display")())
    evidence = getattr(result, "evidence")
    print(f"证据引用: {getattr(evidence, 'input_hash')}")
    print(f"置信度: {getattr(evidence, 'confidence')}")
    if status == "failed":
        print(f"失败原因: {getattr(evidence, 'failure_reason')}")


def _run_task_cli(agent_id_raw: str, task: str) -> int:
    """run-task 子命令执行（守卫 → bootstrap → 执行 → 摘要输出）。

    退出码契约（CLI 契约定稿）：成功与失败完成态均 exit 0（工作流正常走完
    语义——status 可观测锚点在摘要输出）；443/441/444/445 等业务异常 exit 1。

    Args:
        agent_id_raw: --agent-id 原始字符串
        task: --task 原始字符串

    Returns:
        退出码（0=工作流正常走完（含失败完成态），1=业务异常）
    """
    # UUID 守卫（先于 bootstrap——输入错误无需初始化端口注册表）
    try:
        agent_id = _parse_agent_uuid(agent_id_raw)
    except ValidationError as error:
        logger.error("%s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1

    try:
        _ensure_bootstrapped()
        result = asyncio.run(_run_task(agent_id, task))
        _print_workflow_summary(result)
        logger.info(
            "Agent 工作流执行完成: status=%s",
            getattr(result, "workflow_status"),
        )
        return 0
    except DomainError as error:
        logger.error("Agent 工作流执行失败: %s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1
    except Exception as error:
        logger.error("Agent 工作流执行异常: %s", error, exc_info=True)
        return 1


def _run_instantiate_cli(role_raw: str) -> int:
    """instantiate 子命令执行（守卫 → bootstrap → 执行 → UUID 输出）。

    Args:
        role_raw: --role 原始字符串

    Returns:
        退出码（0=成功，1=业务异常）
    """
    # 角色守卫（先于 bootstrap——用法/输入错误无需初始化端口注册表）
    try:
        role = _parse_role(role_raw)
    except AgentRoleNotSupportedError as error:
        logger.error("%s", error)
        print(f"[{error.code}] {error.message} (role={error.context.get('role')!r})", file=sys.stderr)
        return 1

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

    if args.command == "load-profile":
        return _run_load_profile_cli(args.agent_id)
    if args.command == "run-task":
        return _run_task_cli(args.agent_id, args.task)
    return _run_instantiate_cli(args.role)


# ===================================================================
# 模块入口
# ===================================================================

if __name__ == "__main__":
    sys.exit(main())
