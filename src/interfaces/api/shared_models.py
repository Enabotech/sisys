"""接口层共享响应模型模块

提供 API 路由共用的 Pydantic 响应模型，避免重复定义。
遵循 R4（接口层统一管理外部响应格式）。
"""

from __future__ import annotations

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """标准错误响应模型（用于 OpenAPI 文档）

    Attributes:
        detail: 错误详情
    """

    detail: str
