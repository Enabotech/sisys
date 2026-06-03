"""基础设施层嵌入模型配置

管理 BGE-M3 嵌入模型的连接参数，支持本地模式和 API 模式双策略部署。
架构参考: architecture.md §4.3 嵌入模型配置
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class EmbeddingConfig:
    """嵌入模型配置

    Attributes:
        model_name: HuggingFace 模型名称
        model_path: 本地模型路径（非空时优先于 model_name）
        device: 推理设备（cuda/cpu）
        dimension: 嵌入向量维度
        api_url: 嵌入 API 服务地址（非空时启用 API 模式，绕过本地模型加载）
        api_timeout: API 请求超时秒数
    """

    model_name: str = "BAAI/bge-m3"
    model_path: str = ""
    device: str = "cuda"
    dimension: int = 1024
    api_url: str = ""
    api_timeout: float = 30.0

    @classmethod
    def from_env(cls) -> EmbeddingConfig:
        """从环境变量构建配置

        Returns:
            嵌入模型配置实例
        """
        return cls(
            model_name=os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3"),
            model_path=os.getenv("EMBEDDING_MODEL_PATH", ""),
            device=os.getenv("EMBEDDING_MODEL_DEVICE", "cuda"),
            dimension=int(os.getenv("EMBEDDING_MODEL_DIMENSION", "1024")),
            api_url=os.getenv("EMBEDDING_API_URL", ""),
            api_timeout=float(os.getenv("EMBEDDING_API_TIMEOUT", "30.0")),
        )
