"""应用层 L1 文本提取器模块

从用户输入中提取记忆内容

支持的模式：
- "记住 X" → 提取 X
- "记住了 X" → 提取 X
- "以后用 X" → 提取 X
- "要记住 X" → 提取 X
- "别忘了 X" → 提取 X
- "改成 X" → 提取 X（用于修改操作）
- "不要记住 X" → 触发删除操作（返回空 content，operation='delete'）

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.application.ports.text_extractor_service import ExtractionResult, TextExtractorService


@dataclass
class L1ExtractionResult(ExtractionResult):
    """L1 文本提取结果

    Attributes:
        operation: 操作类型，"save"、"delete" 或 "update"
    """

    operation: str = "save"  # "save" | "delete" | "update"


class L1TextExtractor(TextExtractorService):
    """L1 文本提取器，从"记住 X"等模式中提取记忆核心内容 X

    Attributes:
        PATTERNS: 提取模式列表（按优先级排序）
    """

    # 提取模式（按优先级排序）
    # 使用 \s+ 或标点符号分隔，确保能匹配 "记住X" 无空格和 "记住 X" 有空格的情况
    PATTERNS = [
        # 删除操作
        (re.compile(r"^不要记住[，,\s]+(.+)$", re.DOTALL), "delete"),
        (re.compile(r"^别忘了[，,\s]+(.+)$", re.DOTALL), "delete"),
        # 修改操作 - 使用更宽松的分隔符匹配
        (re.compile(r"^改成[，,\s]*[：:=\s]*(.+)$", re.DOTALL), "update"),
        (re.compile(r"^更正为[，,\s]*[：:=\s]*(.+)$", re.DOTALL), "update"),
        (re.compile(r"^改为[，,\s]*[：:=\s]*(.+)$", re.DOTALL), "update"),
        # 保存操作
        (re.compile(r"^记住[，,\s]+(.+)$", re.DOTALL), "save"),
        (re.compile(r"^记住了[，,\s]+(.+)$", re.DOTALL), "save"),
        (re.compile(r"^以后用[，,\s]+(.+)$", re.DOTALL), "save"),
        (re.compile(r"^要记住[，,\s]+(.+)$", re.DOTALL), "save"),
        # 无空格边界情况（如 "记住abc"）- 放在最后兜底
        (re.compile(r"^记住(.+)$", re.DOTALL), "save"),
    ]

    def extract(self, user_input: str) -> L1ExtractionResult:
        """从用户输入中提取记忆内容

        Args:
            user_input: 用户输入（如 "记住，以后用 bun 而不是 npm"）

        Returns:
            L1ExtractionResult，包含提取后的内容、操作类型和匹配模式

        Raises:
            ValueError: 如果输入无法提取
        """
        if not user_input or not user_input.strip():
            raise ValueError("输入不能为空")

        user_input = user_input.strip()

        for pattern, operation in self.PATTERNS:
            match = pattern.match(user_input)
            if match:
                content = match.group(1).strip()
                return L1ExtractionResult(
                    content=content,
                    original=user_input,
                    pattern=pattern.pattern,
                    operation=operation,
                )

        # 无法匹配模式
        raise ValueError(f"无法识别输入模式: {user_input}")

    def supports(self, user_input: str) -> bool:
        """判断此提取器是否支持处理给定输入

        Args:
            user_input: 用户输入

        Returns:
            True 如果支持，False 否则
        """
        if not user_input:
            return False
        for pattern, _ in self.PATTERNS:
            if pattern.match(user_input.strip()):
                return True
        return False
