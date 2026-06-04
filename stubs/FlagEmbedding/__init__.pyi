"""FlagEmbedding 类型存根

基于 FlagEmbedding v1.2+ (BAAI/bge-m3) 公开 API 提供完整类型定义。
FlagEmbedding 是 BAAI 开源的嵌入模型工具包，BGEM3FlagModel 封装 BGE-M3 的多语言嵌入生成。
覆盖 EmbeddingAPIServer 使用的方法。
来源: src/infrastructure/external_services/embedding/embedding_api_server.py
"""

from typing import Any, Literal, overload

import numpy as np
from numpy.typing import NDArray

class BGEM3FlagModel:
    """BGE-M3 多语言嵌入模型

    封装 BAAI/bge-m3，支持三种输出模式：
    - Dense: 1024 维 L2 归一化语义向量 (return_dense=True)
    - Sparse: 词法权重向量，BM25 风格关键词匹配 (return_sparse=True)
    - ColBERT: 多向量表示，用于后期交互重排序 (return_colbert_vecs=True)

    GPU 推理时建议 use_fp16=True 以降低显存占用。
    """

    def __init__(
        self,
        model_name_or_path: str,
        use_fp16: bool = False,
        devices: str | list[str] | None = None,
        **kwargs: Any,
    ) -> None: ...

    @overload
    def encode(
        self,
        sentences: str | list[str],
        return_dense: Literal[True] = True,
        return_sparse: bool = False,
        return_colbert_vecs: bool = False,
        batch_size: int = 256,
        max_length: int = 8192,
    ) -> dict[str, NDArray[np.float32] | list[dict[str, Any]] | None]: ...

    @overload
    def encode(
        self,
        sentences: str | list[str],
        *,
        return_dense: bool = True,
        return_sparse: Literal[True],
        return_colbert_vecs: bool = False,
        batch_size: int = 256,
        max_length: int = 8192,
    ) -> dict[str, NDArray[np.float32] | list[dict[str, Any]] | None]: ...

    def __repr__(self) -> str: ...
