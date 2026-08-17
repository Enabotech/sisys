"""应用层 检索相关性评估 Prompt 模板模块

定义 LLM-as-a-Judge 评估的 System Prompt 和 User Prompt 模板。
包含三个维度的评分标准说明，注入查询文本和检索结果上下文。

设计决策：
- Prompt 模板使用 Python f-string 格式，支持动态注入
- 评分标准以系统提示形式注入，确保 LLM 理解评估要求
- 阻断规则提示仅供 LLM 评分参考，服务端以 @computed_field 计算结果为准
- 时效性字段信息嵌入在 {search_context} 中，不需要独立占位符
"""

from __future__ import annotations

# 相关性评分标准
CONTEXT_RELEVANCE_STANDARD: str = (
    "相关性（context_relevance）：检索结果是否与查询语义相关。1.0 = 完全匹配查询意图，0.0 = 完全不相关。0.6+ = 可接受的相关性。"
)

# 完整性评分标准
COMPLETENESS_STANDARD: str = (
    "完整性（completeness）：检索结果是否覆盖查询的各个子主题。1.0 = 全部信息覆盖，0.0 = 无必要信息。0.6+ = 核心信息已覆盖。"
)

# 时效性评分标准
TIMELINESS_STANDARD: str = (
    "时效性（timeliness）：检索结果是否足够新（基于 payload 中的 updated_at 或 created_at 字段，"
    "若不存在则默认不惩罚）。1.0 = 最新信息，0.0 = 完全过时。0.6+ = 信息时效性可接受。"
)

# 阻断规则说明
BLOCK_RULE: str = (
    "阻断规则：综合评分 < 0.6 时应标注'数据不足'并阻断摘要生成。"
    "注意：服务端以 overall_score 的自动计算结果为准，此评分仅供 LLM 参考。"
)

# System Prompt：角色定义 + 输出格式约束 + 评分标准
SYSTEM_PROMPT: str = f"""你是一位检索质量评估专家，负责评估检索结果的相关性、完整性和时效性。

请严格遵循以下评分标准，为每个维度给出 0-1 之间的分数，并提供判断理由。

## 评分标准

{CONTEXT_RELEVANCE_STANDARD}

{COMPLETENESS_STANDARD}

{TIMELINESS_STANDARD}

## 输出格式

你必须输出符合以下 JSON Schema 的结构化评估结果：
- context_relevance: float (0-1)
- context_relevance_reason: string
- completeness: float (0-1)
- completeness_reason: string
- timeliness: float (0-1)
- timeliness_reason: string

{BLOCK_RULE}"""

# User Prompt 模板：注入查询文本和检索结果上下文
USER_PROMPT_TEMPLATE: str = """## 用户查询

{query_text}

## 检索结果上下文

{search_context}

## 评估要求

请逐条评估上述检索结果，给出每个维度的分数和判断理由。"""


__all__ = [
    "SYSTEM_PROMPT",
    "USER_PROMPT_TEMPLATE",
    "CONTEXT_RELEVANCE_STANDARD",
    "COMPLETENESS_STANDARD",
    "TIMELINESS_STANDARD",
    "BLOCK_RULE",
]
