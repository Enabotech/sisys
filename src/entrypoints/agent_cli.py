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
from typing import Any

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
    EntityValidationError,
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


def load_env(dotenv_path: str | None = None) -> None:
    """显式加载 .env（Story 7-1——6.8-R1-DF1 核销，OD-7 三选一定谳）。

    三层根因修复：入口显式 load_dotenv（python -m 形态下 dotenv 的
    find_dotenv 从 site-packages 向上遍历永不经过仓库目录——仓库根以
    ``Path(__file__)`` 上溯显式定位）；override=False 保护既有环境变量
    （测试形态 env 优先不受影响）；SISYS_USE_TEST_PORTS=1 时跳过（.env 被
    git 追踪，测试进程内注入会泄漏非端口键污染同 worker 后续场景）。

    Args:
        dotenv_path: 显式 .env 路径（缺省仓库根探测——src/entrypoints 上溯两级）
    """
    import os
    from pathlib import Path

    if os.environ.get("SISYS_USE_TEST_PORTS") == "1":
        return  # 测试形态守卫（R1-19）
    from dotenv import load_dotenv

    path = Path(dotenv_path) if dotenv_path else Path(__file__).resolve().parents[2] / ".env"
    if path.is_file():
        load_dotenv(dotenv_path=str(path), override=False)


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


