"""领域层模型推理端口

定义模型推理的抽象契约，由基础设施层实现。
遵循 R1：领域层统一抽象各类基础端口，零外部依赖。

设计原则：
- 只定义最基本的推理契约，不区分 Dense/Sparse/ColBERT 等嵌入类型
- 使用 dict 作为 encode() 返回值，避免领域层依赖 numpy/FlagEmbedding 类型
- EmbeddingServicePort 是 ModelInferencePort 的高阶语义组合：
  - embed_query(text) = encode([text], return_sparse=False) → dense[0]
  - embed_documents(texts) = encode(texts, return_sparse=False) → dense
  - embed_sparse(texts) = encode(texts, return_sparse=True) → sparse
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ModelInferencePort(Protocol):
    """模型推理端口

    提供模型推理的最基本抽象，不区分嵌入类型。
    由 SafeBGE3Model、ONNXModel、OpenAIEmbedding 等具体实现。
    调用方通过 encode() 获取原始模型输出，高阶语义由组合层封装。
    """

    @property
    def dimension(self) -> int:
        """模型输出向量维度

        Returns:
            向量维度（bge-m3 为 1024）
        """
        ...

    async def encode(
        self,
        texts: list[str],
        return_sparse: bool = False,
    ) -> dict:
        """模型推理入口

        对文本列表执行模型推理，返回 Dense 向量和可选的 Sparse 权重。
        使用 dict 作为返回值，避免领域层依赖特定技术类型。

        Args:
            texts: 待编码文本列表（至少 1 条）
            return_sparse: 是否返回稀疏词汇权重

        Returns:
            {"dense": list[list[float]], "sparse": list[dict] | None}
            - dense: 浮点向量列表（每项经 L2 归一化）
            - sparse: 稀疏向量列表 [{"indices": [...], "values": [...]}, ...]

        Raises:
            ModelInferenceError: 模型未加载或推理失败时
        """
        ...

    async def close(self) -> None:
        """释放模型持有的资源（GPU 内存等）

        关闭后实例不可再使用。调用 close() 是幂等的。
        """
        ...


__all__ = [
    "ModelInferencePort",
]
