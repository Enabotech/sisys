"""应用层单 Agent 工作流 Prompt 模块（Story 5-3 — 单 Agent 标准工作流）

六阶段工作流的 prompt 资产：模块常量（核心约束文本/分节定序/task 模板）+
构造函数（TOOLS L1 视图行格式 + 五阶段 user prompt）。零 IO 纯函数模块
（架构约束 E——验证器 AST 断言）。

设计决策（debate_prompts 四连先例同构）：
- system_prompt 前缀稳定性 = Fake LLM 分派契约（validation_feedback_prompts
  L21 注释先例）：SYSTEM 各分节标题文本保持稳定——工具链 generate 面按
  prompt 前缀分派的测试替身依赖此稳定性
- HEARTBEAT 档案不注入（DC-3 裁决）：调度心跳配置是运行时健康信号非推理
  上下文，不入 prompt 不进计量——装配材料=其余五档案 + TOOLS L1
- 核心约束文本（CORE_CONSTRAINTS_TEXT）：思维链五段输出要求 + 安全红线，
  项目首个「核心约束」载体（AGENT.md 未实施的语义承载——D-2）
- task_description 进 user prompt（TASK_USER_PROMPT_TEMPLATE），不进 system
- plan prompt 重试轮回灌注入位（revised_plan/error_analysis——R2-F4：
  反思-重试闭环的信息流承载，防重试退化为同输入复读）

消息安全性：prompt 不泄露内部实现细节（端口名/类名/温度参数等）。
"""

from __future__ import annotations

from src.application.ports.skill_loader import ToolMetadata

#: system_prompt 五分节定序（DC-3：IDENTITY→SOUL→CODE→核心约束→TOOLS L1；
#: USER/MEMORY 追加 system 尾节由装配器处理——本常量是分节顺序唯一真源）
SECTION_ORDER: tuple[str, ...] = (
    "identity",
    "soul",
    "code_of_conduct",
    "core_constraints",
    "tools_l1",
)

#: 核心约束文本（思维链五段输出要求 + 安全红线——项目首个「核心约束」载体）
CORE_CONSTRAINTS_TEXT = """\
## 核心约束

输出纪律：
1. 思维链五段式输出：Input → <Reflection>…</Reflection> → <Tools_Used>…</Tools_Used>
   → <Constraints_Check>…</Constraints_Check> → JSON（最终结构化答案）
2. 推理必须基于任务与工具产出，不得虚构数据、不得编造引用
3. 工具调用必须与规划一致，禁止跳过验证直接给结论
4. 全部使用中文输出（代码与数据结构除外），严格遵守输出 Schema\
""".strip()

#: task user prompt 模板（task_description 进 user 消息——DC-3 键位分工）
TASK_USER_PROMPT_TEMPLATE = """\
## 任务

{task}

## 要求

请理解并执行上述任务，按当前阶段要求输出。\
"""


def build_l1_view(tools_l1: tuple[ToolMetadata, ...]) -> str:
    """构造 TOOLS L1 视图文本（行格式：名称: 描述（用: 触发词））。

    description 即触发器（interface-design §5.6 Step5——规划阶段 LLM 从
    L1 视图自判工具选择，DC-10）。空清单时显式降级占位（R3-DF1：TOOLS.md
    缺失/降级空 L1 不静默空段——「无可用工具」注记使装配降级可观测）。

    Args:
        tools_l1: L1 工具元数据清单（仅 active）

    Returns:
        L1 视图多行文本（每工具一行）
    """
    if not tools_l1:
        return "（无可用工具——TOOLS.md 缺失或降级为空清单）"
    lines = []
    for meta in tools_l1:
        triggers = "、".join(meta.when_to_use) if meta.when_to_use else "按任务需要判断"
        lines.append(f"{meta.tool_name}: {meta.description}（用: {triggers}）")
    return "\n".join(lines)


def build_perceive_prompt(task: str) -> str:
    """感知阶段 user prompt（任务上下文摘要）。

    Args:
        task: 任务描述原文

    Returns:
        感知阶段 user prompt
    """
    return f"""\
## 感知任务

{task}

## 要求

请输出任务上下文摘要：任务目标、涉及领域、关键约束与预期产出形态。\
"""


