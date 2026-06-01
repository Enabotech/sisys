"""基础设施层 BGE-M3 嵌入服务实现

使用 SentenceTransformer 加载 bge-m3 模型，提供文本到向量的嵌入生成能力
架构参考: architecture.md §4.3 嵌入模型实现
依赖: sentence-transformers, torch
"""

from __future__ import annotations

import logging
import os
from typing import cast

import numpy as np
from sentence_transformers import SentenceTransformer

from src.infrastructure.config.embedding import EmbeddingConfig

logger = logging.getLogger(__name__)


class BGE3EmbeddingService:
    """BGE-M3 嵌入服务实现

    实现 EmbeddingServicePort 接口，提供文本编码功能
    """

    def __init__(self, config: EmbeddingConfig | None = None) -> None:
        """初始化嵌入服务

        Args:
            config: 嵌入模型配置，为空时使用默认配置
        """
        if config is None:
            config = EmbeddingConfig()
        self._config = config

        if config.model_path and os.path.isdir(config.model_path):
            logger.info("从本地路径加载嵌入模型: %s", config.model_path)
            self._model: SentenceTransformer = SentenceTransformer(config.model_path, device=config.device)
        else:
            logger.info("从 HuggingFace Hub 加载嵌入模型: %s", config.model_name)
            self._model = SentenceTransformer(config.model_name, device=config.device)

    @property
    def dimension(self) -> int:
        """嵌入向量维度

        Returns:
            向量维度（bge-m3 为 1024）
        """
        return int(self._model.get_sentence_embedding_dimension())

    def encode_text(self, text: str) -> list[float]:
        """单文本编码

        Args:
            text: 待编码文本

        Returns:
            经 L2 归一化的浮点向量

        Raises:
            ValueError: 文本为空时
        """
        if not text or not text.strip():
            raise ValueError("文本不能为空")
        embedding = self._model.encode(text, normalize_embeddings=True)
        return cast(list[float], cast(np.ndarray, embedding).tolist())

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        """批量文本编码

        Args:
            texts: 待编码文本列表

        Returns:
            经 L2 归一化的浮点向量列表
        """
        if not texts:
            return []
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return cast(list[list[float]], cast(np.ndarray, embeddings).tolist())
