"""Agent 命令行接口（Story 5-1 实例化 + Story 5-2 档案加载 + Story 5-3 工作流执行 + Story 5-4 隔离管理）

提供 Agent 实例化、档案加载、单 Agent 工作流执行与 EIP 隔离管理命令行工具。
使用 argparse 标准库（零额外依赖），通过 pyproject.toml 注册为 sisys-agent 入口点。

架构约束：
- 位于 entrypoints 组装层（进程入口，D1 方案 A 上移自 interfaces/cli）
- 通过 composition_root 的 bootstrap() + resolve("agent_instantiation_use_case" /
  "agent_profile_use_case" / "agent_workflow_use_case" /
  "isolation_management_service") 获取应用层用例/服务（与 ocr_cli 同款接线模式）
- 角色字符串 → 枚举转换必须守卫（禁止裸 AgentRole(value)——Enum 原生抛
  ValueError 逃逸统一异常体系，统一映射 AgentRoleNotSupportedError）
- 隔离等级字符串 → 枚举转换必须守卫（Story 5-4——禁止裸 IsolationLevel(value)，
  统一映射 IsolationLevelNotSupportedError(446)；禁 .lower() 归一——
  AgentRole 枚举值全小写而 IsolationLevel 全大写，lower 化将拒绝全部合法输入；
  --level 大小写敏感）
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
- set-isolation 同等级 no-op 是正常态（exit 0 + 未变更提示——幂等重试语义；
  Story 5-4）。

bootstrap 幂等守卫（Story 5-3——DC-12 ③ 前提）：
- _ensure_bootstrapped 检查 registry 关键端口已存在即跳过重放——防同进程
  二次 bootstrap 因 lambda 工厂 spec 不幂等抛 ConflictError（测试进程内
  main() 调用的前置条件）。

运行方式：
    sisys-agent instantiate --role ceo
    sisys-agent load-profile --agent-id <uuid>
    sisys-agent run-task --agent-id <uuid> --task "<任务描述>"
    sisys-agent isolation-status --agent-id <uuid>
    sisys-agent set-isolation --agent-id <uuid> --level <L4|L3|L2> --reason "<原因>"
    poetry run sisys-agent run-task --agent-id <uuid> --task "<任务描述>"

输出：
    instantiate 成功路径 stdout 为纯 UUID 单行（agent_id）；
    load-profile 成功路径 stdout 为多行人类可读摘要（六档案逐项 OK +
    活跃技能数 + 启动上下文 token 计量）；日志与错误走 stderr；
    run-task 成功/失败完成态 stdout 为多行摘要（六阶段状态行 + 思维链
    五段预览 + 证据引用 + 置信度 + 状态标记）；
    isolation-status 成功路径 stdout 为多行摘要（等级+名称 / 三维度策略 /
    isoformat 时间 / 最近触发原因——Story 5-4）；
    set-isolation 成功路径 stdout 为切换摘要（previous -> target）或
    no-op 提示（exit 0 含 no-op——幂等语义）；
    退出码 0=成功或工作流正常走完（含失败完成态/no-op） / 1=业务异常（统一异常
    体系编码） / 2=用法错误（argparse）。
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid as uuid_module
from datetime import datetime

from src.application.ports.isolation_management import (
    IsolationManagementServicePort,
    IsolationSwitchResult,
)
from src.composition_root import bootstrap
from src.domain.entities.agent import AgentRole
from src.domain.entities.isolation_state import IsolationState
from src.domain.events.enums import IsolationLevel
from src.domain.exceptions import (
    AgentRoleNotSupportedError,
    DomainError,
    IsolationLevelNotSupportedError,
    ValidationError,
)
from src.domain.ports.isolation_switch_log_repository import (
    IsolationSwitchLogQuery,
    IsolationSwitchLogRepository,
    IsolationSwitchLogSearchResult,
)
from src.domain.ports.resolver import get_resolver, resolve

logger = logging.getLogger(__name__)

# CLI 支持的隔离等级清单（显式元组字面量——禁从 frozenset 迭代派生：迭代序
# 不稳定致帮助文本漂移；与 domain MVP_ALLOWED_LEVELS 集合相等由测试双锁
# （V2 开放 L1 时仅改 domain 常量，测试红提醒同步本清单）——Story 5-4）
SUPPORTED_ISOLATION_LEVELS: tuple[str, ...] = ("L4", "L3", "L2")


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


def _parse_isolation_level(raw: str) -> IsolationLevel:
    """隔离等级字符串 → IsolationLevel 枚举（守卫转换——Story 5-4）

    两道守卫（顺序对齐 _parse_role 先例——第一道转换在前是唯一拦截非法
    字符串的活路径，第二道预检拦「合法枚举但未开放」即 L1 融合态）:
    ① 禁止裸 IsolationLevel(raw)——Enum 原生 ValueError 逃逸统一异常体系，
      统一映射 IsolationLevelNotSupportedError(446)；
    ② MVP_ALLOWED_LEVELS 预检——L1 是合法枚举值，字符串转换拦不住它。
    大小写敏感（契约 <L4|L3|L2>——枚举值全大写，禁 .lower() 归一——
    AgentRole 先例的归一化在此不适用）。

    Args:
        raw: 命令行原始输入（如 "L4"；"l4"/"L9" 均为非法输入）

    Returns:
        IsolationLevel 枚举实例

    Raises:
        IsolationLevelNotSupportedError: 非法或未开放等级字符串（EXCEPTION_446
            ——context 携带原始输入与支持列表）
    """
    from src.domain.value_objects.isolation_policy import MVP_ALLOWED_LEVELS

    level: IsolationLevel
    try:
        level = IsolationLevel(raw.strip())
    except ValueError:
        raise IsolationLevelNotSupportedError(
            level=raw,
            supported_levels=SUPPORTED_ISOLATION_LEVELS,
        ) from None
    if level not in MVP_ALLOWED_LEVELS:
        raise IsolationLevelNotSupportedError(
            level=raw,
            supported_levels=SUPPORTED_ISOLATION_LEVELS,
        )
    return level


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器

    Returns:
        配置完成的 ArgumentParser 实例
    """
    parser = argparse.ArgumentParser(
        prog="sisys-agent",
        description="SISYS Agent 命令行工具 — Agent 实例化/档案加载/任务执行/EIP 隔离管理（MVP: CEO 单 Agent）",
        epilog=(
            "示例: sisys-agent instantiate --role ceo | sisys-agent load-profile --agent-id <uuid> | "
            "sisys-agent run-task --agent-id <uuid> --task <文本> | "
            "sisys-agent isolation-status --agent-id <uuid> | "
            "sisys-agent set-isolation --agent-id <uuid> --level L3 --reason <文本> | "
            "sisys-agent isolation-logs --agent-id <uuid> [--level L3] [--start <ISO>] [--end <ISO>]"
        ),
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

    isolation_status = subparsers.add_parser(
        "isolation-status",
        help="查询 Agent EIP 隔离状态（等级 + 三维度策略 + 时间与触发原因）",
    )
    isolation_status.add_argument(
        "-a",
        "--agent-id",
        type=str,
        required=True,
        metavar="AGENT_ID",
        help="目标 Agent 实例 UUID（instantiate 产出的 agent_id）",
    )

    set_isolation = subparsers.add_parser(
        "set-isolation",
        help="切换 Agent EIP 隔离等级（MVP 唯一触发通道——用户显式请求；同等级 no-op 幂等）",
    )
    set_isolation.add_argument(
        "-a",
        "--agent-id",
        type=str,
        required=True,
        metavar="AGENT_ID",
        help="目标 Agent 实例 UUID（instantiate 产出的 agent_id）",
    )
    set_isolation.add_argument(
        "-l",
        "--level",
        type=str,
        required=True,
        metavar="LEVEL",
        help='目标隔离等级（MVP 开放 "L4"/"L3"/"L2"——大小写敏感；L1 融合态 V2 开放）',
    )
    set_isolation.add_argument(
        "-r",
        "--reason",
        type=str,
        required=True,
        metavar="REASON",
        help='切换原因（非空——用户显式请求语义必填，如 "任务需要软隔离"）',
    )
    isolation_logs = subparsers.add_parser(
        "isolation-logs",
        help="检索 Agent 隔离切换日志（FR-AC-06 审计留痕——按 AGENT/时间/等级多维 + 分页）",
    )
    isolation_logs.add_argument(
        "-a",
        "--agent-id",
        type=str,
        required=False,
        default=None,
        metavar="AGENT_ID",
        help="按 Agent 实例 UUID 精确过滤（可选——缺省检索全部 Agent）",
    )
    isolation_logs.add_argument(
        "-l",
        "--level",
        type=str,
        required=False,
        default=None,
        metavar="LEVEL",
        help='按隔离等级过滤（可选 "L4"/"L3"/"L2"——原等级或目标等级任一命中即返回）',
    )
    isolation_logs.add_argument(
        "--start",
        type=str,
        required=False,
        default=None,
        metavar="ISO8601",
        help="切换时间闭区间下界（可选 ISO 8601，如 2026-10-25T00:00:00+00:00）",
    )
    isolation_logs.add_argument(
        "--end",
        type=str,
        required=False,
        default=None,
        metavar="ISO8601",
        help="切换时间闭区间上界（可选 ISO 8601）",
    )
    isolation_logs.add_argument(
        "-n",
        "--limit",
        type=int,
        required=False,
        default=50,
        metavar="N",
        help="分页上限（默认 50，上限 500）",
    )
    isolation_logs.add_argument(
        "-o",
        "--offset",
        type=int,
        required=False,
        default=0,
        metavar="N",
        help="分页偏移（默认 0）",
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


def _print_isolation_status_summary(state: object) -> None:
    """输出隔离状态多行人类可读摘要（stdout——Story 5-4）。

    等级+名称 / 三维度策略（消费方持 state 联查 get_isolation_policy 派生）/
    isoformat 全格式时间 / 最近触发原因。

    Args:
        state: IsolationState（属性访问避免 import 依赖——R4 接口层适配）
    """
    from src.domain.value_objects.isolation_policy import get_isolation_policy

    current_level = getattr(state, "current_level")
    policy = get_isolation_policy(current_level)
    print(f"当前隔离等级: {current_level.value}（{policy.name}）")
    print(f"Prompt 隔离: {policy.prompt_isolation}")
    print(f"工具隔离: {policy.tool_isolation}")
    print(f"数据隔离: {policy.data_isolation.value}")
    print(f"初始化时间: {getattr(state, 'initialized_at').isoformat()}")
    print(f"更新时间: {getattr(state, 'updated_at').isoformat()}")
    print(f"最近触发原因: {getattr(state, 'last_trigger_reason')}")


def _run_isolation_status_cli(agent_id_raw: str) -> int:
    """isolation-status 子命令执行（守卫 → bootstrap → 执行 → 摘要输出）。

    Args:
        agent_id_raw: --agent-id 原始字符串

    Returns:
        退出码（0=成功，1=业务异常——443/447/201）
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
        service = resolve("isolation_management_service")
        state = asyncio.run(_get_isolation_state(service, agent_id))
        _print_isolation_status_summary(state)
        logger.info("隔离状态查询成功: agent_id=%s", agent_id)
        return 0
    except DomainError as error:
        logger.error("隔离状态查询失败: %s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1
    except Exception as error:
        logger.error("隔离状态查询异常: %s", error, exc_info=True)
        return 1


async def _get_isolation_state(service: IsolationManagementServicePort, agent_id: uuid_module.UUID) -> IsolationState:
    """查询隔离状态并清理已打开的连接池（守卫触 Redis + outbox 触达 PG）。"""
    try:
        return await service.get_isolation_state(agent_id)
    finally:
        await _close_connection_pools()


def _print_switch_summary(result: object, target_level: IsolationLevel) -> None:
    """输出切换摘要（成功切换 / no-op 两形态——stdout）。"""
    switched = getattr(result, "switched")
    if switched:
        state = getattr(result, "state")
        previous_value = getattr(getattr(result, "event"), "previous_level", None)
        previous = previous_value.value if previous_value is not None else target_level.value
        reason = getattr(state, "last_trigger_reason")
        print(f"隔离等级已切换: {previous} -> {target_level.value}（原因: {reason}）")
    else:
        print(f"隔离等级未变更（同等级 {target_level.value}）: no-op")


def _run_set_isolation_cli(agent_id_raw: str, level_raw: str, reason: str) -> int:
    """set-isolation 子命令执行（守卫 → bootstrap → 执行 → 摘要输出）。

    Args:
        agent_id_raw: --agent-id 原始字符串
        level_raw: --level 原始字符串（L9/L1 → 446 统一异常出口）
        reason: --reason 原始字符串

    Returns:
        退出码（0=成功（含 no-op），1=业务异常——443/446/447/201）
    """
    # 双守卫（先于 bootstrap——输入错误无需初始化端口注册表）
    try:
        agent_id = _parse_agent_uuid(agent_id_raw)
        level = _parse_isolation_level(level_raw)
    except (ValidationError, IsolationLevelNotSupportedError) as error:
        logger.error("%s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1

    try:
        _ensure_bootstrapped()
        service = resolve("isolation_management_service")
        result = asyncio.run(_switch_isolation_level(service, agent_id, level, reason))
        _print_switch_summary(result, level)
        logger.info("隔离等级切换命令完成: agent_id=%s level=%s", agent_id, level.value)
        return 0
    except DomainError as error:
        logger.error("隔离等级切换失败: %s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1
    except Exception as error:
        logger.error("隔离等级切换异常: %s", error, exc_info=True)
        return 1


async def _switch_isolation_level(
    service: IsolationManagementServicePort,
    agent_id: uuid_module.UUID,
    level: IsolationLevel,
    reason: str,
) -> IsolationSwitchResult:
    """执行隔离等级切换并清理已打开的连接池。"""
    try:
        return await service.switch_isolation_level(agent_id, level, reason)
    finally:
        await _close_connection_pools()


def _parse_optional_agent_uuid(agent_id_raw: str | None) -> uuid_module.UUID | None:
    """可选 --agent-id 解析（None 直通——isolation-logs 全量检索形态）.

    Raises:
        ValidationError: 非法 UUID 字符串（EXCEPTION_201）
    """
    if agent_id_raw is None:
        return None
    return _parse_agent_uuid(agent_id_raw)


def _parse_optional_iso_datetime(raw: str | None, option_name: str) -> datetime | None:
    """可选 ISO 8601 时间参数解析（None 直通；非法格式 → ValidationError 201）.

    Args:
        raw: --start/--end 原始字符串
        option_name: 参数名（错误消息定位）

    Raises:
        ValidationError: 非法 ISO 8601 格式（EXCEPTION_201）
    """
    if raw is None:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as error:
        raise ValidationError(
            message=f"{option_name} 必须为 ISO 8601 格式（实际值 {raw!r}，如 2026-10-25T00:00:00+00:00）",
        ) from error
    if parsed.tzinfo is None:
        raise ValidationError(
            message=f"{option_name} 必须携带时区（实际值 {raw!r}——裸时间会产生本地时区歧义）",
        )
    return parsed


def _run_isolation_logs_cli(
    agent_id_raw: str | None,
    level_raw: str | None,
    start_raw: str | None,
    end_raw: str | None,
    limit: int,
    offset: int,
) -> int:
    """isolation-logs 子命令执行（守卫 → bootstrap → 检索 → 摘要输出——Story 5.6）.

    Args:
        agent_id_raw: --agent-id 原始字符串（可选）
        level_raw: --level 原始字符串（可选——CLI 层枚举转换守卫）
        start_raw: --start 原始字符串（可选 ISO 8601）
        end_raw: --end 原始字符串（可选 ISO 8601）
        limit: 分页上限
        offset: 分页偏移

    Returns:
        退出码（0=成功（含空结果），1=业务异常——446/201/103）
    """
    # 多守卫（先于 bootstrap——输入错误无需初始化端口注册表）
    try:
        agent_id = _parse_optional_agent_uuid(agent_id_raw)
        level = _parse_isolation_level(level_raw) if level_raw is not None else None
        start_time = _parse_optional_iso_datetime(start_raw, "--start")
        end_time = _parse_optional_iso_datetime(end_raw, "--end")
    except (ValidationError, IsolationLevelNotSupportedError) as error:
        logger.error("%s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1

    try:
        _ensure_bootstrapped()
        repo = resolve("isolation_switch_log_repository")
        query = IsolationSwitchLogQuery(
            agent_id=agent_id,
            start_time=start_time,
            end_time=end_time,
            level=level,
            offset=offset,
            limit=limit,
        )
        result = asyncio.run(_search_isolation_logs(repo, query))
        _print_isolation_logs_summary(result)
        logger.info("隔离切换日志检索完成: total=%s offset=%d limit=%d", result.total, offset, limit)
        return 0
    except DomainError as error:
        logger.error("隔离切换日志检索失败: %s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1
    except Exception as error:
        logger.error("隔离切换日志检索异常: %s", error, exc_info=True)
        return 1


async def _search_isolation_logs(
    repo: IsolationSwitchLogRepository, query: IsolationSwitchLogQuery
) -> IsolationSwitchLogSearchResult:
    """检索隔离切换日志并清理已打开的连接池（fallback 独立会话触达 PG）。"""
    try:
        return await repo.search(query)
    finally:
        await _close_connection_pools()


def _print_isolation_logs_summary(result: object) -> None:
    """输出切换日志检索摘要（空结果单行 / 多行条目 + 尾行总数——stdout）."""
    items = getattr(result, "items")
    total = getattr(result, "total")
    offset = getattr(result, "offset")
    if not items:
        print("无隔离切换日志记录")
        return
    for log in items:
        log_id_short = str(getattr(log, "log_id"))[:8]
        previous_value = getattr(log, "previous_level").value
        target_value = getattr(log, "target_level").value
        switch_ts = getattr(log, "switch_timestamp").isoformat()
        reason = getattr(log, "trigger_reason")
        reason_display = reason if len(reason) <= 40 else f"{reason[:40]}..."
        chain = getattr(log, "approval_chain")
        chain_display = " → ".join(chain) if chain else "-"
        print(
            f"[{log_id_short}] {previous_value} -> {target_value} | {switch_ts} | "
            f"原因: {reason_display} | 审批链: {chain_display}"
        )
    print(f"共 {total} 条（显示 {len(items)} 条，offset={offset}）")


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
    if args.command == "isolation-status":
        return _run_isolation_status_cli(args.agent_id)
    if args.command == "set-isolation":
        return _run_set_isolation_cli(args.agent_id, args.level, args.reason)
    if args.command == "isolation-logs":
        return _run_isolation_logs_cli(
            args.agent_id,
            args.level,
            args.start,
            args.end,
            args.limit,
            args.offset,
        )
    return _run_instantiate_cli(args.role)


# ===================================================================
# 模块入口
# ===================================================================

if __name__ == "__main__":
    sys.exit(main())
