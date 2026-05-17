"""SISYS 领域层 UDMR 路由任务值对象模块

封装 UDMR（统一数据驻留与模型路由）的任务上下文信息，
作为不可变值对象在领域层传递。遵循六边形架构：值对象，
仅包含业务逻辑，无外部依赖

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass(frozen=True)
class UDMRTask:
    """UDMR 路由任务值对象（不可变）.

    Attributes:
        task_id: 任务唯一标识符
        input: 待检测内容
        data_residency: 数据驻留要求 (CHINA_DOMESTIC/CHINA_HKMO/OVERSEAS)
        preferred_model: 首选模型
        allowed_models: 白名单允许模型列表
    """

    task_id: UUID = field(default_factory=uuid4)
    input: str = ""
    data_residency: str = "CHINA_DOMESTIC"
    preferred_model: str = ""
    allowed_models: list[str] = field(default_factory=list)

    def is_china_domestic(self) -> bool:
        """检查数据是否需要在中国大陆处理

        Returns:
            True 如果 data_residency 为 CHINA_DOMESTIC
        """
        return self.data_residency == "CHINA_DOMESTIC"

    def requires_local_processing(self) -> bool:
        """检查是否需要本地处理

        Returns:
            True 如果 data_residency 为 CHINA_DOMESTIC
        """
        return self.is_china_domestic()

    def get_task_context(self) -> dict:
        """获取任务上下文，用于 UDMR 路由决策

        Returns:
            dict 包含任务上下文信息
        """
        return {
            "task_id": str(self.task_id),
            "session_id": str(self.task_id),
            "complexity": "high" if self.requires_local_processing() else "normal",
            "data_residency": self.data_residency,
            "preferred_model": self.preferred_model,
            "allowed_models": self.allowed_models,
        }
