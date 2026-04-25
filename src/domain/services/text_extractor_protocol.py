"""TextExtractorProtocol — 文本提取接口（领域层）。

用于依赖倒置：MemoryService 通过此协议注入 L1TextExtractor 实现。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ExtractionResult:
    """文本提取结果。"""

    content: str  # 提取后的记忆核心内容
    original: str  # 原始用户输入
    pattern: str  # 匹配到的模式（如 "记住 X"）


class TextExtractorProtocol(ABC):
    """文本提取接口。

    实现类：L1TextExtractor（src/application/text_processing/l1_text_extractor.py）
    """

    @abstractmethod
    def extract(self, user_input: str) -> ExtractionResult:
        """从用户输入中提取记忆内容。

        Args:
            user_input: 用户输入（如 "记住，以后用 bun 而不是 npm"）

        Returns:
            ExtractionResult，包含提取后的内容和原始输入

        Raises:
            ValueError: 如果输入无法提取
        """

    @abstractmethod
    def supports(self, user_input: str) -> bool:
        """判断此提取器是否支持处理给定输入。

        Args:
            user_input: 用户输入

        Returns:
            True 如果支持，False 否则
        """
