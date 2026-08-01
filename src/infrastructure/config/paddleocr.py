"""基础设施层 PaddleOCR-VL 配置模块

提供 PaddleOCR-VL API 连接配置，用于 OCR 扫描件解析。
遵循项目统一的 @dataclass + from_env() 配置模式。
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class PaddleOCRConfig:
    """PaddleOCR-VL 连接配置

    用于 OCR 端口（PaddleOCRVLAdapter）的 API 连接配置。

    Attributes:
        api_url: PaddleOCR-VL API 地址
        api_timeout: HTTP 请求超时时间（秒）
    """

    api_url: str = "http://localhost:8080"
    api_timeout: float = 300.0

    @classmethod
    def from_env(cls) -> PaddleOCRConfig:
        """从环境变量加载配置

        环境变量：
        - PADDLEOCR_VL_API_URL: API 地址（默认 http://localhost:8080）
        - PADDLEOCR_VL_API_TIMEOUT: 超时秒数（默认 300）

        Returns:
            配置实例
        """
        return cls(
            api_url=os.getenv("PADDLEOCR_VL_API_URL", "http://localhost:8080"),
            api_timeout=float(os.getenv("PADDLEOCR_VL_API_TIMEOUT", "300.0")),
        )
