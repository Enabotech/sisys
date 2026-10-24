"""三重隔离判定核心（Prompt/工具/数据——domain 纯函数矩阵）。

Story 5.5 PDP（Policy Decision Point）: 判定矩阵唯一真源——等级语义全部从
ISOLATION_POLICIES 策略字段派生（prompt_isolation/tool_isolation/data_isolation
消费 5-4 契约），本模块零等级硬编码。矩阵三步:

1. shared 面: READ → 放行（全等级）; WRITE → 按 data_isolation
   （READ_ONLY→拒 / RESTRICTED_WRITE→拒[MVP 受限写白名单未定义，D-4] /
   FREE_WRITE→放行 / FULL_SHARED→放行）——shared 面不分 cross/self
2. private + self: 放行（自身资源自由读写）
3. private + cross: prompt_isolation True（L4/L3/L2）→ 拒; False（L1 融合态）→ 放行

零 IO 纯函数（全格穷举单测可判定）；IO 编排与异常翻译归应用层守卫服务（PEP）。

Author:
    agimtech <enabotech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.domain.exceptions import EntityValidationError
from src.domain.value_objects.isolation_policy import DataIsolationMode, IsolationPolicy

__all__ = [
    "AccessOperation",
    "IsolationAccessDecision",
    "IsolationResource",
    "IsolationViolationKind",
    "decide_isolation_access",
    "decide_tool_access",
    "resource_is_private",
]


class IsolationResource(str, Enum):
    """三重隔离资源归属分类（11 成员两归属类）。

    private（9，Agent 命名空间私有）: 身份档案/运行时系统提示词/工作流上下文/
    Agent 实体状态/隔离状态/会话/沙箱会话/工具执行历史/L0 记忆。
    shared（2，协作共享面）: 公共黑板/共享工作区。
    """

    PROFILE = "profile"
    SYSTEM_PROMPT = "system_prompt"
    WORKFLOW_CONTEXT = "workflow_context"
    AGENT_STATE = "agent_state"
    ISOLATION_STATE = "isolation_state"
    SESSION = "session"
    SANDBOX_SESSION = "sandbox_session"
    TOOL_EXECUTION_HISTORY = "tool_execution_history"
    MEMORY = "memory"
    BLACKBOARD = "blackboard"
    SHARED_WORKSPACE = "shared_workspace"


#: shared 面（协作共享面——矩阵第 1 步分类依据；策略前向语义注记：
#: TOOL_EXECUTION_HISTORY 归 private 而 Epic 4 存储现按 tenant 维度——MVP 无跨
#: Agent 读取通道故无冲突，存储归属性演进归 Epic 4 后续联动）
_SHARED_RESOURCES: frozenset[IsolationResource] = frozenset({IsolationResource.BLACKBOARD, IsolationResource.SHARED_WORKSPACE})


class AccessOperation(str, Enum):
    """资源访问操作（写涵盖增删改——MVP 不细分）。"""

    READ = "read"
    WRITE = "write"


class IsolationViolationKind(str, Enum):
    """隔离违规种类（对应异常 448/449 两个语义轴——跨主体越权/单主体操作禁止）。"""

    ACCESS_VIOLATION = "access_violation"
    OPERATION_FORBIDDEN = "operation_forbidden"


@dataclass(frozen=True)
class IsolationAccessDecision:
    """三重隔离判定决策对象（纯函数返回值——allowed/violation/reason 三件套）。

    Attributes:
        allowed: 是否放行。
        violation: 拒绝时的违规种类（放行时必为 None）。
        reason: 中文判定依据（审计可读；拒绝 reason 编码触发细分——
            tool_not_in_allowlist:{name} / data_isolation:{mode} 形态）。
    """

    allowed: bool
    violation: IsolationViolationKind | None
    reason: str

    def __post_init__(self) -> None:
        """互斥不变量校验（allowed=True 时 violation 必为 None；反之必非 None）。"""
        if self.allowed and self.violation is not None:
            raise EntityValidationError(
                message="放行决策不可携带 violation（互斥不变量）",
                context={"allowed": self.allowed, "violation": self.violation.value},
            )
        if not self.allowed and self.violation is None:
            raise EntityValidationError(
                message="拒绝决策必须携带 violation（互斥不变量）",
                context={"allowed": self.allowed, "reason": self.reason},
            )


def resource_is_private(resource: IsolationResource) -> bool:
    """判定资源是否归属 Agent 命名空间私有类（矩阵第 1/2 步分类依据）。

    Args:
        resource: 资源归属分类枚举成员。

    Returns:
        True 表示 private（9 成员）; False 表示 shared（协作共享面 2 成员）。
    """
    return resource not in _SHARED_RESOURCES


def decide_isolation_access(
    policy: IsolationPolicy,
    *,
    cross_agent: bool,
    resource: IsolationResource,
    operation: AccessOperation,
) -> IsolationAccessDecision:
    """三重隔离判定矩阵（Prompt/数据面——纯函数零 IO，唯一真源）。

    矩阵三步（等级语义从 ISOLATION_POLICIES 策略字段派生，本函数零等级硬编码）:
    shared 面 → 读放行 / 写按 data_isolation; private 面 → 跨主体按
    prompt_isolation / 自身放行。shared 面写不因 self 豁免（矩阵第 1 步不分
    cross/self——单主体轴与 448 跨主体轴正交）。

    Args:
        policy: 隔离策略（ISOLATION_POLICIES 四级表成员——判定唯一策略输入）。
        cross_agent: 是否跨主体访问（actor ≠ target）。
        resource: 资源归属分类。
        operation: 访问操作（读/写）。

    Returns:
        判定决策对象（allowed/violation/reason 三件套）。
    """
    if not resource_is_private(resource):
        if operation is AccessOperation.READ:
            return IsolationAccessDecision(allowed=True, violation=None, reason="共享面读开放（全等级）")
        if policy.data_isolation in (DataIsolationMode.FREE_WRITE, DataIsolationMode.FULL_SHARED):
            return IsolationAccessDecision(
                allowed=True, violation=None, reason=f"共享面写允许（{policy.data_isolation.value}）"
            )
        return IsolationAccessDecision(  # READ_ONLY / RESTRICTED_WRITE（MVP 受限写拒——D-4）
            allowed=False,
            violation=IsolationViolationKind.OPERATION_FORBIDDEN,
            reason=f"data_isolation:{policy.data_isolation.value}",
        )
    if not cross_agent:
        return IsolationAccessDecision(allowed=True, violation=None, reason="自身资源访问")
    if policy.prompt_isolation:  # L4/L3/L2 全 True——「独立」贯穿三级
        return IsolationAccessDecision(
            allowed=False,
            violation=IsolationViolationKind.ACCESS_VIOLATION,
            reason=f"跨 Agent 私有资源访问被拒（{policy.name}）",
        )
    return IsolationAccessDecision(  # L1 FULL_SHARED 自洽（MVP 禁用——V2 前向格锁定）
        allowed=True, violation=None, reason="融合态前向语义（V2）"
    )


def decide_tool_access(
    policy: IsolationPolicy,
    *,
    tool_name: str,
    allowed_tools: tuple[str, ...],
) -> IsolationAccessDecision:
    """工具白名单判定（工具面——纯函数零 IO）。

    tool_isolation False（L3/L2/L1 共享池）→ 放行; True（L4 严格隔离）→
    白名单内放行 / 白名单外拒。拒绝 reason 恰为 tool_not_in_allowlist:{name}
    形态（与 449 context reason 对称透传）；白名单明细不进 reason 与 context
    （禁泄露——明细经配置通道可查）。

    Args:
        policy: 隔离策略（tool_isolation 维度消费）。
        tool_name: 请求执行的工具名（中文显示名——TOOL_CATALOG 真源形态）。
        allowed_tools: 角色工具白名单（tuple 形态——AgentConfig.allowed_tools
            真源；类型收紧防裸 str 传入退化为子串匹配的白名单放大）。

    Returns:
        判定决策对象（allowed/violation/reason 三件套）。
    """
    if not policy.tool_isolation:
        return IsolationAccessDecision(allowed=True, violation=None, reason=f"共享工具池（{policy.name}）")
    if tool_name in allowed_tools:
        return IsolationAccessDecision(allowed=True, violation=None, reason=f"工具在白名单内（{policy.name}）")
    return IsolationAccessDecision(
        allowed=False,
        violation=IsolationViolationKind.OPERATION_FORBIDDEN,
        reason=f"tool_not_in_allowlist:{tool_name}",
    )