def _validate_plan_uuid(plan_id: str, command: str) -> str:
    """plan_id 守卫 + canonical 归一（Story 7-1——6.9-R1-DF1 核销）。

    校验通过返回 ``str(uuid_module.UUID(plan_id))`` 小写 canonical 形态：
    大写/无连字符等宽松形态归一后下传（服务层键拼接恒小写 canonical，
    原始串下传即键 miss → 静默空态 exit 0 欺骗性成功——本归一即其修复）；
    非法输入统一 ``EntityValidationError`` 242（九处内联守卫单点收敛，
    消息与 context 键面不变——行为只增强不破坏）。

    Args:
        plan_id: --plan-id 原始字符串
        command: 命令名（异常 context 携带——错误定位）

    Returns:
        canonical 小写 UUID 字符串

    Raises:
        EntityValidationError: 242——非 UUID 形态
    """
    try:
        return str(uuid_module.UUID(plan_id))
    except (ValueError, TypeError, AttributeError):
        raise EntityValidationError(
            message="plan_id 必须为 UUID 字符串",
            context={"command": command, "field": "plan_id", "plan_id": plan_id},
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

    blm_plan = subparsers.add_parser(
        "blm-plan",
        help="执行 BLM 前两阶段规划（业绩差距分析+市场洞察六子步骤——MVP CEO 单角色阻塞执行）",
    )
    blm_plan.add_argument(
        "-a",
        "--agent-id",
        type=str,
        required=True,
        metavar="AGENT_ID",
        help="目标 Agent 实例 UUID（instantiate 产出的 agent_id）",
    )
    blm_plan.add_argument(
        "-t",
        "--task",
        type=str,
        required=True,
        metavar="TASK",
        help='规划任务描述（如 "制定新能源汽车行业五年战略规划"）',
    )
    blm_plan.add_argument(
        "--plan-id",
        type=str,
        default=None,
        metavar="PLAN_ID",
        help="规划任务标识（缺省新铸——同 id 重跑将被拒绝 482，重试请用新 id；"
        "建议 UUID 字符串——非 UUID 形态思维链归档将全程静默缺席，CR3-F1）",
    )

    # Story 6-4: chain-query 扁平子命令（决策追溯查询——AC-5 CLI 消费入口；
    # --include-blob 缺省 False：默认读 L2 决策依据足够，深度审计显式开启）
    chain_query = subparsers.add_parser(
        "chain-query",
        help="决策追溯查询（按 plan_id 读回 EVIDENCE_PACKAGE 思维链档案——五段展示形态）",
    )
    chain_query.add_argument(
        "--plan-id",
        type=str,
        required=True,
        metavar="PLAN_ID",
        help="规划任务标识（UUID 字符串——与 BLM plan_id 同源）",
    )
    chain_query.add_argument(
        "--include-blob",
        action="store_true",
        default=False,
        help="深度解引用 L4 WORM blob（默认 False——读 L2 决策依据足够）",
    )

    # Story 6-5a: report-generate 扁平子命令（Markdown 报告生成——双源聚合+
    # 领域渲染+L0/L2 持久化+ReportGenerated 首激活；同 plan_id 重复生成产生新
    # 报告不拦截——OD-10 幂等锚=report_id）；Story 6-5b: --format {markdown,pdf}
    # 参数扩展（默认 markdown 向后兼容——OD-11，单入口演进友好）
    report_generate = subparsers.add_parser(
        "report-generate",
        help="按 plan_id 生成战略规划报告（Markdown/PDF——BLM 前两阶段交付物）",
    )
    report_generate.add_argument(
        "--plan-id",
        type=str,
        required=True,
        metavar="PLAN_ID",
        help="规划任务标识（UUID 字符串——与 BLM plan_id 同源）",
    )
    report_generate.add_argument(
        "--format",
        type=str,
        choices=("markdown", "pdf"),
        default="markdown",
        metavar="FORMAT",
        help="报告格式（默认 markdown 向后兼容；pdf 含引文索引与 L4 WORM 归档——Story 6-5b）",
    )
    report_generate.add_argument(
        "--brand-template",
        type=str,
        required=False,
        default=None,
        metavar="TEMPLATE_NAME",
        help="品牌模板名（可选——白标 PDF 渲染应用品牌三件；仅 --format pdf 支持组合，Story 6-11）",
    )

    # Story 6-3: checkpoint-create 扁平子命令（Checkpoint 完整形态快照显式创建——
    # OD-5：MVP 同步链下"阶段完成即暂停等审批"物理不可达，由显式调用触发；
    # created_via 不暴露参数（硬编码传 "cli"——R6-4）；retrieved_docs 不可经
    # argparse（空列表构造——take_notes 实体抽取对空检索证据降级容忍 :238-246）
    checkpoint_create = subparsers.add_parser(
        "checkpoint-create",
        help="显式创建 Checkpoint 完整形态快照（持久化笔记→压缩→归档→落库→发布五步机制）",
    )
    checkpoint_create.add_argument(
        "--plan-id",
        type=str,
        required=True,
        metavar="PLAN_ID",
        help="规划任务标识（UUID 字符串——与 BLM plan_id 同源）",
    )
    checkpoint_create.add_argument(
        "--checkpoint-no",
        type=str,
        required=True,
        metavar="CP_NO",
        help='检查点编号（"CP-1".."CP-8"——BLM 前两阶段 8 恢复点）',
    )
    checkpoint_create.add_argument(
        "--stage-id",
        type=str,
        required=True,
        metavar="STAGE_ID",
        help="阶段标识（STAGE_VALUE_DOMAIN 值域，如 performance_gap）",
    )
    checkpoint_create.add_argument(
        "--query",
        type=str,
        required=True,
        metavar="QUERY",
        help="原始查询文本（持久化笔记输入）",
    )
    checkpoint_create.add_argument(
        "--user-id",
        type=str,
        required=True,
        metavar="USER_ID",
        help="执行用户标识",
    )
    checkpoint_create.add_argument(
        "--summary",
        type=str,
        required=True,
        metavar="SUMMARY",
        help="阶段摘要（调用方直供）",
    )
    checkpoint_create.add_argument(
        "--completed",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="完成状态（默认 True；--no-completed 构造未完成恢复点——R6-21）",
    )

    # Story 6-6: checkpoint-list/checkpoint-show/checkpoint-recover 扁平子命令族
    # （Checkpoint 摘要查看与恢复——审批面三入口；扁平族先例 R2-F18 维持；
    # recover 的四 --correction-* 参数成组约束在 post-parse 检测（CLI 层唯一
    # 落位——CorrectionRecord 默认值兜底下部分出现在用例层不可表达，AC-2 裁定））
    checkpoint_list = subparsers.add_parser(
        "checkpoint-list",
        help="查看 plan 下全部 Checkpoint 摘要清单（8 键+sync 状态——Story 6-6）",
    )
    checkpoint_list.add_argument(
        "--plan-id",
        type=str,
        required=True,
        metavar="PLAN_ID",
        help="规划任务标识（UUID 字符串）",
    )

    checkpoint_show = subparsers.add_parser(
        "checkpoint-show",
        help="查看单点 Checkpoint 恢复视图（9 键——修正面乐观锁基线随附）",
    )
    checkpoint_show.add_argument(
        "--plan-id",
        type=str,
        required=True,
        metavar="PLAN_ID",
        help="规划任务标识（UUID 字符串）",
    )
    checkpoint_show.add_argument(
        "--checkpoint-no",
        type=str,
        required=True,
        metavar="CP_NO",
        help='恢复起点检查点编号（"CP-1".."CP-8"）',
    )

    checkpoint_recover = subparsers.add_parser(
        "checkpoint-recover",
        help="恢复执行（无 --confirm 输出影响评估 dry-run；带 --confirm 执行双模式恢复）",
    )
    checkpoint_recover.add_argument(
        "--plan-id",
        type=str,
        required=True,
        metavar="PLAN_ID",
        help="规划任务标识（UUID 字符串）",
    )
    checkpoint_recover.add_argument(
        "--checkpoint-no",
        type=str,
        required=True,
        metavar="CP_NO",
        help='恢复起点检查点编号（"CP-1".."CP-8"）',
    )
    checkpoint_recover.add_argument(
        "--correction-type",
        type=str,
        default=None,
        metavar="TYPE",
        help="关键参数修正类型（四 --correction-* 参数成组提供）",
    )
    checkpoint_recover.add_argument(
        "--previous-value",
        type=str,
        default=None,
        metavar="OLD",
        help="修正前值（四 --correction-* 参数成组提供）",
    )
    checkpoint_recover.add_argument(
        "--new-value",
        type=str,
        default=None,
        metavar="NEW",
        help="修正后值（四 --correction-* 参数成组提供）",
    )
    checkpoint_recover.add_argument(
        "--applied-by",
        type=str,
        default=None,
        metavar="APPLIER",
        help="修正人（四 --correction-* 参数成组提供；--confirmed-by 缺省链兜底）",
    )
    checkpoint_recover.add_argument(
        "--mode",
        type=str,
        choices=("replay", "override"),
        default=None,
        metavar="MODE",
        help="显式恢复模式（缺省取引擎建议；建议 replay 而请求 override 将被 487 拒绝）",
    )
    checkpoint_recover.add_argument(
        "--confirm",
        action="store_true",
        help="确认执行（缺省为 dry-run 影响评估——不调引擎三零）",
    )
    checkpoint_recover.add_argument(
        "--confirmed-by",
        type=str,
        default=None,
        metavar="APPROVER",
        help="审批人标识（confirm 路径必填；缺省取 --applied-by）",
    )

    # Story 6-7: trace-tree 扁平子命令（溯源树四层展示——CLI 分析视入口；
    # --depth choices 用 str 元组（仓内先例均 str 元组——--format/--mode）+
    # runner 内 int 转换（DR3-7/DR1-22）；CLI 面越域由 argparse 拦截 exit 2
    # 不走 242——与用例层守卫分工钦定（API 契约节/AC-6））
    trace_tree = subparsers.add_parser(
        "trace-tree",
        help="溯源树四层展示（结论→分析→数据切片→原始文档——Story 6-7）",
    )
    trace_tree.add_argument(
        "--plan-id",
        type=str,
        required=True,
        metavar="PLAN_ID",
        help="规划任务标识（UUID 字符串）",
    )
    trace_tree.add_argument(
        "--depth",
        type=str,
        choices=("1", "2", "3", "4"),
        default="4",
        metavar="DEPTH",
        help="展开深度（1=仅结论层/2=+分析层/3=+切片层/4=+文档层；默认 4 全树）",
    )
    trace_tree.add_argument(
        "--stage",
        type=str,
        default=None,
        metavar="STAGE",
        help="客户端按 stage 过滤展示（按 --depth 构建后过滤；保留结论层行）",
    )

    # Story 6-8: executive-view 扁平子命令（高管简化视图四段聚合+RAG 三色——
    # CLI 高管速览入口；--plan-id 必填单参数零可选（YAGNI：审计窗/输出形态均
    # 服务常量钉死——AC-6 钦定）
    executive_view = subparsers.add_parser(
        "executive-view",
        help="高管简化视图（规划态势/审批中心/审计摘要/报告可得性四段+三色健康——Story 6-8）",
    )
    executive_view.add_argument(
        "--plan-id",
        type=str,
        required=True,
        metavar="PLAN_ID",
        help="规划任务标识（UUID 字符串）",
    )

    # Story 6-9: analyst-view 扁平子命令（分析师视图三段聚合——工具箱/进度/溯源；
    # CLI 分析师作业入口；--plan-id 必填单参数零可选（YAGNI：无格式/分类过滤
    # 参数需求来源，输出形态服务常量钉死——6-8 同款裁定）
    analyst_view = subparsers.add_parser(
        "analyst-view",
        help="分析师视图（专业工具箱/BLM 六阶段进度/溯源摘要三段聚合——Story 6-9）",
    )
    analyst_view.add_argument(
        "--plan-id",
        type=str,
        required=True,
        metavar="PLAN_ID",
        help="规划任务标识（UUID 字符串）",
    )

    # Story 6-10: consultant-view 扁平子命令（顾问视图三段聚合——多项目/品牌/导出；
    # CLI 顾问交付入口；零参数面真空（CLI 族首个无参数定义命令：多项目面板本义
    # 跨 plan，无过滤/分页需求来源——YAGNI；与 isolation-logs 的可选过滤面分立）
    subparsers.add_parser(
        "consultant-view",
        help="顾问视图（多项目概况/品牌配置状态/白标导出概况三段聚合——Story 6-10）",
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

    # Story 6-11: 品牌模板配置两命令（白标报告基础——预设配色 3 套×字体 2 项
    # 的可保存可复用模板；模板名是业务键非 UUID——非空/长度校验在服务预检与
    # 实体守卫承载，CLI 面零 UUID 守卫）
    brand_template_save = subparsers.add_parser(
        "brand-template-save",
        help="保存品牌模板（配色/字体预设+可选 Logo——同名再存为修订覆盖，Story 6-11）",
    )
    brand_template_save.add_argument(
        "--name",
        type=str,
        required=True,
        metavar="NAME",
        help="模板名（业务键——同名再存为修订覆盖非冲突）",
    )
    brand_template_save.add_argument(
        "--color-scheme",
        type=str,
        required=True,
        choices=("corporate-blue", "graphite", "burgundy"),
        metavar="KEY",
        help="配色预设键（corporate-blue 商务蓝/graphite 石墨灰/burgundy 酒红——每套 5 色）",
    )
    brand_template_save.add_argument(
        "--font-preset",
        type=str,
        required=True,
        choices=("stsong", "noto-sans-sc"),
        metavar="KEY",
        help="字体预设键（stsong 内置宋体/noto-sans-sc 黑体 TTF）",
    )
    brand_template_save.add_argument(
        "--logo-path",
        type=str,
        required=False,
        default=None,
        metavar="PATH",
        help="本地 Logo 图片路径（可选 PNG/JPEG ≤2MB——缺省保留既有 Logo）",
    )
    subparsers.add_parser(
        "brand-template-list",
        help="品牌模板清单（全局配置——最新修订优先排序，Story 6-11）",
    )
    return parser


async def _close_connection_pools() -> None:
    """关闭已实例化的连接池（Redis/PostgreSQL——若存在），关闭失败仅记日志不抛。

    agent_cli 是首个打开 Redis 池的 CLI（instantiate 经仓储读写；ocr_cli 不
    触碰 Redis）；load-profile 侧 event_publisher → outbox 链路会实例化 PG
    engine（RELIABLE 事件落 outbox 表）——退出不关均留 ResourceWarning
    （R1-F7 对称清理）。仅关闭已实例化的 manager（peek 不触发懒实例化）；
    禁用全量 shutdown()——它会在退出路径惰性实例化未触达的 manager。Qdrant/
    Neo4j 面（R3-F2）：run 链（blm_planning→hybrid_search→dense/sparse→l3_vector
    →qdrant；graph_search→l5_graph→neo4j）与 trace-tree 链（l3_vector→qdrant）
    均在构造期急切实例化对应 manager——两 manager 入列关闭（peek 未实例化者
    no-op；QdrantManager.close 判空自愈、Neo4jManager 构造注入 driver 恒可关）。

    逐 manager 独立 try/except：一处关闭失败不跳过另一处（Redis 失败仍关
    PG）。本方法在 finally 中调用：关闭异常（如断连超时）若上抛会反噬主
    结果——实例化成功被误报 exit 1、失败路径丢失根因异常，故内部消化记
    warning（对齐 run_tool_chain 发布失败「记日志不回滚」先例的防御面收窄）。
    """
    for manager_name in (
        "redis_connection_manager",
        "postgresql_connection_manager",
        "qdrant_connection_manager",
        "neo4j_connection_manager",
    ):
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


def _task_controller(agent_id_raw: str, task: str, dry_run: bool = False) -> Any:
    """run-task controller（守卫→dry_run 分叉→幂等 bootstrap→异步执行——OD-14/OD-12）。

    dry_run=True 返回动作清单（守卫后、bootstrap 前短路——零 resolve 零副作用）；
    False 返回工作流 result（json/table 渲染源——禁经 ``_print_*``）。

    Args:
        agent_id_raw: --agent-id 原始字符串
        task: --task 原始字符串
        dry_run: --dry-run 旗标（client 语义）

    Returns:
        动作清单（dry_run）或工作流 result

    Raises:
        ValidationError: 201——非法 agent_id（守卫先于一切 IO）
    """
    agent_id = _parse_agent_uuid(agent_id_raw)
    if dry_run:
        return [f"将派发任务至 Agent {agent_id}: {task!r}"]
    _ensure_bootstrapped()
    return asyncio.run(_run_task(agent_id, task))


def _run_task_cli(agent_id_raw: str, task: str) -> int:
    """run-task 子命令执行（controller+``_print`` 薄壳——Story 7-1 OD-14 抽取形态）。

    退出码契约（CLI 契约定稿）：成功与失败完成态均 exit 0（工作流正常走完
    语义——status 可观测锚点在摘要输出）；443/441/444/445 等业务异常 exit 1。

    Args:
        agent_id_raw: --agent-id 原始字符串
        task: --task 原始字符串

    Returns:
        退出码（0=工作流正常走完（含失败完成态），1=业务异常）
    """
    try:
        result = _task_controller(agent_id_raw, task)
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


async def _run_blm_planning(agent_id: uuid_module.UUID, task: str, plan_id: str | None) -> object:
    """执行 BLM 前两阶段规划并清理连接池（Story 6-1——阻塞执行到终态）。"""
    use_case = resolve("blm_planning_use_case")
    try:
        return await use_case.execute(agent_id=agent_id, task=task, plan_id=plan_id)
    finally:
        await _close_connection_pools()


def _print_blm_progress(result: object) -> None:
    """输出 BLM 规划多行进度摘要（stdout——AC-3 CLI 进度数据面）。

    规划标识 + 阶段 1 四字段概要 + 六子步骤计数 + 综合结论 + 降级清单
    （降级可见性——AC-6③）+ 耗时（getattr 属性访问避免 import 依赖——
    _print_workflow_summary 先例模式）。

    Args:
        result: BlmPlanningResult（属性访问面）
    """
    print(f"规划任务: {getattr(result, 'plan_id')}")
    gap = getattr(result, "gap_artifacts")
    print(f"阶段 1 业绩差距分析: {getattr(gap, 'financial_gap', '')}")
    print(f"  运营差距: {getattr(gap, 'operational_gap', '')}")
    print(f"  根因: {'；'.join(getattr(gap, 'root_causes', ()))}")
    print(f"  组合健康度: {getattr(gap, 'portfolio_health', '')}")
    insight_steps = getattr(result, "insight_steps", ())
    print(f"阶段 2 市场洞察: {len(insight_steps)}/6 子步骤完成")
    synthesis = getattr(result, "synthesis")
    conclusions = getattr(synthesis, "conclusions", ())
    if conclusions:
        print(f"综合洞察: {conclusions[0]}{' …' if len(conclusions) > 1 else ''}")
    degraded_steps = getattr(result, "degraded_steps", ())
    if degraded_steps:
        print(f"降级步骤（{len(degraded_steps)}）: {', '.join(degraded_steps)}")
    # 6-4 思维链归档汇总行（三段式口径 R2-F8——「成功 N/失败 M/预期 8」，
    # 分母 8 使组装缺席 K=8-N-M 可推算；零静默吞错——archived 台账可见）
    chain_records = getattr(result, "chain_records", ()) or ()
    if chain_records:
        success_count = sum(1 for record in chain_records if getattr(record, "archived", False))
        failed_count = len(chain_records) - success_count
        print(f"思维链归档: 成功 {success_count}/失败 {failed_count}/预期 8")
    print(f"耗时: {getattr(result, 'execution_ms')}ms")


def _run_blm_plan_cli(agent_id_raw: str, task: str, plan_id: str | None) -> int:
    """blm-plan 子命令执行（守卫 → bootstrap → 执行 → 进度摘要输出）。

    退出码契约（对齐 run-task）：成功 exit 0（降级步骤在摘要中显式标注）；
    443/441/447/481 等业务异常 exit 1。

    Args:
        agent_id_raw: --agent-id 原始字符串
        task: --task 原始字符串
        plan_id: --plan-id 可选透传（缺省 None——用例内新铸）

    Returns:
        退出码（0=规划正常完成（含部分降级），1=业务异常）
    """
    try:
        result = _blm_plan_controller(agent_id_raw, task, plan_id)
        _print_blm_progress(result)
        logger.info(
            "BLM 规划执行完成: plan_id=%s degraded=%d",
            getattr(result, "plan_id"),
            len(getattr(result, "degraded_steps", ())),
        )
        return 0
    except DomainError as error:
        logger.error("BLM 规划执行失败: %s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1
    except Exception as error:
        logger.error("BLM 规划执行异常: %s", error, exc_info=True)
        return 1


def _blm_plan_controller(agent_id_raw: str, task: str, plan_id: str | None, dry_run: bool = False) -> Any:
    """blm-plan controller（守卫→dry_run 分叉→幂等 bootstrap→异步执行——OD-14/OD-12）。

    Args:
        agent_id_raw: --agent-id 原始字符串
        task: --task 原始字符串
        plan_id: --plan-id 可选（缺省 None——用例内新铸；传入时经 canonical
            守卫归一——plan_id 命令族第十处收口[6.9-R1-DF1 同族补齐]）
        dry_run: --dry-run 旗标（client 语义——动作清单零 resolve）

    Returns:
        动作清单（dry_run）或规划 result

    Raises:
        ValidationError: 201——非法 agent_id（守卫先于 bootstrap）
        EntityValidationError: 242——非法 plan_id（canonical 守卫归一）
    """
    agent_id = _parse_agent_uuid(agent_id_raw)
    if plan_id is not None:
        plan_id = _validate_plan_uuid(plan_id, "blm-plan")
    if dry_run:
        return [f"将执行 BLM 规划（Agent {agent_id}，plan_id={plan_id or '自动生成'}）"]
    _ensure_bootstrapped()
    return asyncio.run(_run_blm_planning(agent_id, task, plan_id))


async def _run_checkpoint_create(
    plan_id: str,
    checkpoint_no: str,
    stage_id: str,
    query: str,
    user_id: str,
    summary: str,
    completed: bool,
) -> object:
    """执行 Checkpoint 创建用例（resolve → execute；连接池 finally 关闭）。

    Args:
        plan_id: 规划任务标识（UUID 字符串——CLI 守卫已校验）。
        checkpoint_no: 检查点编号。
        stage_id: 阶段标识。
        query: 原始查询文本。
        user_id: 执行用户标识。
        summary: 阶段摘要。
        completed: 完成状态。

    Returns:
        已落库的完整形态快照。
    """
    use_case = resolve("checkpoint_use_case")
    try:
        return await use_case.execute(
            plan_id=plan_id,
            checkpoint_no=checkpoint_no,
            stage_id=stage_id,
            query=query,
            retrieved_docs=[],  # argparse 不接收检索证据（空列表构造——实体抽取降级容忍）
            user_id=user_id,
            summary=summary,
            completed=completed,
            created_via="cli",  # R6-4 钦定：CLI 入口硬编码传值（不暴露参数）
        )
    finally:
        await _close_connection_pools()


def _print_checkpoint_result(result: object) -> None:
    """打印 Checkpoint 创建结果摘要（getattr 属性访问——与 _print_blm_progress 同风格）。

    Args:
        result: 完整形态快照实体。
    """
    print("Checkpoint 创建完成：")
    print(f"  checkpoint_no: {getattr(result, 'checkpoint_no', '')}")
    print(f"  session_id: {getattr(result, 'session_id', '')}")
    print(f"  stage_id: {getattr(result, 'stage_id', '')}")
    print(f"  state_version: {getattr(result, 'state_version', 0)}")
    print(f"  TTL: {getattr(result, 'ttl_seconds', 0)} 秒（30 天）")


async def _run_chain_trace(plan_id: str, include_blob: bool) -> object:
    """执行决策追溯查询（resolve 用例——与 _run_checkpoint_create 同款资源收尾）。

    Args:
        plan_id: 规划任务标识。
        include_blob: 是否深度解引用 L4 WORM blob。

    Returns:
        ChainOfThoughtTraceView 追溯视图。
    """
    use_case = resolve("blm_chain_trace_use_case")
    try:
        return await use_case.execute(plan_id=plan_id, include_blob=include_blob)
    finally:
        await _close_connection_pools()


async def _run_report_generate(
    plan_id: str,
    report_format: str = "markdown",
    brand_template: str | None = None,
) -> object:
    """执行报告生成（按 format 分发 resolve 两用例——与 _run_chain_trace 同款资源收尾）。

    Args:
        plan_id: 规划任务标识。
        report_format: 报告格式（markdown→report_generation_use_case /
            pdf→pdf_report_generation_use_case——OD-11 单入口分发表）。
        brand_template: 品牌模板名（可选——6-11 仅 pdf 分支透传 use case
            brand_template_name；组合守卫已在 CLI 执行层拦截非法组合）。

    Returns:
        StrategicReport 报告实体。
    """
    # 分发显式两分支（resolve 端口名字面保留——架构测试 CLI resolve 形态守护）
    use_case = resolve("pdf_report_generation_use_case") if report_format == "pdf" else resolve("report_generation_use_case")
    try:
        if brand_template is not None:
            return await use_case.execute(plan_id=plan_id, brand_template_name=brand_template)
        return await use_case.execute(plan_id=plan_id)
    finally:
        await _close_connection_pools()


def _print_chain_trace(view: object) -> None:
    """打印决策追溯结果（每条 to_display 五段形态——DC-2 展示用标签）。

    Args:
        view: ChainOfThoughtTraceView（getattr 属性访问——stub 替身兼容）。
    """
    records = getattr(view, "records", []) or []
    print(f"决策追溯查询: 共 {getattr(view, 'total', 0)} 条思维链档案（归档成功 {getattr(view, 'archived_count', 0)}）")
    for record in records:
        stage = record.get("stage", "")
        archive_id = record.get("archive_id", "")
        degraded_marker = "（降级）" if record.get("degraded") else ""
        print(f"--- {stage}{degraded_marker} [archive_id={archive_id}] ---")
        print(record.get("chain").to_display())
        blob_content = record.get("blob_content")
        if blob_content is not None:
            print(f"（WORM blob 深度解引用: stage={blob_content.get('stage', '')}）")


def _run_chain_query_cli(plan_id: str, include_blob: bool) -> int:
    """chain-query 子命令执行（五步定式——checkpoint-create 先例）。

    exit 0 判据 = 查询面返回（空清单亦是合法答案——查询面幂等读语义，
    与恢复面 480 语义分立）；plan_id 非 UUID → 守卫 exit 1（构造真实
    EntityValidationError——R1-F18 统一形态）。

    Args:
        plan_id: --plan-id 原始字符串（UUID 守卫先于 bootstrap）。
        include_blob: --include-blob 旗标（默认 False）。

    Returns:
        退出码（0=查询返回（含空清单），1=业务异常/参数守卫失败）。
    """
    try:
        plan_id = _validate_plan_uuid(plan_id, "chain-query")
    except EntityValidationError as error:
        logger.error("决策追溯查询失败（参数守卫）: %s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1

    try:
        _ensure_bootstrapped()
        result = asyncio.run(_run_chain_trace(plan_id, include_blob))
        _print_chain_trace(result)
        logger.info("决策追溯查询完成: plan_id=%s total=%s", plan_id, getattr(result, "total", 0))
        return 0
    except DomainError as error:
        logger.error("决策追溯查询失败: %s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1
    except Exception as error:
        # CR2-F1：读路径兜底（fallback 打开后失败信封不再恒为 DomainError 族——
        # DB 宕机时 find 的原生 OperationalError 透传，对齐同文件两先例形态：
        # 仅 logger.error（exc_info 带堆栈）+ return 1，无 stderr print）。
        logger.error("决策追溯查询异常: %s", error, exc_info=True)
        return 1


def _print_report_summary(
    result: object,
    report_format: str = "markdown",
    *,
    brand_template_name: str | None = None,
) -> None:
    """打印报告生成摘要（format 感知+品牌增量行——markdown 分支含 memory_id，PDF 分支含对象键+bucket）。

    memory_id 打印（R2-10，仅 markdown 分支）：人类用户经 memory_id +
    L0StoragePort.read 或 base 目录提示定位物理文件；PDF 分支 file_path 是
    L4 对象键逻辑路径（``.md`` 反解不适用——6-5b format 感知扩展），定位
    信息 = 对象键 + bucket（bucket 自端口常量 import——实体不携 bucket 字段）。
    6-11 品牌增量行：brand 参在场时打印「品牌模板: {name}（已应用）」
    （brand_template_name keyword-only——None 零品牌行，既有输出零变化）。

    Args:
        result: StrategicReport 实体（getattr 属性面消费——零实体 import 依赖）。
        report_format: 报告格式（markdown/pdf——分发方透传）。
        brand_template_name: 品牌模板名（可选——在场打印品牌增量行）。
    """
    file_path = str(getattr(result, "file_path", ""))
    print("报告生成完成：")
    print(f"  报告标识: {getattr(result, 'report_id', '')}")
    # CR1-F9：report_type 是 ReportType 枚举成员——f-string 直渲染为
    # 「ReportType.MARKDOWN」repr；二级 .value 取值（枚举与裸 str 双形态
    # 均输出 "markdown"），保 CLI 零 import 依赖
    report_type_value = getattr(getattr(result, "report_type", None), "value", getattr(result, "report_type", ""))
    print(f"  报告类型: {report_type_value}")
    print(f"  逻辑路径: {file_path}")
    if report_format == "pdf":
        # PDF 分支：对象键 + bucket 定位（L4 WORM）。引文计数经 L2 metadata
        # 可查（citation_count/citations 键）——实体是 6-5a 冻结面八字段不携
        # 该值，CLI 打印面不重复呈现（R3-1：删除恒 0 的 getattr 死指标行）
        from src.application.ports.pdf_report import EVIDENCE_BUCKET_TYPE

        print(f"  存储桶: {EVIDENCE_BUCKET_TYPE}")
    else:
        memory_id = file_path.rsplit("/", 1)[-1].removesuffix(".md") if file_path else ""
        print(f"  memory_id: {memory_id}")
    if brand_template_name is not None:
        print(f"  品牌模板: {brand_template_name}（已应用）")
    print(f"  正文章节数: {getattr(result, 'section_count', 0)}（降级 {getattr(result, 'degraded_section_count', 0)}）")
    print(f"  生成耗时: {getattr(result, 'generation_ms', 0)} ms")


def _report_generate_controller(
    plan_id: str,
    report_format: str = "markdown",
    brand_template: str | None = None,
    dry_run: bool = False,
) -> Any:
    """report-generate controller（守卫族→dry_run 分叉→幂等 bootstrap→异步执行——OD-14/OD-12）。

    守卫序：组合守卫 494（brand×format）先于 UUID 守卫（既有顺序保持）；
    report_format 值域 242 插于两者之间（R1-F3——统一面无 argparse choices，
    controller 层补值域防 ``== "pdf"`` 二值分发静默落 markdown）。

    Args:
        plan_id: --plan-id 原始字符串
        report_format: --report-format 值（markdown/pdf——Typer 面拆分 OD-13）
        brand_template: --brand-template 值（仅 pdf 组合合法）
        dry_run: --dry-run 旗标（client 语义——产物写入型动作清单）

    Returns:
        动作清单（dry_run）或报告生成 result

    Raises:
        BrandTemplateValidationError: 494——brand_template 与非 pdf 组合
        EntityValidationError: 242——report_format 值域外 / 非法 plan_id
    """
    if brand_template is not None and report_format != "pdf":
        from src.domain.exceptions import BrandTemplateValidationError

        raise BrandTemplateValidationError(
            field="parameter_combination",
            message="品牌模板应用仅支持 PDF 导出（--brand-template 需与 --report-format pdf 组合；兼容入口 --format pdf）",
            context_extra={"template_name": brand_template, "reason": "参数组合非法"},
        )
    if report_format not in ("markdown", "pdf"):
        raise EntityValidationError(
            message=f"--report-format 值域非法（markdown|pdf）: {report_format!r}",
            context={"command": "report-generate", "field": "report_format", "report_format": report_format},
        )
    plan_id = _validate_plan_uuid(plan_id, "report-generate")
    if dry_run:
        return [f"将生成 {report_format} 报告并写 L0/L2（plan_id={plan_id}）"]
    _ensure_bootstrapped()
    return asyncio.run(_run_report_generate(plan_id, report_format, brand_template))


def _run_report_generate_cli(
    plan_id: str,
    report_format: str = "markdown",
    brand_template: str | None = None,
) -> int:
    """report-generate 子命令执行（controller+``_print`` 薄壳——Story 7-1 OD-14 抽取形态）。

    exit 0 判据 = 报告生成返回（持久化已落盘+事件已发布——宽容语义）；
    plan_id 非 UUID → 守卫 exit 1；``--brand-template`` 携带且 ``--format
    markdown`` → 组合守卫 494（post-parse 检测归 CLI 层唯一落位[checkpoint-recover
    成组约束先例]——bootstrap 前先于用例零调用）；490~493/494
    DomainError → [code] stderr exit 1（双层异常定式）。

    Args:
        plan_id: --plan-id 原始字符串（UUID 守卫先于 bootstrap）。
        report_format: --format 值（markdown/pdf——分发透传，默认 markdown）。
        brand_template: --brand-template 值（可选品牌模板名——仅 pdf 组合合法）。

    Returns:
        退出码（0=报告生成完成，1=业务异常/参数守卫失败）。
    """
    try:
        result = _report_generate_controller(plan_id, report_format, brand_template)
        _print_report_summary(result, report_format, brand_template_name=brand_template)
        logger.info(
            "报告生成完成: plan_id=%s report_id=%s format=%s brand_template=%s",
            plan_id,
            getattr(result, "report_id", ""),
            report_format,
            brand_template or "-",
        )
        return 0
    except DomainError as error:
        logger.error("报告生成失败: %s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1
    except Exception as error:
        logger.error("报告生成异常: %s", error, exc_info=True)
        return 1


async def _run_brand_template_save(
    name: str,
    color_scheme: str,
    font_preset: str,
    logo_path: str | None = None,
) -> object:
    """执行品牌模板保存（resolve 用例——与 _run_report_generate 同款资源收尾）。

    Args:
        name: 模板名（业务键）。
        color_scheme: 配色预设键。
        font_preset: 字体预设键。
        logo_path: 本地 Logo 路径（可选）。

    Returns:
        BrandTemplate 模板实体。
    """
    use_case = resolve("save_brand_template_use_case")
    try:
        return await use_case.execute(
            name=name,
            color_scheme=color_scheme,
            font_preset=font_preset,
            logo_path=logo_path,
        )
    finally:
        await _close_connection_pools()


async def _run_brand_template_list() -> object:
    """执行品牌模板清单查询（resolve 用例——零参全局清单）。

    Returns:
        模板实体元组。
    """
    use_case = resolve("list_brand_templates_use_case")
    try:
        return await use_case.execute()
    finally:
        await _close_connection_pools()


def _print_brand_template_saved(result: object) -> None:
    """打印保存成功摘要（输出即契约——保存行+配置行+模板标识行）。

    呈现名经预设常量单源映射（COLOR_SCHEME_PRESETS/FONT_PRESETS 的
    display_name——CLI import application ports 合法）；脏键防御回落原值。
    """
    from src.application.ports.brand_template import COLOR_SCHEME_PRESETS, FONT_PRESETS

    name = str(getattr(result, "name", ""))
    color_preset = COLOR_SCHEME_PRESETS.get(str(getattr(result, "color_scheme", "")))
    font_preset = FONT_PRESETS.get(str(getattr(result, "font_preset", "")))
    color_display = color_preset.display_name if color_preset else str(getattr(result, "color_scheme", ""))
    font_display = font_preset.display_name if font_preset else str(getattr(result, "font_preset", ""))
    logo_state = "已上传" if getattr(result, "logo_object_key", None) else "未设置"
    print(f"品牌模板已保存: {name}")
    print(f"  配色: {color_display} | 字体: {font_display} | Logo: {logo_state}")
    print(f"  模板标识: {getattr(result, 'template_id', '')}")


def _print_brand_template_list(rows: object) -> None:
    """打印模板清单（首行计数+逐模板行+空态提示行——行序由服务承载）。

    行格式：``  {name} | 配色: {呈现名} | 字体: {呈现名} | Logo: {已配置|未设置}
    | 更新: {YYYY-MM-DD HH:MM}``；空态后恒在提示行指向 brand-template-save
    （与 6-10 :1806 提示行形态对齐）。
    """
    from src.application.ports.brand_template import COLOR_SCHEME_PRESETS, FONT_PRESETS

    templates: list[Any] = list(rows) if isinstance(rows, (list, tuple)) else []
    print(f"品牌模板: 共 {len(templates)} 个")
    for template in templates:
        color_preset = COLOR_SCHEME_PRESETS.get(str(getattr(template, "color_scheme", "")))
        font_preset = FONT_PRESETS.get(str(getattr(template, "font_preset", "")))
        color_display = color_preset.display_name if color_preset else str(getattr(template, "color_scheme", ""))
        font_display = font_preset.display_name if font_preset else str(getattr(template, "font_preset", ""))
        logo_state = "已配置" if getattr(template, "logo_object_key", None) else "未设置"
        updated_at = getattr(template, "updated_at", None)
        updated_display = updated_at.strftime("%Y-%m-%d %H:%M") if updated_at else "-"
        print(
            f"  {getattr(template, 'name', '')} | 配色: {color_display}"
            f" | 字体: {font_display} | Logo: {logo_state} | 更新: {updated_display}"
        )
    print("提示: 执行 brand-template-save 配置品牌模板")


def _run_brand_template_save_cli(
    name: str,
    color_scheme: str,
    font_preset: str,
    logo_path: str | None = None,
) -> int:
    """brand-template-save 子命令执行（四步定式——写命令无 UUID 守卫步：
    模板名非 UUID 参数，非空/长度校验在服务预检与实体守卫承载）。

    Args:
        name: --name 原始字符串。
        color_scheme: --color-scheme 预设键（argparse choices 已拦非法值）。
        font_preset: --font-preset 预设键。
        logo_path: --logo-path 路径（可选）。

    Returns:
        退出码（0=保存完成，1=业务异常）。
    """
    try:
        _ensure_bootstrapped()
        result = asyncio.run(_run_brand_template_save(name, color_scheme, font_preset, logo_path))
        _print_brand_template_saved(result)
        logger.info("品牌模板已保存: name=%s color_scheme=%s font_preset=%s", name, color_scheme, font_preset)
        return 0
    except DomainError as error:
        logger.error("品牌模板保存失败: %s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1
    except Exception as error:
        logger.error("品牌模板保存异常: %s", error, exc_info=True)
        return 1


def _run_brand_template_list_cli() -> int:
    """brand-template-list 子命令执行（四步定式——零参数全局清单）。

    Returns:
        退出码（0=清单输出完成，1=业务异常）。
    """
    try:
        _ensure_bootstrapped()
        rows = asyncio.run(_run_brand_template_list())
        _print_brand_template_list(rows)
        row_count = len(rows) if isinstance(rows, (list, tuple)) else 0
        logger.info("品牌模板清单输出完成: %s 行", row_count)
        return 0
    except DomainError as error:
        logger.error("品牌模板清单失败: %s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1
    except Exception as error:
        logger.error("品牌模板清单异常: %s", error, exc_info=True)
        return 1


def _run_checkpoint_create_cli(
    plan_id: str,
    checkpoint_no: str,
    stage_id: str,
    query: str,
    user_id: str,
    summary: str,
    completed: bool,
) -> int:
    """checkpoint-create 子命令执行（五步定式——_run_blm_plan_cli 先例）。

    exit 0 判据 = 快照落库成功（R3-D 钦定——⑤发布降级不改变 exit code，
    仅 warning 日志；重复创建语义：MVP 允许同 checkpoint_no 重复创建=覆盖
    快照+追加归档行，correction_history 重置初始（R3-D/R6-7 已知 MVP 语义）。

    Args:
        plan_id: --plan-id 原始字符串（UUID 守卫先于 bootstrap）。
        checkpoint_no: --checkpoint-no 原始字符串。
        stage_id: --stage-id 原始字符串。
        query: --query 原始字符串。
        user_id: --user-id 原始字符串。
        summary: --summary 原始字符串。
        completed: --completed/--no-completed（默认 True）。

    Returns:
        退出码（0=快照落库成功（含发布降级），1=业务异常）。
    """
    # UUID 守卫（先于 bootstrap——argparse type= 禁 uuid.UUID 纪律；构造真实
    # EntityValidationError 走 [{code}] {message} 统一形态——与 DomainError 分支
    # 一致，R1 审查 FR-18：禁字面前缀假统一）
    try:
        plan_id = _validate_plan_uuid(plan_id, "checkpoint-create")
    except EntityValidationError as error:
        logger.error("Checkpoint 创建失败（参数守卫）: %s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1

    try:
        _ensure_bootstrapped()
        result = asyncio.run(_run_checkpoint_create(plan_id, checkpoint_no, stage_id, query, user_id, summary, completed))
        _print_checkpoint_result(result)
        logger.info(
            "Checkpoint 创建完成: plan_id=%s checkpoint_no=%s",
            plan_id,
            checkpoint_no,
        )
        return 0
    except DomainError as error:
        logger.error("Checkpoint 创建失败: %s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1
    except Exception as error:
        logger.error("Checkpoint 创建异常: %s", error, exc_info=True)
        return 1


async def _run_checkpoint_list(plan_id: str) -> list[Any]:
    """checkpoint-list 异步执行壳（resolve 清单用例——Story 6-6）。

    resolve 入 try（代码审查 R1-F17）：resolve 抛出（注册名漂移等）时 finally
    关池在同 loop 收口——bootstrap 连接池不泄漏绑死已关闭的 loop。
    """
    try:
        use_case = resolve("checkpoint_list_use_case")
        summaries: list[Any] = await use_case.execute(plan_id=plan_id)
        return summaries
    finally:
        await _close_connection_pools()


def _print_checkpoint_summary_table(summaries: list[Any]) -> None:
    """摘要清单表格打印（纯标准库动态列宽——Story 6-6 钦定新形态）。

    两遍法：max(len(header), max(len(v))) 算列宽 + str.ljust 对齐 + 表头行 +
    ` | ` 分隔（弃 ASCII 边框——值域有界全表 ≤64 字符远小于 128 行宽无需截断；
    completed 输出英文 true/false 保持单测值级断言直白——输出即契约）。
    """
    headers = ("checkpoint_no", "stage", "completed", "version", "sync_status")
    rows = [
        (
            str(getattr(summary, "checkpoint_no", "")),
            str(getattr(summary, "stage_id", "")),
            "true" if getattr(summary, "completed", False) else "false",
            str(getattr(summary, "state_version", 0)),
            str(getattr(summary, "sync_status", "")),
        )
        for summary in summaries
    ]
    widths = [
        max(len(header), *(len(row[column]) for row in rows)) if rows else len(header) for column, header in enumerate(headers)
    ]
    print(" | ".join(header.ljust(widths[column]) for column, header in enumerate(headers)))
    for row in rows:
        print(" | ".join(value.ljust(widths[column]) for column, value in enumerate(row)))


def _checkpoint_list_controller(plan_id: str, dry_run: bool = False) -> Any:
    """checkpoint-list controller（守卫→dry_run 分叉→幂等 bootstrap→异步执行——OD-14/OD-12）。

    Args:
        plan_id: --plan-id 原始字符串
        dry_run: --dry-run 旗标（client 语义——动作清单零 resolve）

    Returns:
        动作清单（dry_run）或 Checkpoint 摘要列表

    Raises:
        EntityValidationError: 242——非法 plan_id（守卫先于 bootstrap）
    """
    plan_id = _validate_plan_uuid(plan_id, "checkpoint-list")
    if dry_run:
        return [f"将查询 Checkpoint 清单（plan_id={plan_id}）"]
    _ensure_bootstrapped()
    return asyncio.run(_run_checkpoint_list(plan_id))


def _run_checkpoint_list_cli(plan_id: str) -> int:
    """checkpoint-list 子命令执行（controller+``_print`` 薄壳——Story 7-1 OD-14 抽取形态）。

    Args:
        plan_id: --plan-id 原始字符串（UUID 守卫先于 bootstrap）。

    Returns:
        退出码（0=清单查询成功（空清单亦 0——枚举面非错误），1=业务异常）。
    """
    try:
        summaries = _checkpoint_list_controller(plan_id)
        if summaries:
            _print_checkpoint_summary_table(summaries)
        else:
            print("该 plan_id 下无 Checkpoint（空清单）")
        logger.info("Checkpoint 清单查询完成: plan_id=%s 条目数=%d", plan_id, len(summaries))
        return 0
    except DomainError as error:
        logger.error("Checkpoint 清单查询失败: %s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1
    except Exception as error:
        logger.error("Checkpoint 清单查询异常: %s", error, exc_info=True)
        return 1


async def _run_checkpoint_show(plan_id: str, checkpoint_no: str) -> Any:
    """checkpoint-show 异步执行壳（resolve 既有恢复视图用例——首消费方）。

    resolve 入 try（代码审查 R1-F17——同 _run_checkpoint_list 注记）。
    """
    try:
        use_case = resolve("checkpoint_recovery_use_case")
        return await use_case.execute(plan_id=plan_id, checkpoint_no=checkpoint_no)
    finally:
        await _close_connection_pools()


def _print_checkpoint_recovery_view(view: Any) -> None:
    """恢复视图打印（9 键——getattr 形态零实体 import 依赖，6-3 先例）。"""
    print("Checkpoint 恢复视图：")
    print(f"  checkpoint_no: {getattr(view, 'checkpoint_no', '')}")
    print(f"  stage: {getattr(view, 'stage', '')}")
    print(f"  compressed_context: {getattr(view, 'compressed_context', '')[:120]}")
    print(f"  state_data keys: {sorted(getattr(view, 'state_data', {}).keys())}")
    print(f"  correction_history: {getattr(view, 'correction_history', [])}")
    print(f"  subsequent_checkpoints: {getattr(view, 'subsequent_checkpoints', [])}")
    print(f"  recommended_mode: {getattr(view, 'recommended_mode', '')}")
    print(f"  state_version: {getattr(view, 'state_version', 0)}")
    print(f"  snapshot_id: {getattr(view, 'snapshot_id', '')}")


def _run_checkpoint_show_cli(plan_id: str, checkpoint_no: str) -> int:
    """checkpoint-show 子命令执行（五步定式——resolve 既有 checkpoint_recovery_use_case）。

    Args:
        plan_id: --plan-id 原始字符串（UUID 守卫先于 bootstrap）。
        checkpoint_no: --checkpoint-no 原始字符串。

    Returns:
        退出码（0=视图查询成功，1=业务异常）。
    """
    try:
        plan_id = _validate_plan_uuid(plan_id, "checkpoint-show")
    except EntityValidationError as error:
        logger.error("Checkpoint 详情失败（参数守卫）: %s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1

    try:
        _ensure_bootstrapped()
        view = asyncio.run(_run_checkpoint_show(plan_id, checkpoint_no))
        _print_checkpoint_recovery_view(view)
        logger.info("Checkpoint 详情查询完成: plan_id=%s checkpoint_no=%s", plan_id, checkpoint_no)
        return 0
    except DomainError as error:
        logger.error("Checkpoint 详情查询失败: %s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1
    except Exception as error:
        logger.error("Checkpoint 详情查询异常: %s", error, exc_info=True)
        return 1


async def _run_trace_tree(plan_id: str, depth: int) -> Any:
    """trace-tree 异步执行壳（resolve traceability_tree_use_case——Story 6-7）。

    resolve 入 try（代码审查 R1-F17——同 _run_checkpoint_show 注记）。
    """
    try:
        use_case = resolve("traceability_tree_use_case")
        return await use_case.execute(plan_id=plan_id, depth=depth)
    finally:
        await _close_connection_pools()


def _print_traceability_tree(tree: Any, *, stage_filter: str | None = None) -> None:
    """溯源树打印（四层标签前缀「结论/分析/切片/文档」+ 逐层两级空格缩进——输出即契约）。

    纯标准库 print 形态（6-6 checkpoint-list 表格同哲学）；行序=root.children 流程
    规范序（服务已重排——DR3-1）；--stage 客户端过滤作用于 depth 构建结果且保留
    结论层行（DR3-7）；切片行 page 取 ChunkNode.page_start（DR3-7）。空树输出三分化
    （R1-F3——DR1-9 读模型诚实性）：build_degraded=True 打「⚠ 归档查询失败（已降级）」/
    total==0 打「该 plan 无思维链归档行」（total 是 kind 过滤后口径——R3-F3 精确化）/
    total>0 无分析层节点打归档对照行+成因提示（depth 折叠或 stage 越域——空结果自我
    解释是「没有数据」「拿不到数据」还是「有数据未展开」）。降级状态呈现（R3-F1——
    与 R1-F3 同族诚实性）：切片行 status≠resolved 追加 `[status 原值]` 标记
    （如 [point_missing]）、文档行 document_missing 追加 [document_missing]、
    degraded_stages 非空时对照行后打降级 stage 行——解析降级对分析视用户可见
    （标记用 status 原值非中文别名——零翻译层+值域直连 VO 契约）。getattr 形态零
    VO import 依赖（6-3 _print_checkpoint_result 先例）。
    """
    root = getattr(tree, "root", None)
    adopted = getattr(tree, "adopted_archives", 0)
    total = getattr(tree, "total_archives", 0)
    print(f"结论: {getattr(root, 'title', '')}（plan={getattr(tree, 'plan_id', '')}）")
    summary = getattr(root, "summary", "")
    if summary:
        print(f"  {summary}")
    children = getattr(root, "children", None) or ()
    if not children:
        if getattr(tree, "build_degraded", False):
            print("  ⚠ 归档查询失败（已降级）")
        elif total == 0:
            print("  该 plan 无思维链归档行")
        else:
            print(f"  归档对照: 采纳 {adopted} / 候选 {total}（无分析层节点——depth 折叠或 stage 越域）")
        return
    print(f"  归档对照: 采纳 {adopted} / 候选 {total}")
    degraded_stages = getattr(tree, "degraded_stages", None) or ()
    if degraded_stages:
        print(f"  降级 stage: {', '.join(str(stage) for stage in degraded_stages)}")
    for stage_node in children:
        stage = getattr(stage_node, "stage", "")
        if stage_filter is not None and stage != stage_filter:
            continue
        degraded_mark = " [降级]" if getattr(stage_node, "degraded", False) else ""
        print(
            f"  分析: {stage} {getattr(stage_node, 'display_name', '')}{degraded_mark}"
            f" evidence={getattr(stage_node, 'evidence_count', 0)}"
        )
        for chunk_node in getattr(stage_node, "children", None) or ():
            chunk_id = str(getattr(chunk_node, "chunk_id", ""))
            excerpt = str(getattr(chunk_node, "content_excerpt", ""))[:60]
            chunk_status = str(getattr(chunk_node, "status", "resolved"))
            chunk_mark = "" if chunk_status == "resolved" else f" [{chunk_status}]"
            print(f"    切片: {chunk_id[:8]}{chunk_mark} {excerpt} page={getattr(chunk_node, 'page_start', None)}")
            for doc_node in getattr(chunk_node, "children", None) or ():
                doc_status = str(getattr(doc_node, "status", "resolved"))
                doc_mark = "" if doc_status == "resolved" else f" [{doc_status}]"
                print(
                    f"      文档: {getattr(doc_node, 'filename', '')}{doc_mark}"
                    f" page={getattr(doc_node, 'page', None)}"
                    f" 对象={getattr(doc_node, 'bucket', '')}/{getattr(doc_node, 'object_key', None)}"
                )


def _trace_tree_controller(plan_id: str, depth: str, stage: str | None, dry_run: bool = False) -> Any:
    """trace-tree controller（守卫→dry_run 分叉→幂等 bootstrap→异步执行——OD-14/OD-12）。

    Args:
        plan_id: --plan-id 原始字符串
        depth: --depth 原始字符串（本层 int 转换——DR3-7 签名钦定）
        stage: --stage 客户端过滤参数（渲染层消费——controller 透传不使用）
        dry_run: --dry-run 旗标（client 语义——读命令退化态：守卫+动作回显）

    Returns:
        动作清单（dry_run）或追溯树 result

    Raises:
        EntityValidationError: 242——非法 plan_id
    """
    plan_id = _validate_plan_uuid(plan_id, "trace-tree")
    if dry_run:
        return [f"将查询追溯树（plan_id={plan_id} depth={depth}）"]
    _ensure_bootstrapped()
    return asyncio.run(_run_trace_tree(plan_id, int(depth)))


def _run_trace_tree_cli(plan_id: str, depth: str, stage: str | None) -> int:
    """trace-tree 子命令执行（controller+``_print`` 薄壳——Story 7-1 OD-14 抽取形态）。

    Args:
        plan_id: --plan-id 原始字符串（UUID 守卫先于 bootstrap）。
        depth: --depth 原始字符串（runner 内 int 转换——DR3-7 签名钦定）。
        stage: --stage 客户端过滤参数（缺省 None 全量展示）。

    Returns:
        退出码（0=树构建完成含空树——空树是正常态；1=业务异常；2=argparse
        用法错误由 argparse 原生承载）。
    """
    try:
        tree = _trace_tree_controller(plan_id, depth, stage)
        _print_traceability_tree(tree, stage_filter=stage)
        logger.info("溯源树查询完成: plan_id=%s depth=%s stage=%s", plan_id, depth, stage)
        return 0
    except DomainError as error:
        logger.error("溯源树查询失败: %s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1
    except Exception as error:
        logger.error("溯源树查询异常: %s", error, exc_info=True)
        return 1


# ===================================================================
# Story 6-8: executive-view 子命令（高管速览入口——五步定式+_print 四段打印）
# ===================================================================


async def _run_executive_view(plan_id: str) -> Any:
    """executive-view 异步执行壳（resolve executive_view_use_case——Story 6-8）。

    resolve 入 try（代码审查 R1-F17——同 _run_trace_tree 注记）。
    """
    try:
        use_case = resolve("executive_view_use_case")
        return await use_case.execute(plan_id=plan_id)
    finally:
        await _close_connection_pools()


def _print_executive_view(view: Any) -> None:
    """高管简化视图打印（四段分隔行+键值行——输出即契约，纯标准库 print）。

    空态行恒在纪律（6-7 空树三分化同族）：三段 available 缺席时输出空态行
    （进度 0/8/Checkpoint 共 0/最新报告无+操作提示——「指向既有命令」非新功能）；
    审计段无 available 键——total 为全局窗动态值，最近事件按样本降序头部呈现
    （无样本降「最近: 无」半行——R1-F16 钦定形态）。build_degraded 时健康行
    追加「（部分数据降级）」标记（AC-6——「拿不到数据不得报绿」的呈现面）。
    getattr 形态零 VO import 依赖（6-3 _print_checkpoint_result 先例）。
    """
    health = getattr(view, "health", None)
    health_value = getattr(health, "value", str(health))
    health_labels = {"green": "健康", "amber": "关注", "red": "危险"}
    degraded_mark = "（部分数据降级）" if getattr(view, "build_degraded", False) else ""
    print(f"高管简化视图（plan: {getattr(view, 'plan_id', '')}）")
    print(f"健康状态: {health_value}（{health_labels.get(health_value, '未知')}）{degraded_mark}")

    planning = getattr(view, "planning", None)
    print("── 规划态势 ──")
    current_step = getattr(planning, "current_step", None)
    last_activity = getattr(planning, "last_activity_at", None)
    print(
        f"进度: {getattr(planning, 'completed_steps', 0)}/{getattr(planning, 'total_steps', 8)}"
        f"（{getattr(planning, 'progress_percent', 0)}%）"
        f" | 当前: {current_step if current_step else '无'}"
        f" | 降级: {getattr(planning, 'degraded_step_count', 0)} 步"
        f" | 最近活动: {last_activity if last_activity else '无'}"
    )

    approval = getattr(view, "approval", None)
    print("── 审批中心 ──")
    print(
        f"Checkpoint: 共 {getattr(approval, 'total_checkpoints', 0)}"
        f" | 已完成 {getattr(approval, 'completed_count', 0)}"
        f" | in_sync {getattr(approval, 'in_sync_count', 0)}"
        f" | pending_sync {getattr(approval, 'pending_sync_count', 0)}"
        f" | invalidated {getattr(approval, 'invalidated_count', 0)}"
    )
    recovery_mode = getattr(approval, "last_recovery_mode", None)
    if recovery_mode:
        print(
            f"最近恢复: {recovery_mode}"
            f" by {getattr(approval, 'last_recovery_confirmed_by', '')}"
            f" at {getattr(approval, 'last_recovered_at', '')}"
        )
    else:
        print("最近恢复: 无")

    audit = getattr(view, "audit", None)
    print("── 审计摘要 ──")
    recent_events = getattr(audit, "recent_events", None) or ()
    if recent_events:
        latest_event = recent_events[0]
        print(
            f"近 {getattr(audit, 'window_days', 7)} 天事件: {getattr(audit, 'total_events', 0)}"
            f" | 最近: {getattr(latest_event, 'action_type', '')}"
            f" by {getattr(latest_event, 'actor', '')}"
            f" at {getattr(latest_event, 'timestamp', '')}"
        )
    else:
        print(f"近 {getattr(audit, 'window_days', 7)} 天事件: {getattr(audit, 'total_events', 0)} | 最近: 无")

    report = getattr(view, "report", None)
    print("── 报告 ──")
    if getattr(report, "available", False):
        print(
            f"最新报告: {getattr(report, 'report_type', '')} {getattr(report, 'file_path', '')}"
            f" | 章节 {getattr(report, 'section_count', 0)}"
            f"（降级 {getattr(report, 'degraded_section_count', 0)}）"
        )
    else:
        print("最新报告: 无（可先执行 report-generate）")


def _run_executive_view_cli(plan_id: str) -> int:
    """executive-view 子命令执行（五步定式——_run_trace_tree_cli 直系样板）。

    Args:
        plan_id: --plan-id 原始字符串（UUID 守卫先于 bootstrap）。

    Returns:
        退出码（0=视图构建完成含空态——空态是正常态；1=业务异常；2=argparse
        用法错误由 argparse 原生承载）。
    """
    try:
        plan_id = _validate_plan_uuid(plan_id, "executive-view")
    except EntityValidationError as error:
        logger.error("高管简化视图查询失败（参数守卫）: %s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1

    try:
        _ensure_bootstrapped()
        view = asyncio.run(_run_executive_view(plan_id))
        _print_executive_view(view)
        logger.info("高管简化视图查询完成: plan_id=%s", plan_id)
        return 0
    except DomainError as error:
        logger.error("高管简化视图查询失败: %s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1
    except Exception as error:
        logger.error("高管简化视图查询异常: %s", error, exc_info=True)
        return 1


# Story 6-9: analyst-view 子命令（分析师作业入口——五步定式+_print 三段打印）
# ===================================================================
async def _run_analyst_view(plan_id: str) -> Any:
    """analyst-view 异步执行壳（resolve analyst_view_use_case——Story 6-9）。

    resolve 入 try（代码审查 R1-F17——同 _run_executive_view 注记）。
    """
    try:
        use_case = resolve("analyst_view_use_case")
        return await use_case.execute(plan_id=plan_id)
    finally:
        await _close_connection_pools()


def _print_analyst_view(view: Any) -> None:
    """分析师视图打印（三段分隔行+逐工具清单+六阶段进度条——输出即契约，纯标准库 print）。

    呈现语义注记（R3-F6——AC-3 分立注记呈现面延续）：进度行=快照 int 直读口径/
    阶段行=timeline 派生口径，两口径可不一致（如快照 3/8 而六阶段合计 2/8——
    timeline 含值域外脏值时），属「快照计数 vs 派生计数」预期语义非 bug。
    进度条 10 格字符形态：k=round(step_completed/step_total*10)（10c/7 与 10
    互质无 .5 tie 面——banker's rounding 无触发面，确定性安全）；step_total==0
    时恒 10 格 ░（后四阶段规划态）；后四阶段行尾追加「（V1 交付）」注记（归
    Epic 10 Story 10-1——呈现面承载不进 status 值域）。
    段降级形态：toolbox 段降「工具清单获取失败」单行；progress 段降「进度: 无快照」
    （快照缺席与段降级同形——CLI 面不区分两层）；溯源统计行恒在（空态全 0 形态）。
    getattr 形态零 VO import 依赖（6-3/6-8 先例）。
    """
    degraded_mark = "（部分数据降级）" if getattr(view, "build_degraded", False) else ""
    print(f"分析师视图（plan: {getattr(view, 'plan_id', '')}）{degraded_mark}")

    toolbox = getattr(view, "toolbox", None)
    print("── 专业工具箱 ──")
    if getattr(toolbox, "degraded", False):
        print("工具清单获取失败")
    else:
        categories = getattr(toolbox, "categories", None) or ()
        category_text = " ".join(
            f"{getattr(category, 'category', '')}×{getattr(category, 'tool_count', 0)}" for category in categories
        )
        print(f"工具: 共 {getattr(toolbox, 'total_tools', 0)} 种（ACTIVE） | 分类: {category_text}")
        for tool in getattr(toolbox, "tools", None) or ():
            print(f"  {getattr(tool, 'slug', '')} — {getattr(tool, 'tool_name', '')}（{getattr(tool, 'category', '')}）")

    progress = getattr(view, "progress", None)
    print("── BLM 进度 ──")
    if not getattr(progress, "available", False):
        print("进度: 无快照")
    else:
        current_step = getattr(progress, "current_step", None)
        print(
            f"进度: {getattr(progress, 'completed_steps', 0)}/{getattr(progress, 'total_steps', 0)}"
            f"（{getattr(progress, 'progress_percent', 0)}%）"
            f" | 当前: {current_step if current_step else '无'}"
            f" | 降级: {getattr(progress, 'degraded_step_count', 0)} 步"
        )
    status_labels = {"completed": "已完成", "in_progress": "进行中", "not_started": "未启动"}
    for index, stage in enumerate(getattr(progress, "stages", None) or (), start=1):
        step_total = getattr(stage, "step_total", 0)
        step_completed = getattr(stage, "step_completed", 0)
        filled = round(step_completed / step_total * 10) if step_total > 0 else 0
        bar = "█" * filled + "░" * (10 - filled)
        status = getattr(stage, "status", None)
        status_value = getattr(status, "value", str(status))
        v1_mark = "（V1 交付）" if step_total == 0 else ""
        print(
            f"  {index}. {getattr(stage, 'phase_name', '')}: [{bar}]"
            f" {status_labels.get(status_value, status_value)}（{step_completed}/{step_total}）{v1_mark}"
        )

    traceability = getattr(view, "traceability", None)
    print("── 溯源摘要 ──")
    tree_mark = "（部分树数据降级）" if getattr(traceability, "tree_build_degraded", False) else ""
    print(
        f"分析: {getattr(traceability, 'stage_count', 0)} | 切片: {getattr(traceability, 'chunk_count', 0)}"
        f" | 文档: {getattr(traceability, 'document_count', 0)}"
        f" | 可跳转: {getattr(traceability, 'jump_ready_count', 0)}{tree_mark}"
    )
    if getattr(traceability, "degraded_stage_count", 0) > 0:
        print(f"降级 stage: {getattr(traceability, 'degraded_stage_count', 0)}")
    print(f"提示: 执行 trace-tree --plan-id {getattr(view, 'plan_id', '')} 查看完整溯源树")


def _run_analyst_view_cli(plan_id: str) -> int:
    """analyst-view 子命令执行（五步定式——_run_executive_view_cli 直系样板）。

    Args:
        plan_id: --plan-id 原始字符串（UUID 守卫先于 bootstrap）。

    Returns:
        退出码（0=视图构建完成含空态——空态是正常态；1=业务异常；2=argparse
        用法错误由 argparse 原生承载）。
    """
    try:
        plan_id = _validate_plan_uuid(plan_id, "analyst-view")
    except EntityValidationError as error:
        logger.error("分析师视图查询失败（参数守卫）: %s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1

    try:
        _ensure_bootstrapped()
        view = asyncio.run(_run_analyst_view(plan_id))
        _print_analyst_view(view)
        logger.info("分析师视图查询完成: plan_id=%s", plan_id)
        return 0
    except DomainError as error:
        logger.error("分析师视图查询失败: %s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1
    except Exception as error:
        logger.error("分析师视图查询异常: %s", error, exc_info=True)
        return 1


# ===================================================================
# Story 6-10: consultant-view 子命令（顾问交付入口——零参数全局视图+三段打印）
# ===================================================================
async def _run_consultant_view() -> Any:
    """consultant-view 异步执行壳（resolve consultant_view_use_case——Story 6-10）。

    resolve 入 try（同 _run_analyst_view 注记）：resolve 抛出（注册名漂移等）时
    finally 仍关闭连接池。
    """
    try:
        use_case = resolve("consultant_view_use_case")
        return await use_case.execute()
    finally:
        await _close_connection_pools()


def _print_consultant_view(view: Any) -> None:
    """顾问视图打印（三段分隔行+逐项目两行形态+品牌两行+导出定位——输出即契约，纯标准库 print）。

    零参数全局面板：项目行含全库行（共享库背景行照常计入输出——CLI 呈现本义）；
    时间戳呈现 ISO 截断 %Y-%m-%d %H:%M（分钟粒度——信息密度呈现形态）；段降级
    两形态分立（OD-12 呈现面对齐）：find 级（degraded+空清单）降「项目清单获取
    失败」单行；循环级（degraded+清单保留）照常呈现清单——行报告列 None 呈现
    「最新报告: 无」+首行「（部分数据降级）」标记承载降级信号（brand 两行恒在
    ——零 IO 恒稳；export 段值级降 0/无照常呈现）。getattr 形态零 VO import
    依赖（6-3/6-8/6-9 先例）。
    """
    degraded_mark = "（部分数据降级）" if getattr(view, "build_degraded", False) else ""
    print(f"顾问视图（全局多项目面板）{degraded_mark}")

    projects_section = getattr(view, "projects", None)
    projects_rows = getattr(projects_section, "projects", None) or ()
    print("── 多项目概况 ──")
    if getattr(projects_section, "degraded", False) and not projects_rows:
        # find 级降级（OD-12 段值降默认——清单为空判别键；循环级降级清单恒非空：
        # 服务端 degraded 仅在分组循环内置位，循环执行即至少一行入清单）
        print("项目清单获取失败")
    else:
        # 正常/循环级部分降级共用呈现（循环级：清单保留+行报告列 None——「最新报告: 无」）
        print(f"项目: 共 {getattr(projects_section, 'plan_count', 0)} 个")
        for row in projects_rows:
            activity = getattr(row, "latest_activity_at", None)
            activity_text = activity[:16].replace("T", " ") if activity else "未知"
            print(f"  {getattr(row, 'plan_id', '')} | 归档: {getattr(row, 'archive_count', 0)} | 最新活动: {activity_text}")
            report_type = getattr(row, "latest_report_type", None)
            if report_type is None:
                print("    最新报告: 无")
            else:
                report_at = getattr(row, "latest_report_at", None)
                report_at_text = report_at[:16].replace("T", " ") if report_at else "未知"
                degraded_sections = getattr(row, "latest_degraded_section_count", None)
                degraded_text = f"，降级小节 {degraded_sections}" if degraded_sections is not None else ""
                print(f"    最新报告: {report_type}（{report_at_text}{degraded_text}）")

    brand = getattr(view, "brand", None)
    print("── 品牌配置 ──")
    # 6-11 v1.1.0 三值派生（R3 补位）：显示行三段改 BrandSection 派生值——
    # configured 态「已配置+默认」并存的呈现面自相矛盾修复（6-2 三值派生改造）
    configured_state = "已配置" if getattr(brand, "configured", False) else "未配置"
    print(
        f"品牌模板: {configured_state}"
        f" | Logo: {getattr(brand, 'logo_status', '未配置（系统默认）')}"
        f" | 配色: {getattr(brand, 'color_scheme_status', '未配置（系统默认）')}"
        f" | 字体: {getattr(brand, 'font_status', 'STSong-Light（内置）')}"
    )
    print("提示: 执行 brand-template-save 配置品牌模板")

    export = getattr(view, "export", None)
    print("── 白标导出 ──")
    print(
        f"可交付: {getattr(export, 'plans_with_reports', 0)} 项目有报告"
        f" | 最新 PDF: {getattr(export, 'plans_with_latest_pdf', 0)} 项目"
    )
    latest_pdf_plan = getattr(export, "latest_pdf_plan_id", None)
    if latest_pdf_plan is None:
        print("  最新 PDF: 无")
    else:
        print(f"  最新 PDF: {latest_pdf_plan}")
        print(f"  对象键: {getattr(export, 'latest_pdf_object_key', '')}")
    print("提示: 执行 report-generate --plan-id <uuid> --format pdf 生成白标 PDF")


def _run_consultant_view_cli() -> int:
    """consultant-view 子命令执行（五步定式名保留——实态四步去守卫步，Task 3 docstring 差异注记）。

    零输入零守卫面（OD-3）：无 plan_id 输入——畸形守卫步语义自然缺席（零输入即
    零畸形面，非缺失——6-8/6-9 连续两 Story UUID 守卫后的设计结果）；四步实态：
    _ensure_bootstrapped → asyncio.run+resolve → 打印 → DomainError/Exception
    双 except 兜底（防御性兜底——段级容错下不可达，兜底结构照设）。

    Returns:
        退出码（0=视图构建完成含空态——空态是正常态；1=业务异常；2=argparse
        用法错误由 argparse 原生承载）。
    """
    try:
        _ensure_bootstrapped()
        view = asyncio.run(_run_consultant_view())
        _print_consultant_view(view)
        logger.info("顾问视图查询完成")
        return 0
    except DomainError as error:
        logger.error("顾问视图查询失败: %s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1
    except Exception as error:
        logger.error("顾问视图查询异常: %s", error, exc_info=True)
        return 1


async def _run_checkpoint_recovery_view(plan_id: str, checkpoint_no: str) -> Any:
    """dry-run 评估数据面（resolve 既有恢复视图用例——仅取②步视图零执行）。

    resolve 入 try（代码审查 R1-F17——同 _run_checkpoint_list 注记）。
    """
    try:
        use_case = resolve("checkpoint_recovery_use_case")
        return await use_case.execute(plan_id=plan_id, checkpoint_no=checkpoint_no)
    finally:
        await _close_connection_pools()


async def _run_checkpoint_recover(plan_id: str, **kwargs: Any) -> Any:
    """恢复执行异步执行壳（resolve 执行用例——confirm 路径）。

    resolve 入 try（代码审查 R1-F17——同 _run_checkpoint_list 注记）。
    """
    try:
        use_case = resolve("checkpoint_recovery_execute_use_case")
        return await use_case.execute(plan_id=plan_id, **kwargs)
    finally:
        await _close_connection_pools()


def _parse_correction_group(
    correction_type: str | None,
    previous_value: str | None,
    new_value: str | None,
    applied_by: str | None,
) -> Any:
    """四 --correction-* 参数成组守卫（CLI 层唯一落位——post-parse 检测）。

    四个 args 原始形态（None=未提供）仅在 CLI 层可见——CorrectionRecord 字段
    默认值兜底下「部分出现」到用例层已不可表达（AC-2 裁定）；部分出现 →
    构造真实 EntityValidationError 242（6-3 R1-F18 真实异常构造纪律）。

    Returns:
        CorrectionRecord（四参数全提供）或 None（全未提供——纯恢复场景）。

    Raises:
        EntityValidationError: 242——四参数部分出现；或 correction_type 显式空串
            （修正判别键不可空——空修正无审计语义；previous/new/applied_by 空串
            属显式退化值，applied_by 空由 confirm 审批守卫兜底——代码审查 R1-F9）。
    """
    provided = [value for value in (correction_type, previous_value, new_value, applied_by) if value is not None]
    if provided and len(provided) < 4:
        raise EntityValidationError(
            message=(
                "--correction-type/--previous-value/--new-value/--applied-by 四参数必须成组提供"
                f"（实测仅提供 {len(provided)}/4）"
            ),
            context={
                "command": "checkpoint-recover",
                "field": "correction_group",
                "provided_count": str(len(provided)),
            },
        )
    if not provided:
        return None
    if not (correction_type or "").strip():
        raise EntityValidationError(
            message="--correction-type 不可为空串（修正判别键必填——空修正无审计语义）",
            context={
                "command": "checkpoint-recover",
                "field": "correction_type",
                "correction_type": correction_type or "",
            },
        )
    from src.domain.entities.checkpoint import CorrectionRecord

    return CorrectionRecord(
        correction_type=correction_type or "",
        previous_value=previous_value or "",
        new_value=new_value or "",
        applied_by=applied_by or "",
    )


def _print_recovery_assessment(view: Any, mode_raw: str | None, correction: Any, confirmed_by: str | None) -> None:
    """dry-run 影响评估输出（后续清单+建议模式+风险提示+修正展示+待确认提示）。

    风险等级经 assess_consistency_risk 同源计算（与引擎⑤步单一事实源——OD-5）；
    冲突组合附「confirm 必拒 487」预检提示（执法在执行态，评估态展示建议/请求
    双模式并预警）。
    """
    from src.domain.entities.checkpoint import RecoveryMode
    from src.domain.services.recovery_mode import assess_consistency_risk

    recommended = getattr(view, "recommended_mode", None)
    subsequent = list(getattr(view, "subsequent_checkpoints", []))
    if isinstance(recommended, RecoveryMode):
        recommended_mode = recommended
    elif isinstance(recommended, str) and recommended:
        recommended_mode = RecoveryMode(recommended)  # str-Enum 按值构造（小写值域）
    else:
        recommended_mode = RecoveryMode.OVERRIDE
    requested_mode = RecoveryMode(mode_raw) if mode_raw else None
    effective = requested_mode if requested_mode is not None else recommended_mode
    risk = assess_consistency_risk(effective, len(subsequent))

    print("恢复影响评估（dry-run——未执行）：")
    print(f"  恢复起点: {getattr(view, 'checkpoint_no', '')}")
    print(f"  后续 Checkpoint 清单: {subsequent or '（无）'}")
    print(f"  建议恢复模式: {recommended_mode.value}")
    if requested_mode is not None:
        print(f"  请求恢复模式: {requested_mode.value}")
    print(f"  一致性风险等级: {risk}")
    if correction is not None:
        print("  将应用的关键参数修正（仅展示零应用）：")
        print(f"    correction_type: {getattr(correction, 'correction_type', '')}")
        print(f"    previous_value: {getattr(correction, 'previous_value', '')}")
        print(f"    new_value: {getattr(correction, 'new_value', '')}")
        print(f"    applied_by: {getattr(correction, 'applied_by', '')}")
    approver_source = confirmed_by if confirmed_by is not None else getattr(correction, "applied_by", "")
    approver = approver_source or "（未提供——confirm 时必填）"
    print(f"  审批人: {approver}")
    if requested_mode is not None and recommended_mode is RecoveryMode.REPLAY and requested_mode is RecoveryMode.OVERRIDE:
        print("  ⚠ 预检提示：该组合 confirm 必被 487 拒绝（影响≥2 个后续 Checkpoint 强制 Replay）")
    print("待确认：加 --confirm 执行恢复（评估态不落恢复记录/不发布事件/不应用修正）")


def _print_recovery_outcome(outcome: Any) -> None:
    """恢复执行结果输出（Outcome 展示面——getattr 形态零实体依赖）。"""
    print("Checkpoint 恢复执行完成：")
    print(f"  checkpoint_no: {getattr(outcome, 'checkpoint_no', '')}")
    print(f"  recovery_mode: {getattr(outcome, 'recovery_mode', '')}")
    print(f"  corrected: {getattr(outcome, 'corrected', False)}")
    print(f"  new_state_version: {getattr(outcome, 'new_state_version', 0)}")
    print(f"  affected_checkpoints: {getattr(outcome, 'affected_checkpoints', [])}")
    print(f"  execution_ms: {getattr(outcome, 'execution_ms', 0.0):.2f}")
    print(f"  next_action_hint: {getattr(outcome, 'next_action_hint', '')}")
    print(f"  recovery_record_session_id: {getattr(outcome, 'recovery_record_session_id', '')}")


def _checkpoint_recover_controller(
    plan_id: str,
    checkpoint_no: str,
    correction_type: str | None,
    previous_value: str | None,
    new_value: str | None,
    applied_by: str | None,
    mode_raw: str | None,
    confirm: bool,
    confirmed_by: str | None,
    dry_run: bool = False,
) -> Any:
    """checkpoint-recover controller（守卫族全前移→dry_run 分叉→双态执行——OD-14/OD-12）。

    守卫族（全前移 controller 顶部——dry-run 短路不跳过任何守卫）：UUID 242 →
    四参成组 242 → ``--mode`` 值域 242（**Story 7-1 前移**：原在 confirm 分支
    内 :2303-2306 形态，dry-run 短路会跳过——OD-12 钦定②）→ 审批人 242
    （confirm 必填——dry-run×--yes 同样校验）。dry_run 动作清单随 confirm
    位切换（评估态/执行态措辞分叉——OD-12 钦定①）。

    Args:
        plan_id: --plan-id 原始字符串
        checkpoint_no: --checkpoint-no 原始字符串
        correction_type: --correction-type（四参数成组）
        previous_value: --previous-value（四参数成组）
        new_value: --new-value（四参数成组）
        applied_by: --applied-by（四参数成组；--confirmed-by 缺省链兜底）
        mode_raw: --mode 原始字符串（replay|override）
        confirm: 确认旗标（Typer 面 --yes / 兼容入口 --confirm 等价注入）
        confirmed_by: --confirmed-by（confirm 路径必填）
        dry_run: --dry-run 旗标（client 语义——全局短路零 resolve）

    Returns:
        动作清单（dry_run）或评估视图 view（confirm=False）/ 执行结果 outcome

    Raises:
        EntityValidationError: 242——守卫族任一失败
    """
    plan_id = _validate_plan_uuid(plan_id, "checkpoint-recover")
    correction = _parse_correction_group(correction_type, previous_value, new_value, applied_by)
    explicit_mode = None
    if mode_raw is not None:
        if mode_raw not in ("replay", "override"):
            raise EntityValidationError(
                message="--mode 值域非法（replay|override）",
                context={"command": "checkpoint-recover", "field": "mode", "mode": mode_raw},
            )
        from src.domain.entities.checkpoint import RecoveryMode

        explicit_mode = RecoveryMode(mode_raw)
    # is None 判缺省（代码审查 R1-F9）：显式空串原样保留不静默兜底
    effective_confirmed_by = confirmed_by if confirmed_by is not None else (applied_by or "")
    if confirm and not effective_confirmed_by:
        raise EntityValidationError(
            message="confirm 执行必须提供 --confirmed-by（或 --applied-by）——审批人身份不可缺省空",
            context={"command": "checkpoint-recover", "field": "confirmed_by", "confirmed_by": ""},
        )
    if dry_run:
        if confirm:
            return ["应用修正（如有）", "落恢复记录", "发布恢复事件", "输出恢复结果"]
        return ["输出恢复影响评估（评估模式——不落记录/不发事件/不应用修正）"]
    if not confirm:
        _ensure_bootstrapped()
        return asyncio.run(_run_checkpoint_recovery_view(plan_id, checkpoint_no))
    _ensure_bootstrapped()
    return asyncio.run(
        _run_checkpoint_recover(
            plan_id,
            checkpoint_no=checkpoint_no,
            correction=correction,
            mode=explicit_mode,
            confirmed_by=effective_confirmed_by,
            created_via="cli",
        )
    )


def _run_checkpoint_recover_cli(
    plan_id: str,
    checkpoint_no: str,
    correction_type: str | None,
    previous_value: str | None,
    new_value: str | None,
    applied_by: str | None,
    mode_raw: str | None,
    confirm: bool,
    confirmed_by: str | None,
) -> int:
    """checkpoint-recover 子命令执行（controller+双态渲染薄壳——Story 7-1 OD-14 抽取形态）。

    无 --confirm = dry-run（影响评估输出 + exit 0 + 三零——不调执行引擎仅
    resolve ②步视图）；有 --confirm = 执行 AC-3 全链。exit 0 口径：dry-run
    评估完成 / 恢复记录落库成功（发布降级不改 exit code——AC-4）。

    Args:
        plan_id: --plan-id 原始字符串（UUID 守卫先于 bootstrap）。
        checkpoint_no: --checkpoint-no 原始字符串。
        correction_type: --correction-type（四参数成组）。
        previous_value: --previous-value（四参数成组）。
        new_value: --new-value（四参数成组）。
        applied_by: --applied-by（四参数成组；--confirmed-by 缺省链兜底）。
        mode_raw: --mode 原始字符串（choices 已拦截小写值域）。
        confirm: --confirm 旗标（缺省 dry-run）。
        confirmed_by: --confirmed-by（confirm 路径必填；缺省取 --applied-by）。

    Returns:
        退出码（0=评估完成/恢复记录落库成功，1=业务异常）。
    """
    try:
        if not confirm:
            view = _checkpoint_recover_controller(
                plan_id, checkpoint_no, correction_type, previous_value, new_value, applied_by, mode_raw, confirm, confirmed_by
            )
            # correction 幂等重建（渲染参数——controller 守卫段已构造验证）
            correction = _parse_correction_group(correction_type, previous_value, new_value, applied_by)
            _print_recovery_assessment(view, mode_raw, correction, confirmed_by)
            logger.info("Checkpoint 恢复评估完成（dry-run）: plan_id=%s checkpoint_no=%s", plan_id, checkpoint_no)
            return 0
        outcome = _checkpoint_recover_controller(
            plan_id, checkpoint_no, correction_type, previous_value, new_value, applied_by, mode_raw, confirm, confirmed_by
        )
        _print_recovery_outcome(outcome)
        logger.info(
            "Checkpoint 恢复执行完成: plan_id=%s checkpoint_no=%s mode=%s",
            plan_id,
            checkpoint_no,
            mode_raw or "（建议模式）",
        )
        return 0
    except DomainError as error:
        logger.error("Checkpoint 恢复失败: %s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1
    except Exception as error:
        logger.error("Checkpoint 恢复异常: %s", error, exc_info=True)
        return 1


def _instantiate_controller(role_raw: str, dry_run: bool = False) -> Any:
    """instantiate controller（Typer 面——守卫→dry_run 分叉→幂等 bootstrap→异步执行）。

    Story 7-1 OD-14/OD-12：Typer 新前端统一走 ``_ensure_bootstrapped`` 幂等
    守卫形态（兼容入口 ``_run_instantiate_cli`` 保留 ``bootstrap()`` 直调
    例外——零回归铁律，见端口表例外注记）。

    Args:
        role_raw: --role 原始字符串
        dry_run: --dry-run 旗标（client 语义——动作清单零 resolve）

    Returns:
        动作清单（dry_run）或实例化 result（含 agent_id）

    Raises:
        AgentRoleNotSupportedError: 441——非法角色（守卫先于 bootstrap）
    """
    role = _parse_role(role_raw)
    if dry_run:
        return [f"将实例化 {role.value} 角色 Agent"]
    _ensure_bootstrapped()
    return asyncio.run(_instantiate(role))


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
    # 多守卫（先于 bootstrap——输入错误无需初始化端口注册表；Query 构造（242
    # 守卫：反转时间窗/越界分页等）同属输入校验面——纯 dataclass 构造零依赖，
    # 上移保持守卫序原则，R1-F20）
    try:
        agent_id = _parse_optional_agent_uuid(agent_id_raw)
        level = _parse_isolation_level(level_raw) if level_raw is not None else None
        start_time = _parse_optional_iso_datetime(start_raw, "--start")
        end_time = _parse_optional_iso_datetime(end_raw, "--end")
        query = IsolationSwitchLogQuery(
            agent_id=agent_id,
            start_time=start_time,
            end_time=end_time,
            level=level,
            offset=offset,
            limit=limit,
        )
    except (ValidationError, IsolationLevelNotSupportedError, EntityValidationError) as error:
        logger.error("%s", error)
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1

    try:
        _ensure_bootstrapped()
        repo = resolve("isolation_switch_log_repository")
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
    load_env()  # 显式 .env 加载（6.8-R1-DF1 核销——双入口复用单函数）
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
    if args.command == "blm-plan":
        return _run_blm_plan_cli(args.agent_id, args.task, args.plan_id)
    if args.command == "checkpoint-create":
        return _run_checkpoint_create_cli(
            args.plan_id,
            args.checkpoint_no,
            args.stage_id,
            args.query,
            args.user_id,
            args.summary,
            args.completed,
        )
    if args.command == "checkpoint-list":
        return _run_checkpoint_list_cli(args.plan_id)
    if args.command == "checkpoint-show":
        return _run_checkpoint_show_cli(args.plan_id, args.checkpoint_no)
    if args.command == "checkpoint-recover":
        return _run_checkpoint_recover_cli(
            args.plan_id,
            args.checkpoint_no,
            args.correction_type,
            args.previous_value,
            args.new_value,
            args.applied_by,
            args.mode,
            args.confirm,
            args.confirmed_by,
        )
    if args.command == "chain-query":
        return _run_chain_query_cli(args.plan_id, args.include_blob)
    if args.command == "trace-tree":
        return _run_trace_tree_cli(args.plan_id, args.depth, args.stage)
    if args.command == "executive-view":
        return _run_executive_view_cli(args.plan_id)
    if args.command == "analyst-view":
        return _run_analyst_view_cli(args.plan_id)
    if args.command == "consultant-view":
        return _run_consultant_view_cli()
    if args.command == "report-generate":
        return _run_report_generate_cli(
            args.plan_id,
            getattr(args, "format", "markdown"),
            getattr(args, "brand_template", None),
        )
    if args.command == "brand-template-save":
        return _run_brand_template_save_cli(
            args.name,
            args.color_scheme,
            args.font_preset,
            getattr(args, "logo_path", None),
        )
    if args.command == "brand-template-list":
        return _run_brand_template_list_cli()
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
