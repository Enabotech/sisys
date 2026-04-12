"""
sisys - Domain Events.

领域事件模块 - 包含所有领域事件定义。
"""

from src.domain.events.base import DomainEvent
from src.domain.events.plan_events import PlanCreated, PlanStatusChanged

__all__ = [
    "DomainEvent",
    "PlanCreated",
    "PlanStatusChanged",
]
