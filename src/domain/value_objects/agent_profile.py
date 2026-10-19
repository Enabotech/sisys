"""领域层 Agent 身份档案值对象（Story 5-2 — Agent 身份档案加载）

AgentProfile——Agent 启动上下文的六档案静态资产载体（IDENTITY/CODE/SOUL/USER/
MEMORY/HEARTBEAT 六份 .md 内容），TOOLS.md 视图经 skill_loader 端口 L1 元数据
组装（单一真源，DC-2），不进入本 VO（ToolMetadata 属 application 层——domain
依赖 application 违反方向矩阵，分层裁定见 DC-7）。

出处：
- or.md 四.1.[1]（L277）：AGENT 实例化启动时加载身份档案（IDENTITY.md）、
  行为规范（CODE.md）、人格定义（SOUL.md）、工具集（TOOLS.md）、用户信息
  （USER.md）、长期记忆（MEMORY.md）、心跳任务配置（HEARTBEAT.md）。
- architecture.md §11.2.2/§11.2.8：七档案启动时一次性加载，不在运行时动态更新。

校验语义：本 VO 的 __post_init__ 为直接构造场景的纵深兜底——加载器
（MarkdownAgentProfileLoader）是判空主检位（其 442 的 context.profile_path
携带文件名，DC-5 观测锚点），兜底路径的 context 允许 profile_path 为空。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from src.domain.entities.agent import AgentRole
from src.domain.exceptions import AgentProfileError

#: 六档案字段名清单（IDENTITY/CODE/SOUL/USER/MEMORY/HEARTBEAT——or.md 四.1.[1] 枚举序）
PROFILE_FIELDS: tuple[str, ...] = (
    "identity",
    "code_of_conduct",
    "soul",
    "user_preferences",
    "memory",
    "heartbeat",
)


@dataclass(frozen=True)
class AgentProfile:
    """Agent 身份档案值对象（六档案静态资产，frozen 不可变）

    档案归属具体 Agent 实例（agent_id 锚点）+ 角色（role 决定寻址目录
    profiles/{role.value}/）。

    Attributes:
        agent_id: 档案归属的 Agent 实例标识（UUID 对象）
        role: Agent 角色（枚举——决定档案寻址目录）
        identity: IDENTITY.md 内容（身份：角色定义/职责/权责边界）
        code_of_conduct: CODE.md 内容（行为准则）
        soul: SOUL.md 内容（价值观/决策风格）
        user_preferences: USER.md 内容（用户偏好）
        memory: MEMORY.md 内容（长期记忆——MVP 静态种子，DC-6）
        heartbeat: HEARTBEAT.md 内容（心跳任务配置——静态档案不接线 scheduler，L7 deferred）
    """

    agent_id: uuid.UUID
    role: AgentRole
    identity: str
    code_of_conduct: str
    soul: str
    user_preferences: str
    memory: str
    heartbeat: str

    def __post_init__(self) -> None:
        """自校验：锚点类型守卫 + 六档案字段先类型后空值（442）。

        校验顺序契约：agent_id/role 类型 → 六字段 isinstance(str) → strip 非空。
        先类型后判空是 5-1 R2-F2 教训的防线——truthy 标量（如 int 12345）
        会越过纯判空检查静默通过。
        """
        if not isinstance(self.agent_id, uuid.UUID):
            raise AgentProfileError(
                reason="agent_id 必须为 uuid.UUID 类型",
            )
        if not isinstance(self.role, AgentRole):
            raise AgentProfileError(
                reason="role 必须为 AgentRole 枚举实例",
            )
        for field_name in PROFILE_FIELDS:
            content = getattr(self, field_name)
            if not isinstance(content, str):
                raise AgentProfileError(
                    reason=f"档案字段 {field_name} 必须为 str 类型（实际 {type(content).__name__}）",
                )
            if not content.strip():
                raise AgentProfileError(
                    reason=f"档案字段 {field_name} 内容为空白（strip 后非空校验未通过）",
                )
