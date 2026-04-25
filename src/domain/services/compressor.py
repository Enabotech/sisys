"""Compressor — 压缩接口（领域层）。

用于依赖倒置：MemoryService 通过此协议注入 L1Compressor 实现。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CompressionResult:
    """压缩结果。"""

    compressed: str  # 压缩后的内容（约 150 字）
    original_length: int  # 原始长度
    compressed_length: int  # 压缩后长度
    ratio: float  # 压缩率


class CompressorProtocol(ABC):
    """压缩接口。

    实现类：L1Compressor（src/application/text_processing/l1_compressor.py）

    混合压缩策略：
    - ≤200 字：直接规则压缩（无 LLM 调用）
    - >200 字：LLM 压缩至约 150 字
    """

    @abstractmethod
    def compress(self, content: str) -> CompressionResult:
        """压缩内容至约 150 字，压缩率≥70%。

        Args:
            content: 待压缩内容（≤500 字）

        Returns:
            CompressionResult，包含压缩后内容和统计信息

        Raises:
            ValueError: 如果内容超过限制
        """

    @abstractmethod
    def supports(self, content: str) -> bool:
        """判断此压缩器是否支持处理给定内容。

        Args:
            content: 待压缩内容

        Returns:
            True 如果支持，False 否则
        """
