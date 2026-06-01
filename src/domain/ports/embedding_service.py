"""领域层嵌入服务端口

定义文本嵌入生成的领域接口，由基础设施层实现
架构参考: architecture.md §4.3 L3 向量层嵌入生成
设计原则: 领域层零外部依赖，Protocol 仅声明方法签名
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingServicePort(Protocol):
    """嵌入服务端口

    提供文本到向量的嵌入生成能力，由 BGE-M3 模型实现
    """

    @property
    def dimension(self) -> int:
        """嵌入向量维度

        Returns:
            向量维度（bge-m3 为 1024）
        """
        ...

    def encode_text(self, text: str) -> list[float]:
        """单文本编码

        Args:
            text: 待编码文本

        Returns:
            浮点向量（经 L2 归一化）

        Raises:
            ValueError: 文本为空时
        """
        ...

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        """批量文本编码

        Args:
            texts: 待编码文本列表

        Returns:
            浮点向量列表（经 L2 归一化）

        Raises:
            ValueError: 列表中包含空文本时
        """
        ...
