"""应用层 溯源 Prompt 模板模块

定义 LLM-as-a-Judge 引文质量评估的 System Prompt 和 User Prompt 模板。
评估引文与结论的相关性（relevance）、完整性（completeness）、准确性（accuracy）三维评分。

设计决策：
- Prompt 模板使用 Python f-string / str.format 格式，支持动态注入
- 评估标准以系统提示形式注入，确保 LLM 理解评估要求
- User Prompt 包含原始结论文本和引文列表（含置信度和 Bounding Box 信息）
"""

from __future__ import annotations

from src.domain.value_objects.citation import Citation

# 相关性评分标准
RELEVANCE_STANDARD: str = "相关性（relevance）：引文是否支持结论。1.0 = 完全支持，0.0 = 完全无关。0.6+ = 引文与结论语义相关。"

# 完整性评分标准
COMPLETENESS_STANDARD: str = (
    "完整性（completeness）：引文是否覆盖结论的关键信息。1.0 = 全部覆盖，0.0 = 无必要信息。0.6+ = 核心信息已覆盖。"
)

# 准确性评分标准
ACCURACY_STANDARD: str = "准确性（accuracy）：引文内容是否准确反映原文。1.0 = 完全准确，0.0 = 严重偏差。"

# System Prompt：角色定义 + 输出格式约束 + 评估标准
SYSTEM_PROMPT: str = f"""你是一位文献引用质量评估专家，负责评估引文与结论的相关性、完整性和准确性。

请严格遵循以下评分标准，为每个引文给出 0-1 之间的分数，并提供判断理由。

## 评估标准

{RELEVANCE_STANDARD}

{COMPLETENESS_STANDARD}

{ACCURACY_STANDARD}

## 输出格式

你必须输出符合以下 JSON Schema 的结构化评估结果：
- citations: array of objects，每个包含：
  - citation_id: string
  - relevance: float (0-1)
  - completeness: float (0-1)
  - accuracy: float (0-1)
- overall_score: float (0-1)"""

# User Prompt 模板：注入原始结论文本和引文列表
USER_PROMPT_TEMPLATE: str = """## 原始结论

{claim}

## 引文列表

{citations_context}

## 评估要求

请逐条评估上述引文，给出相关性、完整性和准确性的分数，并给出判断理由。"""

# 单条引文格式化模板（用于构建 citations_context）
CITATION_ITEM_TEMPLATE: str = """- 引文 ID: {citation_id}
  文档 ID: {document_id}
  内容: {text}
  置信度: {confidence:.2f}
  Bounding Box: {bbox_info}
"""


def format_citation_context(
    citations: list[Citation],
) -> str:
    """格式化引文列表为 Prompt 上下文

    Args:
        citations: Citation 值对象列表

    Returns:
        格式化的引文上下文文本
    """
    parts = []
    for citation in citations:
        bbox = getattr(citation, "bbox", None)
        if bbox is not None:
            bbox_info = f"page={bbox.page}, x={bbox.x:.1f}, y={bbox.y:.1f}, width={bbox.width:.1f}, height={bbox.height:.1f}"
        else:
            bbox_info = "无"
        parts.append(
            CITATION_ITEM_TEMPLATE.format(
                citation_id=citation.citation_id,
                document_id=str(citation.document_id),
                text=citation.text,
                confidence=citation.confidence,
                bbox_info=bbox_info,
            )
        )
    return "\n".join(parts)


def build_traceability_prompt(
    claim: str,
    citations: list[Citation],
) -> tuple[str, str]:
    """构建溯源评估 System Prompt 和 User Prompt

    Args:
        claim: 原始结论文本
        citations: Citation 值对象列表

    Returns:
        (system_prompt, user_prompt) 元组
    """
    user_prompt = USER_PROMPT_TEMPLATE.format(
        claim=claim,
        citations_context=format_citation_context(citations),
    )
    return SYSTEM_PROMPT, user_prompt


__all__ = [
    "SYSTEM_PROMPT",
    "USER_PROMPT_TEMPLATE",
    "CITATION_ITEM_TEMPLATE",
    "RELEVANCE_STANDARD",
    "COMPLETENESS_STANDARD",
    "ACCURACY_STANDARD",
    "format_citation_context",
    "build_traceability_prompt",
]
