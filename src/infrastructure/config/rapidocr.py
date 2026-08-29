"""基础设施层 RapidOCR 配置模块

通过环境变量提供本地 RapidOCR 模型、执行提供者和并发配置。
领域层仅依赖 OCRPort，不直接依赖此配置模块。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from src.domain.exceptions import ConfigurationError


@dataclass(frozen=True)
class RapidOCRConfig:
    """RapidOCR 本地推理配置。

    Attributes:
        model_dir: 模型配置或模型根目录；空值使用包默认模型。
        max_concurrency: 单个模型实例允许的最大并发推理数。
    """

    model_dir: str = ""
    max_concurrency: int = 1

    @classmethod
    def from_env(cls) -> RapidOCRConfig:
        """从环境变量加载配置。"""
        raw_concurrency = os.getenv("RAPIDOCR_MAX_CONCURRENCY", "1")
        try:
            max_concurrency = int(raw_concurrency)
        except ValueError as exc:
            raise ConfigurationError(message="RAPIDOCR_MAX_CONCURRENCY 必须为整数", cause=exc) from exc
        return cls(
            model_dir=os.getenv("RAPIDOCR_MODEL_DIR", ""),
            max_concurrency=max_concurrency,
        )


__all__ = ["RapidOCRConfig"]
