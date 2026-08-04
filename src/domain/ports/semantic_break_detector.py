"""语义断裂检测端口模块

定义 SemanticBreakDetector Protocol，用于弱结构文档（会议纪要/访谈）的语义断裂检测。

status: deferred — 实现触发条件:
  Epic 3 Story 3.7 检索相关性评估中，任一文档类型 Top-5 Recall < 0.80
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SemanticBreakDetector(Protocol):
    """语义断裂检测端口协议

    对弱结构文档（会议纪要、访谈记录等）的文本片段列表，
    检测相邻片段间的语义断裂点。

    实现触发条件（Epic 3 Story 3.7）：
      某文档类型（如：会议纪要）Top-5 Recall < 0.80

    预期实现方案：
      使用 BGE-M3 embedding 计算相邻 segment 的余弦相似度，
      低于 threshold 处标记为断裂点。

    Methods:
        detect_breaks: 检测语义断裂点索引列表
    """

    async def detect_breaks(
        self,
        segments: list[str],
        threshold: float = 0.65,
    ) -> list[int]:
        """检测语义断裂点

        对文本片段列表中的相邻片段进行语义相似度分析，
        返回语义断裂点索引列表。

        Args:
            segments: 文本片段列表（按原始阅读顺序排列）
            threshold: 语义相似度阈值（0.0~1.0），低于此值的相邻片段将被标记为断裂点

        Returns:
            断裂点索引列表（断裂发生在 segments[i] 和 segments[i+1] 之间）

        Raises:
            ValueError: segments 为空列表时抛出

        Example:
            >>> segments = ["章节A内容...", "完全不同的主题B..."]
            >>> detects = await detector.detect_breaks(segments, threshold=0.65)
            >>> # detects = [0]  表示在 segments[0] 和 segments[1] 之间存在语义断裂
        """
        ...


__all__ = ["SemanticBreakDetector"]
