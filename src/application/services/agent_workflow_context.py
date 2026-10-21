"""应用层单 Agent 工作流上下文装配器（Story 5-3 — DC-3 装配契约定稿）

启动上下文装配（5-2 风险 #1 核销）：五分节 system_prompt 定序 + CJK 感知
token 计量 + WorkflowContext 组装。纯函数零 IO 模块（架构约束 E——验证器
AST 断言）。

装配契约（DC-3 定稿）：
- system_prompt 五分节定序：IDENTITY→SOUL→CODE（行为约束）→核心约束文本
  （思维链五段输出要求 + 安全红线——agent_workflow_prompts.CORE_CONSTRAINTS_TEXT）
  →TOOLS L1 视图（"{tool_name}: {description}（用: {when_to_use}）" 行格式）
- USER/MEMORY 追加 system 尾节；task_description 进 user prompt（键位分工）
- HEARTBEAT 档案不注入（调度心跳配置是运行时健康信号非推理上下文——不入
  prompt 不进计量）
- 计量口径重定义：assembled_context_tokens = 全部分节 CJK 感知估算（弃
  5-2 startup_context_tokens 三件套口径——字段保留不动，本模块产出新口径）
- CJK 计量照抄 context_compressor._estimate_chars_tokens L408-425（中文
  1.5 字/token 其他 4 字/token、max(·,1) 下限——跨模块引下划线私有成员
  不雅，照抄实现含三段 Unicode 区间判定）
- 空 L1 降级（R3-DF1 核销）：TOOLS.md 缺失/降级空清单时显式「无可用工具」
  注记（非静默空段——装配降级可观测）
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from src.application.ports.agent_workflow import WorkflowContext
from src.application.ports.skill_loader import ToolMetadata
from src.application.services.agent_workflow_prompts import (
    CORE_CONSTRAINTS_TEXT,
    SECTION_ORDER,
    build_l1_view,
)
from src.domain.value_objects.agent_profile import AgentProfile

#: MVP 固定单租户标识（Agent 实体无租户字段——ExecutionContext 构造的租户
#: 来源；多租户扩展归后续 Story，R1-F21）
MVP_TENANT_ID = UUID("00000000-0000-4000-8000-000000000001")


def cjk_estimate_tokens(text: str) -> int:
    """CJK 感知 token 估算（context_compressor._estimate_chars_tokens 照抄）。

    中文按 1.5 字/token、其他按 4 字/token，max(·,1) 下限。三段 Unicode
    区间判定：CJK 统一表意（一-鿿）/CJK 符号和标点（　-〿）/全角形式与
    半宽片假名（＀-￯）。

    Args:
        text: 待估算文本

    Returns:
        估算 token 数（≥1）
    """
    if not text:
        return 1
    cjk_count = sum(1 for c in text if "一" <= c <= "鿿" or "　" <= c <= "〿" or "＀" <= c <= "￯")
    non_cjk = max(len(text) - cjk_count, 0)
    estimated = int(cjk_count / 1.5 + non_cjk / 4)
    return max(estimated, 1)


def build_system_prompt(profile: AgentProfile, tools_l1: tuple[ToolMetadata, ...]) -> str:
    """装配五分节 system_prompt（+ USER/MEMORY 尾节——HEARTBEAT 不注入）。

    分节顺序唯一真源 = SECTION_ORDER（agent_workflow_prompts——DC-3）。

    Args:
        profile: 六档案 VO（heartbeat 字段不消费）
        tools_l1: L1 工具元数据清单（空清单显式降级注记——R3-DF1）

    Returns:
        装配完成的 system_prompt 文本
    """
    # 分节内容映射（SECTION_ORDER 键 → 档案字段/常量/L1 视图）
    sections: dict[str, str] = {
        "identity": profile.identity,
        "soul": profile.soul,
        "code_of_conduct": profile.code_of_conduct,
        "core_constraints": CORE_CONSTRAINTS_TEXT,
        "tools_l1": build_l1_view(tools_l1),
    }
    # 分节标题映射（展示锚——顺序断言锚点；core_constraints 常量自带
    # 「## 核心约束」标题，此处标题位留空防重复）
    section_titles: dict[str, str] = {
        "identity": "## 身份档案（IDENTITY）",
        "soul": "## 价值观（SOUL）",
        "code_of_conduct": "## 行为准则（CODE）",
        "core_constraints": "",
        "tools_l1": "## 工具清单（TOOLS L1）",
    }
    parts = [f"{section_titles[key]}\n\n{sections[key]}" if section_titles[key] else sections[key] for key in SECTION_ORDER]
    # USER/MEMORY 追加 system 尾节（在五分节之后——DC-3）
    parts.append(f"## 用户偏好（USER）\n\n{profile.user_preferences}")
    parts.append(f"## 长期记忆（MEMORY）\n\n{profile.memory}")
    return "\n\n".join(parts)


def estimate_assembled_tokens(profile: AgentProfile, tools_l1: tuple[ToolMetadata, ...]) -> int:
    """装配总计量（新口径：五档案 + L1 视图 + 核心约束文本——heartbeat 不入）。

    Args:
        profile: 六档案 VO（heartbeat 不进计量）
        tools_l1: L1 工具元数据清单

    Returns:
        装配产物 CJK 感知估算 token 总数（≥1）
    """
    return cjk_estimate_tokens(build_system_prompt(profile, tools_l1))


def build_context(profile_result: Any, task: str) -> WorkflowContext:
    """装配入口：档案加载结果 + 任务 → WorkflowContext（五字段）。

    单向装配（R1-F23）：用例加载档案后传材料，本函数纯组装不触 IO；
    服务端口 build_context 方法委托本函数（装配逻辑单点）。

    Args:
        profile_result: AgentProfileLoadResult（五档案 + tools_l1 + 计量）
        task: 任务描述原文

    Returns:
        WorkflowContext 装配产物
    """
    profile: AgentProfile = profile_result.profile
    tools_l1: tuple[ToolMetadata, ...] = profile_result.tools_l1
    return WorkflowContext(
        system_prompt=build_system_prompt(profile, tools_l1),
        tools_l1=tools_l1,
        task=task,
        tenant_id=MVP_TENANT_ID,
        assembled_context_tokens=estimate_assembled_tokens(profile, tools_l1),
    )


__all__ = [
    "MVP_TENANT_ID",
    "build_context",
    "build_system_prompt",
    "cjk_estimate_tokens",
    "estimate_assembled_tokens",
]
