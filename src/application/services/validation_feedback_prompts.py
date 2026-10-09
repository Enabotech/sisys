"""Validation Feedback 修复 prompt 模板（Story 4.7 AC-2）

fix-gen（修复建议生成）的 prompt 组装——「建议者」角色（引擎 Code stage 是
唯一代码产出作者——决策 #9：fix-gen 产出策略/代码草案，引擎按 hints 重新生成
完整代码，「建议者+作者」两级结构的归因局限显式接受）。

分派契约：FIX_SYSTEM_PROMPT 以 "Validation Feedback 修复顾问" 开头——Fake LLM
按 system_prompt 角色标记分派（4-5 R1-F06 纪律，BDD 同款契约）。
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "FIX_SYSTEM_PROMPT",
    "build_fix_prompt",
    "render_prior_attempts",
]

# fix-gen system_prompt（角色标记——Fake LLM 分派键，前缀须保持稳定）
FIX_SYSTEM_PROMPT = (
    "Validation Feedback 修复顾问：你是工具执行失败的修复顾问。基于 STDERR、"
    "Schema violations、历史修复案例与此前失败的修复方案，给出下一步修复建议"
    "（策略与代码草案）——引擎将按建议重新生成完整代码。禁止重复已失败的方案。"
)

# 摘录展示截断（prompt 内展示用头部截断——签名计算仍为尾部锚定）
_EXCERPT_DISPLAY_LIMIT = 500


def _display(text: str, limit: int = _EXCERPT_DISPLAY_LIMIT) -> str:
    """头部截断展示（prompt 展示口径）."""
    return text[:limit] if len(text) > limit else text


def render_prior_attempts(prior_attempts: list[dict[str, Any]]) -> tuple[str, str]:
    """渲染跨尝试失败反馈（R8-1 动作+结果成对）.

    空方案条目（suggested_fix_excerpt=""——llm_generation_failed 形态）渲染为
    「未产出方案（生成失败）」标注，不进入「禁止重复失败方案」清单
    （R9-20：无指涉对象——空串渲染为已试方案会误导 fix-gen）。

    Args:
        prior_attempts: 此前各次 attempt 摘要列表（含 stderr_excerpt/detail/
            suggested_fix_excerpt）

    Returns:
        (反馈文本, 禁止重复清单文本) 二元组
    """
    if not prior_attempts:
        return "", ""
    lines: list[str] = []
    banned: list[str] = []
    for attempt in prior_attempts:
        no = attempt.get("attempt_no", "?")
        detail = attempt.get("detail", "")
        stderr = _display(str(attempt.get("stderr_excerpt", "") or ""))
        fix = str(attempt.get("suggested_fix_excerpt", "") or "")
        line = f"- attempt {no}（{detail}）"
        if stderr:
            line += f"：{stderr}"
        if fix:
            line += f"；已试方案：{fix}"
            banned.append(f"attempt {no} 的方案（{fix}）")
        else:
            line += "；未产出方案（生成失败）"
        lines.append(line)
    feedback = "\n".join(lines)
    banned_text = ""
    if banned:
        banned_text = "以下方案已失败，禁止重复：\n" + "\n".join(f"- {b}" for b in banned)
    return feedback, banned_text


def build_fix_prompt(
    *,
    tool_name: str,
    stderr_excerpt: str,
    schema_violations: list[dict[str, Any]] | tuple[Any, ...],
    case_summaries: list[str],
    negative_hint: str,
    prior_attempts: list[dict[str, Any]],
    tool_call_arguments: dict[str, Any] | None = None,
) -> str:
    """组装修复建议生成 prompt.

    Args:
        tool_name: 工具名
        stderr_excerpt: 触发失败 STDERR 摘录
        schema_violations: Schema violations（389-Schema 子路径）
        case_summaries: 命中案例配方列表（CASE_GUIDED 注入）
        negative_hint: 负样本提示（NEGATIVE_CASE_GUIDED 注入）
        prior_attempts: 此前各次 attempt 摘要（跨尝试反馈——R8-1）
        tool_call_arguments: 工具调用参数（上下文参考）

    Returns:
        完整修复 prompt 文本
    """
    sections: list[str] = [f"工具 {tool_name} 执行失败，请给出修复建议。"]
    if stderr_excerpt:
        sections.append(f"失败 STDERR：\n{_display(stderr_excerpt)}")
    if schema_violations:
        violation_lines = []
        for v in schema_violations:
            if isinstance(v, dict):
                violation_lines.append(
                    f"- path={v.get('path', '')}, expected={v.get('expected', '')}, message={v.get('message', '')}"
                )
            else:
                violation_lines.append(f"- {v}")
        sections.append("Schema 校验 violations：\n" + "\n".join(violation_lines))
    if case_summaries:
        sections.append("历史成功修复案例：\n" + "\n".join(f"- {_display(s)}" for s in case_summaries))
    if negative_hint:
        sections.append(f"注意：{negative_hint}")
    feedback, banned = render_prior_attempts(prior_attempts)
    if feedback:
        sections.append(f"此前增强尝试的失败记录：\n{feedback}")
    if banned:
        sections.append(banned)
    if tool_call_arguments:
        sections.append(f"工具调用参数：{tool_call_arguments}")
    sections.append("请给出下一步修复建议（策略与代码草案），不要重复已失败方案。")
    return "\n\n".join(sections)
