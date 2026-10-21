"""领域层思维链值对象（Story 5-3 — 单 Agent 标准工作流）

ChainOfThought——Agent 工作流产出的 JSON 思维链五字段结构化载体（可审计
推理过程），供 6-4 持久化与 5.7 Phoenix 追踪消费的结构化真源；展示形态经
to_display() 生成五段 XML 标签文本（存储用结构化、展示用标签——DC-2 双形态）。

出处：
- or.md §五.5（L480）：思维链五段式输出 Input → <Reflection> → <Tools_Used>
  → <Constraints_Check> → JSON（最终结构化答案）。
- epics_v1.0.md L1560（AC-2 JSON 思维链输出）。

字段来源映射（DC-2 组装覆写 + 终局合成定稿）：
- input_summary ← perceive 产物（组装覆写——LLM 复述值被服务覆写）
- tools_used ← 真实工具调用轨迹（组装覆写——与实际轨迹天然一致，含版本
  后缀如 "pestel:v1.2.0"；允许空元组——无工具任务合法形态）
- reflection / constraints_check / final_answer ← package 阶段终局单次合成

校验语义：__post_init__ 为 VO 构造器守卫——校验失败抛 EntityValidationError
(242)；服务端终局组装完整性校验捕获 242 改写 ChainOfThoughtValidationError
(445) 携 missing_fields（异常契约三层次序②）。
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.exceptions import EntityValidationError

#: 四个必须非空的 str 字段名清单（tools_used 另走元组类型守卫）
_TEXT_FIELDS: tuple[str, ...] = ("input_summary", "reflection", "constraints_check", "final_answer")


@dataclass(frozen=True)
class ChainOfThought:
    """思维链值对象（五字段，frozen 不可变）

    Attributes:
        input_summary: 输入摘要（perceive 阶段任务上下文摘要——组装覆写产物）
        reflection: 反思（终局合成——成功路径为「一次通过」类文本）
        tools_used: 工具调用轨迹（真实轨迹覆写，含版本后缀；空元组合法）
        constraints_check: 约束检查结论（终局合成）
        final_answer: 最终结构化答案（JSON 尾段原样——终局合成）
    """

    input_summary: str
    reflection: str
    tools_used: tuple[str, ...]
    constraints_check: str
    final_answer: str

    def __post_init__(self) -> None:
        """自校验：四 str 字段先类型后空值；tools_used 元组元素级类型守卫。

        校验顺序契约（AgentProfile VO 先例——5-1 R2-F2 教训防线）：
        先 isinstance(str) 类型守卫再 strip 判空——truthy 标量（如 int 12345）
        会越过纯判空检查静默通过。tools_used 允许空元组（无工具任务合法
        形态），但元素必须为非空 str（轨迹条目级非空）。
        """
        for field_name in _TEXT_FIELDS:
            value = getattr(self, field_name)
            if not isinstance(value, str):
                raise EntityValidationError(
                    message=f"ChainOfThought 字段 {field_name} 必须为 str 类型（实际 {type(value).__name__}）",
                    context={"entity_type": "ChainOfThought", "field": field_name},
                )
            if not value.strip():
                raise EntityValidationError(
                    message=f"ChainOfThought 字段 {field_name} 不能为空白",
                    context={"entity_type": "ChainOfThought", "field": field_name},
                )
        if not isinstance(self.tools_used, tuple):
            raise EntityValidationError(
                message=f"tools_used 必须为 tuple 类型（实际 {type(self.tools_used).__name__}）——frozen VO 禁可变序列字段",
                context={"entity_type": "ChainOfThought", "field": "tools_used"},
            )
        for item in self.tools_used:
            if not isinstance(item, str) or not item.strip():
                raise EntityValidationError(
                    message="tools_used 元素必须为非空 str（工具轨迹条目级校验）",
                    context={"entity_type": "ChainOfThought", "field": "tools_used"},
                )

    def to_display(self) -> str:
        """生成五段展示形态文本（存储用结构化、展示用标签——DC-2）。

        格式（or.md §五.5 L480 展示契约）：
            Input: {input_summary}
            → <Reflection>…</Reflection>
            → <Tools_Used>…</Tools_Used>（逐行轨迹；空轨迹为 (none) 占位）
            → <Constraints_Check>…</Constraints_Check>
            → {final_answer}（JSON 尾段原样）

        Returns:
            五段 XML 标签展示文本（段间以 → 分隔）
        """
        tools_lines = "\n".join(self.tools_used) if self.tools_used else "(none)"
        return (
            f"Input: {self.input_summary}\n"
            f"→ <Reflection>\n{self.reflection}\n</Reflection>\n"
            f"→ <Tools_Used>\n{tools_lines}\n</Tools_Used>\n"
            f"→ <Constraints_Check>\n{self.constraints_check}\n</Constraints_Check>\n"
            f"→ {self.final_answer}"
        )


__all__ = ["ChainOfThought"]
