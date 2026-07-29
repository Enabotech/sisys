"""领域层嵌入服务端口

定义文本嵌入生成的领域接口，由基础设施层实现
架构参考: architecture.md §4.3 L3 向量层嵌入生成
设计原则: 领域层零外部依赖，Protocol 仅声明方法签名

命名规范: 对标 LangChain Embeddings 基类 —
- embed_query: 查询嵌入（搜索时编码用户查询文本）
- embed_documents: 文档嵌入（索引时批量编码文档）
- embed_sparse: 稀疏词汇权重嵌入（BM25 风格精确关键词匹配）
"""

from __future__ import annotations

from typing import Protocol, TypedDict, runtime_checkable


class SparseEmbedding(TypedDict):
    """稀疏嵌入向量

    对应 FlagEmbedding 的 lexical_weights 输出，
    为 Story 3-1b（BM25 稀疏检索 + RRF 融合）提供 Sparse 嵌入能力。

    Attributes:
        indices: 词元 ID 列表（升序排列）
        values: 词元权重列表（与 indices 一一对应）
    """

    indices: list[int]
    values: list[float]


@runtime_checkable
class EmbeddingServicePort(Protocol):
    """嵌入服务端口

    提供文本到向量的嵌入生成能力，由 BGE-M3 模型（FlagEmbedding）实现。
    支持 Dense（1024 维语义向量）和 Sparse（词汇权重稀疏向量）两种嵌入模式。

    方法分为三类：
    - embed_query / embed_documents: Dense 嵌入，用于余弦相似度语义检索
    - embed_sparse: Sparse 嵌入，用于 BM25 风格精确关键词匹配
    """

    @property
    def dimension(self) -> int:
        """嵌入向量维度

        Returns:
            向量维度（bge-m3 为 1024）
        """
        ...

    async def embed_query(self, text: str) -> list[float]:
        """查询文本 Dense 嵌入

        用于搜索场景：将用户的自然语言查询编码为语义向量。
        与 embed_documents 的区别在于调用语义 — 本方法明确标识"查询"意图，
        未来可支持非对称嵌入模型（如 E5 的 query: / passage: 前缀策略）。

        Args:
            text: 查询文本（单条）

        Returns:
            经 L2 归一化的 1024 维浮点向量

        Raises:
            ValidationError: 文本为空时
        """
        ...

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """文档批量 Dense 嵌入

        用于索引场景：将待检索的文档批量编码为语义向量。
        批量接口统一处理单文档与多文档，调用方传入单元素列表即可。

        Args:
            texts: 待编码文档文本列表

        Returns:
            浮点向量列表（每项经 L2 归一化，1024 维）

        Raises:
            ValidationError: 列表中包含空文本时
        """
        ...

    async def embed_sparse(self, texts: list[str]) -> list[SparseEmbedding]:
        """文档 Sparse 嵌入（批量）

        生成词汇权重的稀疏向量，用于 BM25 风格的精确关键词匹配检索。
        对应 architecture.md §11.1 "Dense+Sparse+Payload 过滤"。
        为 Story 3-1b（BM25 稀疏检索 + RRF 融合）提供 Sparse 嵌入能力。

        Args:
            texts: 待编码文本列表

        Returns:
            SparseEmbedding 列表（每项含 indices 和 values）

        Raises:
            ValidationError: 列表中包含空文本时
        """
        ...

    async def close(self) -> None:
        """释放嵌入服务持有的资源

        关闭 HTTP 连接池或其他网络资源。调用后实例不可再使用。
        由 Composition Root 的 shutdown() 在应用退出时调用。
        """
        ...
