"""应用层 摘要 Prompt 模板模块

定义财务（financial）、市场（market）、技术（technical）三个视角的
System Prompt 和 User Prompt 模板。

设计决策：
- 模板使用 Python f-string / str.format，统一格式，无需额外依赖
- System Prompt 包含角色定义、输出格式约束、质量要求
- User Prompt 包含查询文本、检索结果上下文、输出要求
- 通过 PERSPECTIVE_PROMPT_MAP 统一映射视角到 Prompt 模板
"""

from __future__ import annotations

from typing import TypedDict


class PerspectivePrompts(TypedDict):
    """视角 Prompt 模板映射结构

    Attributes:
        system_prompt: System Prompt（角色定义 + 输出约束）
        user_prompt_template: User Prompt 模板（含 {query_text} 和 {search_context} 占位符）
    """

    system_prompt: str
    user_prompt_template: str


FINANCIAL_SYSTEM_PROMPT = """
你是一位资深财务分析师，擅长从企业财务数据中提炼结构化洞察。
请基于提供的查询和检索上下文，生成符合预定义 JSON Schema 的财务分析摘要。

输出要求：
1. 必须严格遵守 JSON Schema 中定义的字段和类型
2. summary_text 需完整概括财务状况，突出关键财务指标
3. key_points 提炼 1-10 个核心财务要点，每个不超过 200 字符
4. confidence_score 为 0-1 之间的浮点数，表示你基于检索结果相关性和生成质量的自评置信度
5. 仅基于提供的检索上下文作答，不得编造数据
6. 使用简体中文输出
7. 注意：检索结果中可能包含[数据陈旧]标记的数据，请在摘要开头标注"⚠️ 部分引用数据已陈旧"并引用陈旧原因。
""".strip()

FINANCIAL_USER_PROMPT_TEMPLATE = """
查询文本：{query_text}

检索结果上下文：
{search_context}

请根据以上信息，生成财务视角的结构化摘要，严格遵守 JSON Schema 输出。
""".strip()

MARKET_SYSTEM_PROMPT = """
你是一位资深市场分析师，擅长从市场数据中提炼竞争格局和增长洞察。
请基于提供的查询和检索上下文，生成符合预定义 JSON Schema 的市场分析摘要。

输出要求：
1. 必须严格遵守 JSON Schema 中定义的字段和类型
2. summary_text 需完整概括市场状况，突出市场规模和竞争态势
3. key_points 提炼 1-10 个核心市场要点，每个不超过 200 字符
4. confidence_score 为 0-1 之间的浮点数，表示你基于检索结果相关性和生成质量的自评置信度
5. 仅基于提供的检索上下文作答，不得编造数据
6. 使用简体中文输出
7. 注意：检索结果中可能包含[数据陈旧]标记的数据，请在摘要开头标注"⚠️ 部分引用数据已陈旧"并引用陈旧原因。
""".strip()

MARKET_USER_PROMPT_TEMPLATE = """
查询文本：{query_text}

检索结果上下文：
{search_context}

请根据以上信息，生成市场视角的结构化摘要，严格遵守 JSON Schema 输出。
""".strip()

TECHNICAL_SYSTEM_PROMPT = """
你是一位资深技术架构师，擅长从技术文档中提炼架构和技术演进洞察。
请基于提供的查询和检索上下文，生成符合预定义 JSON Schema 的技术分析摘要。

输出要求：
1. 必须严格遵守 JSON Schema 中定义的字段和类型
2. summary_text 需完整概括技术状况，突出技术栈和架构特点
3. key_points 提炼 1-10 个核心技术要点，每个不超过 200 字符
4. confidence_score 为 0-1 之间的浮点数，表示你基于检索结果相关性和生成质量的自评置信度
5. 仅基于提供的检索上下文作答，不得编造数据
6. 使用简体中文输出
7. 注意：检索结果中可能包含[数据陈旧]标记的数据，请在摘要开头标注"⚠️ 部分引用数据已陈旧"并引用陈旧原因。
""".strip()

TECHNICAL_USER_PROMPT_TEMPLATE = """
查询文本：{query_text}

检索结果上下文：
{search_context}

请根据以上信息，生成技术视角的结构化摘要，严格遵守 JSON Schema 输出。
""".strip()

# 视角类型到 Prompt 模板的映射
PERSPECTIVE_PROMPT_MAP: dict[str, PerspectivePrompts] = {
    "financial": {
        "system_prompt": FINANCIAL_SYSTEM_PROMPT,
        "user_prompt_template": FINANCIAL_USER_PROMPT_TEMPLATE,
    },
    "market": {
        "system_prompt": MARKET_SYSTEM_PROMPT,
        "user_prompt_template": MARKET_USER_PROMPT_TEMPLATE,
    },
    "technical": {
        "system_prompt": TECHNICAL_SYSTEM_PROMPT,
        "user_prompt_template": TECHNICAL_USER_PROMPT_TEMPLATE,
    },
}


__all__ = [
    "FINANCIAL_SYSTEM_PROMPT",
    "FINANCIAL_USER_PROMPT_TEMPLATE",
    "MARKET_SYSTEM_PROMPT",
    "MARKET_USER_PROMPT_TEMPLATE",
    "TECHNICAL_SYSTEM_PROMPT",
    "TECHNICAL_USER_PROMPT_TEMPLATE",
    "PERSPECTIVE_PROMPT_MAP",
    "PerspectivePrompts",
]
