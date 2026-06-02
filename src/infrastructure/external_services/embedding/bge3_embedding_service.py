"""基础设施层 BGE-M3 嵌入服务实现

使用 FlagEmbedding (BAAI 官方库) 加载 bge-m3 模型，提供 Dense + Sparse 双模式嵌入生成能力。
架构参考: architecture.md §4.3 嵌入模型实现
依赖: FlagEmbedding, torch

迁移说明（2026-06-02）:
- 从 SentenceTransformers 迁移至 FlagEmbedding（BGEM3FlagModel）
- 原因: BGE-M3 是 BAAI 发布的模型，FlagEmbedding 是 BAAI 官方第一方库，天然支持 Dense+Sparse+ColBERT
- 一次推理同时产出 Dense 和 Sparse 嵌入，减少延迟和内存
- 原生多语言 tokenizer，中文分词质量优于自建 BM25Builder
"""

from __future__ import annotations

import logging
import os
from typing import Any, cast

import numpy as np
from FlagEmbedding import BGEM3FlagModel

from src.infrastructure.config.embedding import EmbeddingConfig

logger = logging.getLogger(__name__)


class BGE3EmbeddingService:
    """BGE-M3 嵌入服务实现

    实现 EmbeddingServicePort 接口，提供 Dense（语义向量）和 Sparse（词汇权重）编码功能。
    使用 FlagEmbedding 的 BGEM3FlagModel 加载模型，支持本地路径和 HuggingFace Hub 两种加载方式。
    """

    def __init__(self, config: EmbeddingConfig | None = None) -> None:
        """初始化嵌入服务

        Args:
            config: 嵌入模型配置，为空时使用默认配置

        Raises:
            ValueError: 配置维度与模型实际维度不一致时
        """
        if config is None:
            config = EmbeddingConfig()
        self._config = config

        model_path = config.model_path if config.model_path and os.path.isdir(config.model_path) else config.model_name
        use_fp16 = config.device == "cuda"

        if config.model_path and os.path.isdir(config.model_path):
            logger.info("从本地路径加载嵌入模型: %s (use_fp16=%s)", model_path, use_fp16)
        else:
            logger.info("从 HuggingFace Hub 加载嵌入模型: %s (use_fp16=%s)", config.model_name, use_fp16)

        self._model: BGEM3FlagModel = BGEM3FlagModel(model_path, use_fp16=use_fp16)

        # 维度验证：通过一次轻量推理验证模型维度与配置一致
        test_result = self._model.encode("dimension check", return_dense=True)
        actual_dim = int(test_result["dense_vecs"].shape[-1])
        if actual_dim != config.dimension:
            raise ValueError(f"配置维度 ({config.dimension}) 与模型实际维度 ({actual_dim}) 不一致")

    @property
    def dimension(self) -> int:
        """嵌入向量维度

        Returns:
            向量维度（bge-m3 为 1024）
        """
        return self._config.dimension

    def encode_text(self, text: str) -> list[float]:
        """单文本 Dense 编码

        Args:
            text: 待编码文本

        Returns:
            经 L2 归一化的 1024 维浮点向量

        Raises:
            ValueError: 文本为空时
        """
        if not text or not text.strip():
            raise ValueError("文本不能为空")
        result = self._model.encode(text, return_dense=True)
        return cast(list[float], cast(np.ndarray, result["dense_vecs"]).tolist())

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        """批量文本 Dense 编码

        Args:
            texts: 待编码文本列表（空列表返回空结果）

        Returns:
            经 L2 归一化的浮点向量列表

        Raises:
            ValueError: 列表中包含空文本时
        """
        if not texts:
            return []
        for i, t in enumerate(texts):
            if not t or not t.strip():
                raise ValueError(f"批量编码中包含空文本: 索引 {i}")
        result = self._model.encode(texts, return_dense=True, batch_size=12)
        return cast(list[list[float]], cast(np.ndarray, result["dense_vecs"]).tolist())

    def encode_sparse(self, text: str) -> dict[str, list[Any]]:
        """单文本 Sparse 编码

        生成词汇权重的稀疏向量，用于 BM25 风格的精确关键词匹配检索。
        使用 BGE-M3 原生 tokenizer 和模型学习的词汇权重，中文分词质量优于自建 TF-IDF。

        Args:
            text: 待编码文本

        Returns:
            稀疏向量 dict：
            {"indices": list[int], "values": list[float]}

        Raises:
            ValueError: 文本为空时
        """
        if not text or not text.strip():
            raise ValueError("文本不能为空")
        result = self._model.encode(text, return_sparse=True)
        lexical_raw = result["lexical_weights"]

        # FlagEmbedding API: 单文本返回 List[Dict[int, float]]，取第一项
        if isinstance(lexical_raw, list):
            if not lexical_raw:
                return {"indices": [], "values": []}
            lexical_weights: dict[int, float] = lexical_raw[0]
        else:
            lexical_weights = lexical_raw

        indices = sorted(lexical_weights.keys())
        values = [float(lexical_weights[i]) for i in indices]

        return {"indices": indices, "values": values}