def build_plan_prompt(
    task: str,
    revised_plan: str = "",
    error_analysis: str = "",
) -> str:
    """规划阶段 user prompt（任务分解与工具匹配）。

    重试轮回灌（R2-F4）：revised_plan 与 error_analysis 非空时注入修正
    上下文——反思-重试闭环的信息流承载（首轮两参为空串零残留）。

    Args:
        task: 任务描述原文
        revised_plan: 反思产出的修正计划（重试轮非空）
        error_analysis: 反思产出的错误分析（重试轮非空）

    Returns:
        规划阶段 user prompt
    """
    revision_section = ""
    if revised_plan or error_analysis:
        revision_section = f"""
## 上一轮验证失败与修正指引

错误分析：{error_analysis or "（无）"}
修正计划：{revised_plan or "（无）"}

请基于上述修正指引重新规划，避免重复上一轮的失败模式。\
"""
    return f"""\
## 规划任务

{task}
{revision_section}
## 要求

请将任务分解为可执行步骤，并从系统提示中的工具清单（L1 视图）选择每步
所需工具（无合适工具的步骤 tool_name 留空、直接推理），为每步给出执行
参数。\
"""


def build_verify_prompt(task: str, execution_summary: str) -> str:
    """验证阶段 user prompt（结构化检查）。

    Args:
        task: 任务描述原文
        execution_summary: 执行阶段产物摘要（工具轨迹与输出概览）

    Returns:
        验证阶段 user prompt
    """
    return f"""\
## 验证检查

任务：{task}

## 执行产物摘要

{execution_summary}

## 要求

请对照任务目标做结构化检查：产出是否完备、约束是否满足、工具输出是否
支持结论；输出是否通过（passed）、置信度（confidence）与判定依据
（rationale）。\
"""


def build_reflect_prompt(task: str, verification_rationale: str) -> str:
    """反思阶段 user prompt（失败时错误分析与修正计划）。

    Args:
        task: 任务描述原文
        verification_rationale: 末次验证失败依据（rationale）

    Returns:
        反思阶段 user prompt
    """
    return f"""\
## 反思分析

任务：{task}

## 验证失败依据

{verification_rationale}

## 要求

请分析验证失败根因，判断是否可通过修正计划重试（revised）：
- 可修正：给出修正计划（revised_plan）与错误分析（error_analysis）
- 不可修正：revised 置 false（说明根本性障碍，避免无效重试）\
"""


def build_final_synthesis_prompt(
    task: str,
    perception_summary: str,
    execution_summary: str,
    verification_rationale: str,
    reflection_summary: str = "",
    retry_count: int = 0,
) -> str:
    """终局思维链合成 user prompt（package 阶段单次 structured_generate）。

    携带 state 各阶段产物摘要（DC-2：终局合成三字段 reflection/
    constraints_check/final_answer 的生成引导；成功路径 reflection 由
    「一次通过」语义引导产出——化解五字段非空 vs 成功路径无反思矛盾）。

    Args:
        task: 任务描述原文
        perception_summary: 感知阶段任务摘要（input_summary 组装源）
        execution_summary: 执行阶段产物摘要
        verification_rationale: 验证阶段判定依据
        reflection_summary: 反思阶段产物摘要（错误分析 + 修正计划——重试路径
            的修正素材；成功路径无反思轮时为空串，分节省略）
        retry_count: 已消耗重试次数（0 = 一次通过）

    Returns:
        终局合成 user prompt
    """
    # 反思素材行条件渲染：成功路径（无反思轮）省略分节——「历经重试时总结
    # 修正过程」的要求仅在素材存在时生效（防 LLM 无素材虚构修正过程——
    # 与 CORE_CONSTRAINTS_TEXT「不得虚构数据」对齐）
    reflection_section = f"- 反思修正（历经 {retry_count} 次重试）：{reflection_summary}\n" if reflection_summary else ""
    return f"""\
## 综合任务

任务：{task}

## 各阶段产物

- 感知摘要：{perception_summary}
- 执行产物：{execution_summary}
{reflection_section}- 验证结论：{verification_rationale}

## 要求

请综合上述产物输出最终思维链三字段：
1. reflection：整体反思（验证一次通过时给出「一次通过」性总结与质量
   评价；历经重试时基于「反思修正」素材总结修正过程——不得虚构未发生
   的修正）
2. constraints_check：对照任务约束逐项核查结论
3. final_answer：最终结构化答案（JSON 形态，直接可消费）

注意：input_summary 与 tools_used 将被系统按真实记录覆写，仍请输出
占位内容（Schema 必填）。
"""


__all__ = [
    "CORE_CONSTRAINTS_TEXT",
    "SECTION_ORDER",
    "TASK_USER_PROMPT_TEMPLATE",
    "build_final_synthesis_prompt",
    "build_l1_view",
    "build_perceive_prompt",
    "build_plan_prompt",
    "build_reflect_prompt",
    "build_verify_prompt",
]
