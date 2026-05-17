"""SISYS 应用层压缩服务端口模块。

用于依赖倒置：MemoryService 通过此协议注入 L1Compressor 实现。

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class CompressionResult:
    """压缩结果。

    Attributes:
        compressed: 压缩后的内容（约 150 字）。
        original_length: 原始长度。
        compressed_length: 压缩后长度。
        ratio: 压缩率。
    """

    compressed: str
    original_length: int
    compressed_length: int
    ratio: float


class CompressorService(Protocol):
    """压缩接口。

    实现类：L1Compressor（src/application/text_processing/l1_compressor.py）

    混合压缩策略：
    - ≤200 字：直接规则压缩（无 LLM 调用）
    - >200 字：LLM 压缩至约 150 字
    """

    def compress(self, content: str) -> CompressionResult:
        """压缩内容至约 150 字，压缩率≥70%。

        Args:
            content: 待压缩内容（≤500 字）

        Returns:
            CompressionResult，包含压缩后内容和统计信息

        Raises:
            ValueError: 如果内容超过限制
        """

    def supports(self, content: str) -> bool:
        """判断此压缩器是否支持处理给定内容。

        Args:
            content: 待压缩内容

        Returns:
            True 如果支持，False 否则
        """
