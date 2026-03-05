"""
sisys - Domain Entities.

领域实体模块 - 包含核心业务实体定义。
"""

from src.domain.entities.base import AggregateRoot, BaseEntity, ValueObject
from src.domain.entities.strategic_plan import PlanStatus, PlanType, StrategicPlan

__all__ = [
    # 基类
    "BaseEntity",
    "AggregateRoot",
    "ValueObject",
    # 实体
    "StrategicPlan",
    # 枚举
    "PlanType",
    "PlanStatus",
]
